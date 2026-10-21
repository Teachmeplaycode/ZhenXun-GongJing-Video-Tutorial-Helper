"""Tab completion in the composer: the rest of the question the person is typing, in a few words.

The page asks after a short pause in typing (desktop only); the answer is shown in grey after the
caret and Tab takes it. The model sees the video's title, chapters, the suggested questions and the
last question asked, and writes only what comes next. Cheap and short: at most MAX_TOKENS, one
request per person per MIN_GAP seconds and DAY_LIMIT a day; completions don't count as questions.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from modules import log, visitors
from modules.llm import LLMError, Usage

MAX_TOKENS = 32
MAX_CHARS = 24
MIN_GAP = 0.6
DAY_LIMIT = 400

SYSTEM = """你在帮用户补全他正在输入框里打的一句话：一个关于他正在看的视频的问题。
只输出紧接着已输入文字之后要补上的部分：不要重复已经输入的字，不超过 20 个字，到这句问题结束为止（可以带问号）。
贴着视频内容补：用视频里真实出现的功能名、按钮名、人物、说法。拿不准、或者这句话已经完整了，就什么都不输出。
不要解释，不要加引号。"""


class Typed(BaseModel):
    text: str


def context(job, suggestions: list[str], last_question: str) -> str:
    parts = [f"视频标题：{job.video.title}"]
    try:
        chapters = json.loads((job.root / "chapters.json").read_text()).get("chapters") or []
        if chapters:
            parts.append("章节：" + "；".join(c.get("title", "") for c in chapters[:12]))
    except (OSError, ValueError):
        pass
    if suggestions:
        parts.append("推荐过的问题：" + "；".join(suggestions[:3]))
    if last_question:
        parts.append(f"用户上一个问题：{last_question[:80]}")
    return "\n".join(parts)


def clean(raw: str, typed: str) -> str:
    """The model's continuation, trimmed to what goes after `typed`."""
    text = (raw or "").strip().split("\n", 1)[0].strip().strip("\"'“”「」")
    if typed and text.startswith(typed):  # it repeated what was typed
        text = text[len(typed):]
    text = re.sub(r"^(补全|续写|输出)[:：]\s*", "", text)
    return text[:MAX_CHARS]


class CompleteService:
    def __init__(self, get_job, get_client, last_question, suggestions):
        self.get_job, self.get_client = get_job, get_client
        self.last_question, self.suggestions = last_question, suggestions
        self.calls: dict[str, list[float]] = defaultdict(list)
        self.router = APIRouter()
        self.router.add_api_route("/api/link-jobs/{job_id}/complete", self.complete, methods=["POST"])

    def _allow(self, who: str) -> bool:
        now, seen = time.time(), self.calls[who]
        seen[:] = [t for t in seen if now - t < 86400]
        if (seen and now - seen[-1] < MIN_GAP) or len(seen) >= DAY_LIMIT:
            return False
        seen.append(now)
        return True

    async def complete(self, job_id: str, body: Typed):
        job = self.get_job(job_id)
        typed = body.text[-200:]
        if len(typed.strip()) < 2 or not self._allow(visitors.current.get() or "local"):
            return {"completion": ""}
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": context(job, self.suggestions(job), self.last_question(job.id))
                     + f"\n\n已输入：{typed}"}]
        timer = log.Timer()
        try:
            chunks = []
            async for delta in self.get_client().stream(messages, Usage(), max_tokens=MAX_TOKENS):
                chunks.append(delta)
        except LLMError as exc:
            raise HTTPException(503, exc.message if hasattr(exc, "message") else "补全暂时不可用") from None
        completion = clean("".join(chunks), typed)
        log.event("complete", job_id=job.id, chars=len(completion), ms=timer.ms)
        return {"completion": completion}
