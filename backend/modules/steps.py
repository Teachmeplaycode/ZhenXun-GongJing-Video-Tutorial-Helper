"""Step cards for a tutorial: the things the viewer has to do, in order, each at its second of the video.

One model call over the timed speech and screen text, asked for one `seconds|action|detail` line per
step. Times outside the video and lines that don't parse are dropped; each step gets the sampled
frame closest to its time, and — when a sharper read is possible — its own picture at that second, wider
than the 640 px keyframes (steps/<n>.jpg), so small print on the card can be read. Built when asked (it
costs a call, and most videos that aren't tutorials have no steps), cached as steps.json in the job folder.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

FILE = "steps.json"
ROUNDS = 6  # calls at most: a reply that stops short of the end (or is cut by length) is followed on from there
MAX_ACTION = 48  # the prompt asks for 30 characters; a longer line is kept whole up to here, not cut mid-word
MAX_DETAIL = 80
SHOT_WIDTH = 1600  # a step's own picture
SHOTS = "steps"  # its folder in the job
MAX_CHARS = 14000  # of timed text sent; a long tutorial keeps its lines evenly spread

PROMPT = ("你从软件教程里整理「操作步骤卡」：观看者跟着做时必须亲手完成的操作，按视频里的先后顺序。"
          "每步一行，格式：时间|动作|说明。时间写成 mm:ss，照抄材料里讲到或演示这个操作的那一行的时间，不要写步骤序号。动作不超过 30 字，以动词开头，写清点哪个菜单、按钮，或输入什么"
          "（例如：点「数据」选项卡里的「数据验证」）；说明不超过 60 字，写这一步要注意的设置或结果，没有就留空。"
          "只依据给出的语音和画面文字，不要编造视频里没有的操作；闲聊、片头片尾不算步骤。"
          "只要视频在演示怎么操作软件、设备或做出某个东西，就算教程，边讲边做的操作都要列出来。"
          "{span}如果这不是教程、没有可以照着做的操作，只输出：无")

SPAN = "视频全长 {end}，步骤不限数量，要从开头一直整理到结尾，不要中途停下。"
TAIL = "前面已整理到 {start}，这里只给 {start} 之后的材料，接着往下整理到结尾，只列 {start} 之后的步骤。"
# A reply whose last step falls this far short of the end is followed on from that step.
SHORT_OF_END = 0.15

Completer = Callable[[list[dict]], Awaitable[str]]


def load(root: Path) -> dict | None:
    try:
        return json.loads((root / FILE).read_text())
    except (OSError, ValueError):
        return None


def save(root: Path, record: dict) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / FILE).write_text(json.dumps(record, ensure_ascii=False))
    return record


def _clock(t: float) -> str:
    t = int(max(0, t))
    return f"{t // 60:02d}:{t % 60:02d}"


def timed_lines(transcript, screen, after: float = -1) -> list[str]:
    """Speech and on-screen text (past `after` seconds) in time order, `[mm:ss] 说/屏 text`, evenly
    thinned to MAX_CHARS."""
    rows = [(s.start, "说", s.text) for s in transcript or []] + [(c.start, "屏", c.text) for c in screen or []]
    rows = [r for r in rows if r[0] > after]
    rows.sort(key=lambda r: r[0])
    lines = [f"[{_clock(t)} · {round(t)}s] {kind}：{text.strip()}" for t, kind, text in rows
             if text.strip() and not NUMBERS_ONLY.match(text)]
    size = sum(len(x) + 1 for x in lines)
    if size > MAX_CHARS:
        keep = max(1, len(lines) * MAX_CHARS // size)
        lines = [lines[round(i * (len(lines) - 1) / max(1, keep - 1))] for i in range(keep)]
    return lines


def messages(title: str, lines: list[str], duration: float = 0, after: float = 0) -> list[dict]:
    span = (TAIL.format(start=_clock(after)) if after else "") + (SPAN.format(end=_clock(duration)) if duration else "")
    return [{"role": "system", "content": PROMPT.format(span=span)},
            {"role": "user", "content": f"视频标题：{title}\n语音（说）和画面文字（屏），按时间：\n" + "\n".join(lines)}]


# "1. 12|…" / "1、12|…" are numbered; "40.5|…" is a time, not step 40 at 5 s.
# Seconds as asked, or the mm:ss the lines show (models write either).
LINE = re.compile(r"^\s*(?:\d+(?:[、)]|\.\s)\s*)?(\d+:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*s?\s*\|\s*([^|]+?)\s*(?:\|\s*(.*))?$")
NUMBERS_ONLY = re.compile(r"^[\d\s.,:%+\-/()¥$]*$")  # a spreadsheet's cells read off the screen


def seconds(text: str) -> float:
    t = 0.0
    for part in text.split(":"):
        t = t * 60 + float(part)
    return t


# What models put around the line the format asks for: bold, bullets, 「第 3 步：」, a bracketed time,
# a full-width bar, "00:56 - 动作" without bars.
DECOR = re.compile(r"^\s*(?:[-*•>]\s*)?(?:第\s*\d+\s*步\s*[:：.、]?\s*|步骤\s*\d+\s*[:：.、]?\s*)?")
LOOSE = re.compile(r"^\s*(\d+:\d{2}(?::\d{2})?)\s*[-—–:：]\s*(.+)$")


def tidy(line: str) -> str:
    line = line.replace("｜", "|").replace("**", "").replace("`", "")
    line = DECOR.sub("", line)
    line = re.sub(r"^\s*[\[【(（]\s*(\d+:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*s?\s*[\]】)）]\s*\|?", r"\1|", line)
    if "|" not in line and (m := LOOSE.match(line)):
        line = f"{m.group(1)}|{m.group(2)}"
    return line


def parse(output: str, duration: float) -> list[dict]:
    matches = [m for m in map(LINE.match, map(tidy, (output or "").splitlines())) if m]
    # "18:00" or "21:21" for the 18th / 21st second (the lines show both "[00:21 · 21s]"): read as minutes
    # most times run past the end, while the number before the colon always fits in the video.
    raw = [m.group(1) for m in matches]
    clocks = [r for r in raw if r.count(":") == 1]
    as_seconds = bool(duration and raw and len(clocks) == len(raw)
                      and sum(seconds(r) > duration for r in raw) * 2 >= len(raw)
                      and duration >= max(int(r.split(":")[0]) for r in raw))
    steps = []
    for m in matches:
        t = float(m.group(1).split(":")[0]) if as_seconds else seconds(m.group(1))
        if duration and not 0 <= t <= duration:
            continue
        action = m.group(2).strip()[:MAX_ACTION]
        if not action:
            continue
        steps.append({"time": round(t, 1), "action": action, "detail": (m.group(3) or "").strip()[:MAX_DETAIL]})
    if len(steps) >= 3 and [s["time"] for s in steps] == [float(i) for i in range(1, len(steps) + 1)]:
        return []  # step numbers written where the times go: no time can be trusted
    return steps


async def _rest(job, complete: Completer, after: float, duration: float) -> list[dict]:
    """The steps past `after`, asked for on their own. A failed call keeps what the earlier ones found."""
    lines = timed_lines(job.transcript.segments if job.transcript else [],
                        job.screentext.segments if job.screentext else [], after)
    if not lines:
        return []
    try:
        output = await complete(messages(job.video.title, lines, duration, after))
    except Exception:  # noqa: BLE001
        return []
    return [s for s in parse(output, duration) if s["time"] > after]


def nearest_frame(slots, t: float):
    ok = [s for s in slots if s.status == "ok"]
    return min(ok, key=lambda s: abs(s.time - t)).index if ok else None


Sharp = Callable[[float, Path, int], Awaitable[bool]]  # (second, file, width) → read? (AgentTools.sharp)


def shot_path(root: Path, n: int) -> Path:
    return root / SHOTS / f"{n:02d}.jpg"


async def take_shots(root: Path, steps: list[dict], sharp: Sharp, at_once: int = 4) -> None:
    """Each step's own picture at its second, wider than the keyframes; `shot` marks the ones that came."""
    import asyncio

    (root / SHOTS).mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(at_once)

    async def one(step):
        async with gate:
            try:
                step["shot"] = bool(await sharp(step["time"], shot_path(root, step["n"]), SHOT_WIDTH))
            except Exception:  # noqa: BLE001 — the keyframe still shows
                step["shot"] = False

    await asyncio.gather(*(one(s) for s in steps))


async def build(job, complete: Completer, sharp: Sharp | None = None) -> dict:
    """Ask, parse, attach frames (and, with `sharp`, each step's own sharper picture), cache. A model
    failure raises; nothing usable is a done empty record."""
    lines = timed_lines(job.transcript.segments if job.transcript else [],
                        job.screentext.segments if job.screentext else [])
    if not lines:
        return save(job.root, {"status": "empty", "steps": [], "message": "这个视频没有语音和画面文字，整理不出步骤"})
    duration = job.video.duration or 0
    output = await complete(messages(job.video.title, lines, duration))
    steps = parse(output, duration)
    if not steps and output.strip() not in ("无", ""):
        from modules import log  # a reply in a shape parse doesn't know: keep its start to see why
        log.event("steps.unparsed", job_id=job.id, head=output.strip()[:300])
    for _ in range(ROUNDS - 1):
        reached = max((s["time"] for s in steps), default=0)
        if not steps or not duration or reached >= duration * (1 - SHORT_OF_END):
            break
        if not (more := await _rest(job, complete, reached, duration)):
            break
        steps += more
    for n, step in enumerate(steps, 1):
        step["n"] = n
        step["frame"] = nearest_frame(job.slots, step["time"])
    if not steps:
        return save(job.root, {"status": "empty", "steps": [], "message": "没有找到可以照着做的操作步骤，这可能不是教程"})
    if sharp is not None:
        await take_shots(job.root, steps, sharp)
    return save(job.root, {"status": "done", "steps": steps, "message": f"{len(steps)} 步"})
