"""Write a study note of a video: what the agent would hand a student after a lecture.

Sections follow the chapters (modules/chapters) when there are any, else ~5-minute stretches. For each
section the model reads that stretch's speech and on-screen text (blackboard, slides, subtitles) and
returns its key points, formulas, worked examples, keywords and the moments worth a picture (a full
blackboard, a finished derivation, a clear chart). Those moments are read from the video as frames.
A last call titles the whole note, summarises it and draws a mind map. The result is cached as
notes.json in the job folder; the editor's arrangement of it is saved beside it (notes-board.json).

Only what the video says goes in: the prompts forbid filling gaps from general knowledge, and every
figure must fall inside its section.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

FILE = "notes.json"
BOARD = "notes-board.json"
SECTION_SPAN = 300.0      # seconds per section when the video has no chapters
MAX_SECTIONS = 24
SECTION_CHARS = 9000      # speech + on-screen text one section call may read
MAX_FIGURES = 3           # per section
PARALLEL = 4              # section calls at once

# A model call: messages → the whole reply. FrameGrab: seconds → an image URL (or None).
# Pictures: (start, end) → [(label, image file)] of the section's sampled frames, shown to the model.
Completer = Callable[[list[dict]], Awaitable[str]]
FrameGrab = Callable[[float], Awaitable[str | None]]
Pictures = Callable[[float, float], list[tuple[str, Path]]]
Progress = Callable[[int, int, str], None]


@dataclass
class Figure:
    time: float
    caption: str
    src: str = ""


@dataclass
class Section:
    id: str
    title: str
    start: float
    end: float
    points: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)


def clock(seconds: float) -> str:
    t = max(0, int(seconds))
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def load(root: Path, name: str = FILE) -> dict | None:
    try:
        return json.loads((root / name).read_text())
    except (OSError, ValueError):
        return None


def write(root: Path, record: dict, name: str = FILE) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".{name}.tmp"
    tmp.write_text(json.dumps(record, ensure_ascii=False))
    tmp.replace(root / name)
    return record


def _rows(items: Iterable | None) -> list[tuple[float, float, str]]:
    out = []
    for s in items or ():
        if isinstance(s, (tuple, list)):
            out.append((float(s[0]), float(s[1]), str(s[2]) if len(s) > 2 else ""))
        else:
            out.append((float(s.start), float(s.end), str(getattr(s, "text", ""))))
    return out


def spans(duration: float, chapters: list[dict] | None) -> list[tuple[float, float, str]]:
    """(start, end, suggested title) per section: the chapters, else even stretches."""
    if chapters:
        return [(float(c["start"]), float(c["end"]), str(c.get("title") or "")) for c in chapters][:MAX_SECTIONS]
    if duration <= 0:
        return []
    n = max(1, min(MAX_SECTIONS, round(duration / SECTION_SPAN)))
    step = duration / n
    return [(round(i * step, 2), round(min(duration, (i + 1) * step), 2), "") for i in range(n)]


def stretch_text(transcript, screen, start: float, end: float, limit: int = SECTION_CHARS) -> tuple[str, str]:
    """The speech and on-screen text inside [start, end), timestamped, cut to the budget (speech first)."""
    speech = [f"[{clock(a)}] {t}" for a, b, t in _rows(transcript) if b > start and a < end and t.strip()]
    shown = [f"[{clock(a)}] {t}" for a, b, t in _rows(screen) if b > start and a < end and t.strip()]
    speech_text = "\n".join(speech)
    screen_text = "\n".join(shown)
    room = max(0, limit - min(len(speech_text), limit * 2 // 3))
    return speech_text[: limit - min(len(screen_text), room)], screen_text[:room]


def steps_text(steps: list[dict] | None, start: float, end: float) -> str:
    """The step cards (modules/steps) inside [start, end), one `[mm:ss] action（detail）` line each."""
    return "\n".join(f"[{clock(s['time'])}] {s['action']}" + (f"（{s['detail']}）" if s.get("detail") else "")
                     for s in steps or [] if start <= float(s.get("time", -1)) < end)


SECTION_PROMPT = """你是认真负责的视频笔记整理者。根据这一段的视频画面、语音转写和画面文字，按实际内容整理笔记。
要求：
- 先理解素材类型：可以是电影、镜头分析、知识讲解、生活记录、教程或其他内容，不预设为软件教程或课堂。
- 只写这段视频里真的讲到、写到的内容，不要用常识补充，不要编造例题和结论；转写有错字时按上下文和画面文字纠正。
- 数学、物理等公式用 LaTeX 写在 formulas 里（不加 $ 符号），文字说明写在 points 里。
- figures 选 1 到 3 个能支撑本节内容的清楚画面。time 用秒数，必须在本节时间范围内。
- 附带的画面是本节抽样的几帧（标了时间）；语音转写缺失或很少时，以画面为主。没有公式、例题就将对应数组留空。
- 给了【已整理的步骤】时，它是从这段视频整理出的步骤卡：按它的顺序把操作或内容环节写进要点，配图优先选步骤所在的时间；与语音、画面文字不一致时以原素材为准。
只输出一个 JSON 对象，不要其他文字：
{"title": "本节标题，不超过 20 字",
 "points": ["要点，一句话，不超过 60 字", "……3 到 8 条"],
 "formulas": ["公式或定义，0 到 6 条"],
 "examples": ["例题或案例：题目要点 + 解法关键 + 结论，0 到 4 条"],
 "keywords": ["关键词，2 到 5 个"],
 "figures": [{"time": 123.5, "caption": "这张图展示了什么，不超过 30 字"}]}"""

OVERVIEW_PROMPT = """你根据各节笔记给整份笔记起标题、写摘要、画思维导图。只用给出的内容。
只输出一个 JSON 对象：
{"title": "笔记标题，不超过 24 字",
 "summary": "素材的核心内容和这份笔记的重点，不超过 150 字",
 "mindmap": {"label": "中心主题，不超过 12 字",
             "children": [{"label": "分支，不超过 12 字", "children": [{"label": "要点，不超过 14 字"}]}]}}
思维导图 3 到 8 个分支，每个分支 2 到 5 个要点，按内容关系组织，不要强套课堂或软件教程模板。"""


def parse_json(text: str) -> dict | None:
    """The JSON object in a reply (models sometimes wrap it in ``` fences or add a sentence)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _strings(value, limit: int, length: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        v = str(v).strip() if isinstance(v, (str, int, float)) else ""
        if v and v not in out:
            out.append(v[:length])
    return out[:limit]


def figure_time(value, start: float, end: float) -> float | None:
    """A figure's moment in seconds into the video. Models also write "33:00" or "1:02:03", or count
    from the section's start; a moment that still falls outside the section is a mistake, not a figure."""
    if isinstance(value, str) and re.fullmatch(r"\d{1,2}(:\d{1,2}){1,2}(\.\d+)?", value.strip()):
        t = 0.0
        for part in value.strip().split(":"):
            t = t * 60 + float(part)
    else:
        try:
            t = float(value)
        except (TypeError, ValueError):
            return None
    if start <= t <= end:
        return t
    if 0 <= t <= end - start:  # counted from the section's start
        return start + t
    return None


def section_from(reply: dict | None, sid: str, start: float, end: float, fallback_title: str) -> Section:
    reply = reply or {}
    figures = []
    for f in reply.get("figures") or []:
        if not isinstance(f, dict):
            continue
        t = figure_time(f.get("time"), start, end)
        if t is None:
            continue
        figures.append(Figure(round(t, 2), str(f.get("caption") or "").strip()[:60]))
    title = str(reply.get("title") or "").strip()[:30] or fallback_title or f"第 {sid[1:]} 节"
    return Section(sid, title, start, end,
                   points=_strings(reply.get("points"), 8, 120),
                   formulas=_strings(reply.get("formulas"), 6, 300),
                   examples=_strings(reply.get("examples"), 4, 300),
                   keywords=_strings(reply.get("keywords"), 5, 20),
                   figures=sorted(figures, key=lambda f: f.time)[:MAX_FIGURES])


def mindmap_from(reply: dict | None, title: str, sections: list[Section]) -> dict:
    """The model's mind map, cleaned; else one built from the sections (title → points)."""
    def clean(node, depth):
        if not isinstance(node, dict) or depth > 3:
            return None
        label = str(node.get("label") or "").strip()[:24]
        if not label:
            return None
        kids = [k for k in (clean(c, depth + 1) for c in (node.get("children") or [])[:8]) if k]
        return {"label": label, **({"children": kids} if kids else {})}
    tree = clean((reply or {}).get("mindmap"), 1)
    if tree and tree.get("children"):
        return tree
    return {"label": title[:24], "children": [
        {"label": s.title[:24], **({"children": [{"label": p[:24]} for p in (s.keywords or s.points)[:4]]}
                                   if (s.keywords or s.points) else {})}
        for s in sections]}


def _image_parts(pictures: list[tuple[str, Path]]) -> list[dict]:
    parts = []
    for label, path in pictures:
        try:
            data = base64.b64encode(Path(path).read_bytes()).decode()
        except OSError:
            continue
        parts += [{"type": "text", "text": label}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}]
    return parts


async def build_note(*, title: str, duration: float, transcript, screen, chapters: list[dict] | None,
                     complete: Completer, grab: FrameGrab, progress: Progress | None = None,
                     pictures: Pictures | None = None, steps: list[dict] | None = None) -> dict:
    """The note as a dict (see Section); raises only if there is nothing to write about."""
    parts = spans(duration, chapters)
    if not parts:
        raise ValueError("视频时长未知，无法整理笔记")
    total = len(parts) + 2  # sections, figures, overview
    done = 0

    def step(message: str) -> None:
        nonlocal done
        done += 1
        if progress:
            progress(done, total, message)

    gate = asyncio.Semaphore(PARALLEL)

    async def one(i: int, start: float, end: float, hint: str) -> Section:
        speech, shown = stretch_text(transcript, screen, start, end)
        images = _image_parts(pictures(start, end)) if pictures else []
        if not speech and not shown and not images and not steps_text(steps, start, end):
            step(f"第 {i + 1} 节没有可整理的内容")
            return Section(f"s{i + 1}", hint or f"第 {i + 1} 节", start, end,
                           points=["这一段没有读到语音、画面文字和画面，无法整理。"])
        user = (f"本节时间：{start:.1f}–{end:.1f} 秒（{clock(start)}–{clock(end)}）。"
                + (f"章节标题参考：{hint}\n" if hint else "\n")
                + f"\n【语音转写】\n{speech or '（无）'}\n\n【画面文字】\n{shown or '（无）'}"
                + (f"\n\n【已整理的步骤】\n{cards}" if (cards := steps_text(steps, start, end)) else ""))
        content = [{"type": "text", "text": user}, *images] if images else user
        async with gate:
            try:
                reply = parse_json(await complete([{"role": "system", "content": SECTION_PROMPT},
                                                   {"role": "user", "content": content}]))
            except Exception:  # noqa: BLE001 — one failed section keeps its time range and title
                reply = None
        step(f"已整理第 {i + 1} 节")
        return section_from(reply, f"s{i + 1}", start, end, hint)

    sections = list(await asyncio.gather(*(one(i, a, b, h) for i, (a, b, h) in enumerate(parts))))

    # Frames for the chosen moments, a few at a time (each is one seek into the stream).
    # A section the model gave no usable moment still gets one picture: its middle.
    for s in sections:
        if not s.figures and (s.points or s.formulas):
            s.figures = [Figure(round((s.start + s.end) / 2, 2), s.title)]
    figures = [f for s in sections for f in s.figures]
    frame_gate = asyncio.Semaphore(3)

    async def fill(f: Figure) -> None:
        async with frame_gate:
            try:
                f.src = await grab(f.time) or ""
            except Exception:  # noqa: BLE001 — a figure without a picture is dropped below
                f.src = ""
    await asyncio.gather(*(fill(f) for f in figures))
    for s in sections:
        s.figures = [f for f in s.figures if f.src]
    step(f"配图 {sum(len(s.figures) for s in sections)} 张")

    outline = "\n".join(f"{i + 1}. {s.title}（{clock(s.start)}–{clock(s.end)}）：" + "；".join(s.points[:6])
                        for i, s in enumerate(sections))
    try:
        overview = parse_json(await complete([{"role": "system", "content": OVERVIEW_PROMPT},
                                              {"role": "user", "content": f"视频标题：{title}\n\n各节笔记：\n{outline}"}]))
    except Exception:  # noqa: BLE001 — the note stands without a model-made overview
        overview = None
    step("思维导图")
    note_title = str((overview or {}).get("title") or "").strip()[:40] or title or "视频笔记"
    return {
        "title": note_title,
        "summary": str((overview or {}).get("summary") or "").strip()[:400],
        "video": {"title": title, "duration": duration},
        "sections": [{**asdict(s), "figures": [asdict(f) for f in s.figures]} for s in sections],
        "mindmap": mindmap_from(overview, note_title, sections),
    }
