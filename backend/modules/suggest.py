"""Questions worth asking about this very video, offered before the first question.

Once speech and on-screen text are read, the model reads the title, a sample of both and the
chapter list, and writes three questions the video can answer, in its own terms: the buttons and
menus a tutorial clicks, the claims a health video makes, the people and events of a vlog. A
tutorial gets one question about a particular step and one about where it goes wrong; a video
making health claims gets one asking whether they hold. Generated once per session and kept in
<job>/suggestions.json; GET /api/link-jobs/{id}/suggestions says waiting / running / done / failed.
"""
from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter

from modules import log
from modules.llm import LLMError, Usage

FILE = "suggestions.json"
COUNT = 3
MAX_CHARS = 36
KINDS = {"tutorial": "教程操作", "content": "视频内容", "science": "科普核查", "fraud": "反诈识别"}
SPEECH_CHARS, SCREEN_CHARS = 3500, 2000

SYSTEM = """你在为一个视频理解助手写「推荐问题」：用户刚打开这个视频，还没想好问什么，你替他想 3 个值得问、而且这个视频真能回答的问题。

要求：
- 具体到这个视频：用视频里真实出现的软件功能、按钮菜单名、人物、事件、说法来问，不要问「视频讲了什么」这种放在哪个视频都成立的问题。
- 能从视频里找到答案；不要问视频之外的知识。
- 软件或操作教程：一个问某个具体操作在哪一步、点了什么（例如「数据透视表是在哪一步改成表格形式的？」），一个问哪一步最容易出错或为什么这样做，再一个问整体步骤或某个设置。
- 讲健康、医学、养生、科学说法的视频：其中一个问这些说法对不对。
- 涉及投资、理财、领福利、加群、卖货的视频：其中一个问有没有诈骗或引流风险。
- 三个问题角度不同；每个不超过 30 个字；问题里不要写时间点。
- kind 是问题的类型：tutorial（教程操作）、content（视频内容）、science（核查说法）、fraud（诈骗风险）。
- hint 用 10 个字以内说这个问题能帮用户弄清什么。

只返回 JSON：{"questions":[{"question":"…","kind":"…","hint":"…"}]}"""


def clock(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def _sample(lines: list[str], budget: int) -> list[str]:
    """Lines spread over the whole video within `budget` characters (start, middle and end all show)."""
    if sum(len(x) + 1 for x in lines) <= budget:
        return lines
    keep = max(1, budget // max(1, sum(len(x) + 1 for x in lines) // len(lines)))
    step = len(lines) / keep
    return [lines[int(i * step)] for i in range(keep)]


def context(job) -> str:
    video = job.video
    parts = [f"标题：{video.title}"]
    if video.description:
        parts.append(f"简介：{video.description[:300]}")
    speech = [f"[{clock(s.start)}] {s.text.strip()}" for s in (job.transcript.segments if job.transcript else []) if s.text.strip()]
    seen, screen = set(), []
    for c in (job.screentext.segments if job.screentext else []):
        text = c.text.strip()
        if text and text not in seen:
            seen.add(text)
            screen.append(f"[{clock(c.start)}] {text}")
    if speech:
        parts.append("语音转写（节选）：\n" + "\n".join(_sample(speech, SPEECH_CHARS)))
    if screen:
        parts.append("画面文字（节选）：\n" + "\n".join(_sample(screen, SCREEN_CHARS)))
    try:
        chapters = json.loads((job.root / "chapters.json").read_text()).get("chapters") or []
        if chapters:
            parts.append("章节：" + "；".join(f"{clock(c.get('start', 0))} {c.get('title', '')}" for c in chapters[:12]))
    except (OSError, ValueError):
        pass
    return "\n\n".join(parts)


def parse(raw: str) -> list[dict]:
    """The model's questions, cleaned: at most COUNT, distinct, short, with a known kind."""
    start, end = (raw or "").find("{"), (raw or "").rfind("}")
    try:
        items = json.loads(raw[start:end + 1]).get("questions") or [] if 0 <= start < end else []
    except (ValueError, AttributeError):
        items = []
    out, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            continue
        q = re.sub(r"\s+", " ", str(item.get("question") or "")).strip()
        if not q or len(q) > MAX_CHARS or q in seen:
            continue
        seen.add(q)
        kind = item.get("kind") if item.get("kind") in KINDS else "content"
        out.append({"question": q, "kind": kind, "label": KINDS[kind], "hint": str(item.get("hint") or "").strip()[:16]})
        if len(out) == COUNT:
            break
    return out


def load(root) -> dict | None:
    try:
        return json.loads((root / FILE).read_text())
    except (OSError, ValueError):
        return None


def save(root, record: dict) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / FILE).write_text(json.dumps(record, ensure_ascii=False))
    return record


def ready(job) -> bool:
    """Speech and on-screen text have both settled (done, empty, unavailable or failed)."""
    return all(getattr(getattr(job, name, None), "status", "done") not in ("pending", "running")
               for name in ("transcript", "screentext"))


class SuggestService:
    def __init__(self, get_job, spawn, get_client):
        self.get_job, self.spawn, self.get_client = get_job, spawn, get_client
        self.running: set[str] = set()
        self.router = APIRouter()
        self.router.add_api_route("/api/link-jobs/{job_id}/suggestions", self.get, methods=["GET"])

    async def get(self, job_id: str):
        job = self.get_job(job_id)
        record = load(job.root)
        if record is not None:
            return record
        if not ready(job):
            return {"status": "waiting", "questions": []}
        if job.id not in self.running:
            self.running.add(job.id)
            self.spawn(self.build(job))
        return {"status": "running", "questions": []}

    async def build(self, job) -> None:
        timer = log.Timer()
        try:
            client = self.get_client()
            chunks: list[str] = []
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": context(job)}]
            async for delta in client.stream(messages, Usage(), max_tokens=600):
                chunks.append(delta)
            questions = parse("".join(chunks))
            record = {"status": "done" if questions else "failed", "questions": questions}
            save(job.root, record)
            log.event("suggestions", job_id=job.id, count=len(questions), ms=timer.ms)
        except (LLMError, asyncio.TimeoutError) as exc:
            log.event("suggestions", job_id=job.id, error=str(exc)[:80], ms=timer.ms)  # not cached: tried again next time
        except Exception as exc:  # noqa: BLE001
            log.error("suggestions", exc, job_id=job.id)
        finally:
            self.running.discard(job.id)
