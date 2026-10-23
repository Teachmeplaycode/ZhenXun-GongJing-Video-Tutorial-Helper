"""Step cards for a tutorial: the things the viewer has to do, in order, each at its second of the video.

One model call over the timed speech and screen text, asked for one `seconds|action|detail` line per
step. Times outside the video and lines that don't parse are dropped; each step gets the sampled
frame closest to its time, so the card shows the screen at that moment. Built when asked (it costs a
call, and most videos that aren't tutorials have no steps), cached as steps.json in the job folder.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

FILE = "steps.json"
MAX_STEPS = 30
MAX_ACTION = 30
MAX_DETAIL = 60
MAX_CHARS = 14000  # of timed text sent; a long tutorial keeps its lines evenly spread

PROMPT = ("你从软件教程里整理「操作步骤卡」：观看者跟着做时必须亲手完成的操作，按视频里的先后顺序。"
          "每步一行，格式：开始秒数|动作|说明。动作不超过 30 字，以动词开头，写清点哪个菜单、按钮，或输入什么"
          "（例如：点「数据」选项卡里的「数据验证」）；说明不超过 60 字，写这一步要注意的设置或结果，没有就留空。"
          "只依据给出的语音和画面文字，不要编造视频里没有的操作；讲解、闲聊、片头片尾不算步骤。"
          f"最多 {MAX_STEPS} 步。如果这不是教程、没有可以照着做的操作，只输出：无")

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


def timed_lines(transcript, screen) -> list[str]:
    """Speech and on-screen text in time order, `[mm:ss] 说/屏 text`, evenly thinned to MAX_CHARS."""
    rows = [(s.start, "说", s.text) for s in transcript or []] + [(c.start, "屏", c.text) for c in screen or []]
    rows.sort(key=lambda r: r[0])
    lines = [f"[{_clock(t)} · {round(t)}s] {kind}：{text.strip()}" for t, kind, text in rows if text.strip()]
    size = sum(len(x) + 1 for x in lines)
    if size > MAX_CHARS:
        keep = max(1, len(lines) * MAX_CHARS // size)
        lines = [lines[round(i * (len(lines) - 1) / max(1, keep - 1))] for i in range(keep)]
    return lines


def messages(title: str, lines: list[str]) -> list[dict]:
    return [{"role": "system", "content": PROMPT},
            {"role": "user", "content": f"视频标题：{title}\n语音（说）和画面文字（屏），按时间：\n" + "\n".join(lines)}]


# "1. 12|…" / "1、12|…" are numbered; "40.5|…" is a time, not step 40 at 5 s.
LINE = re.compile(r"^\s*(?:\d+(?:[、)]|\.\s)\s*)?(\d+(?:\.\d+)?)\s*s?\s*\|\s*([^|]+?)\s*(?:\|\s*(.*))?$")


def parse(output: str, duration: float) -> list[dict]:
    steps = []
    for line in (output or "").splitlines():
        m = LINE.match(line)
        if not m:
            continue
        t = float(m.group(1))
        if duration and not 0 <= t <= duration:
            continue
        action = m.group(2).strip()[:MAX_ACTION]
        if not action:
            continue
        steps.append({"time": round(t, 1), "action": action, "detail": (m.group(3) or "").strip()[:MAX_DETAIL]})
    return steps[:MAX_STEPS]


def nearest_frame(slots, t: float):
    ok = [s for s in slots if s.status == "ok"]
    return min(ok, key=lambda s: abs(s.time - t)).index if ok else None


async def build(job, complete: Completer) -> dict:
    """Ask, parse, attach frames, cache. A model failure raises; nothing usable is a done empty record."""
    lines = timed_lines(job.transcript.segments if job.transcript else [],
                        job.screentext.segments if job.screentext else [])
    if not lines:
        return save(job.root, {"status": "empty", "steps": [], "message": "这个视频没有语音和画面文字，整理不出步骤"})
    steps = parse(await complete(messages(job.video.title, lines)), job.video.duration or 0)
    for n, step in enumerate(steps, 1):
        step["n"] = n
        step["frame"] = nearest_frame(job.slots, step["time"])
    if not steps:
        return save(job.root, {"status": "empty", "steps": [], "message": "没有找到可以照着做的操作步骤，这可能不是教程"})
    return save(job.root, {"status": "done", "steps": steps, "message": f"{len(steps)} 步"})
