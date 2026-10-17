"""Find the shot changes (cuts) of a whole video, for marks on the timeline.

One ffmpeg pass over a small stream: frames are thinned to SAMPLE_FPS, shrunk, and ffmpeg's scene score
(the difference between consecutive frames, 0–1) picks the jumps above THRESHOLD. A fast pan can score
high too, so cuts closer than MIN_GAP to the previous one are dropped. No model, no OCR; about as fast
as the stream downloads. The result is cached as cuts.json in the job folder:
{"status": "done" | "failed" | "unavailable", "cuts": [seconds, ...], "message": "..."}.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from .grabber import classify, input_args
from ..video_source import Stream

SAMPLE_FPS = 4       # scene scores between frames 0.25 s apart: a cut lands within a quarter second
THRESHOLD = 0.35     # ffmpeg's usual 0.3–0.4: below it lighting changes and motion start to count
MIN_GAP = 1.0        # seconds; a burst of high scores (a flash, a whip pan) counts once
TARGET_HEIGHT = 360  # the smallest stream near this is read
FILE = "cuts.json"

PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


def parse(output: str) -> list[float]:
    """Times from ffmpeg's metadata=print output, thinned to one per MIN_GAP."""
    cuts: list[float] = []
    for t in sorted(float(x) for x in PTS_RE.findall(output)):
        if t < 0.5:  # the first frame always differs from nothing
            continue
        if not cuts or t - cuts[-1] >= MIN_GAP:
            cuts.append(round(t, 2))
    return cuts


def pick_streams(streams: list[Stream]) -> list[Stream]:
    """Readable addresses, the smallest one near TARGET_HEIGHT first."""
    usable = [s for s in streams if not s.expired()]
    return sorted(usable, key=lambda s: abs((s.height or TARGET_HEIGHT) - TARGET_HEIGHT))


async def detect(stream: Stream, folder: Path, timeout: float) -> tuple[list[float] | None, str]:
    """(cuts, "") or (None, why). ffmpeg writes the scene scores to a file in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "scenes.txt"
    out.unlink(missing_ok=True)
    graph = f"fps={SAMPLE_FPS},scale=-2:120,select='gt(scene,{THRESHOLD})',metadata=print:file={out.name}"
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", *input_args(stream), "-an", "-sn",
            "-vf", graph, "-f", "null", "-"]
    try:
        proc = await asyncio.create_subprocess_exec(*args, cwd=folder, stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        return None, "未安装 ffmpeg"
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None, "timeout"
    try:
        if proc.returncode != 0:
            return None, classify(stderr.decode(errors="replace"))
        return parse(out.read_text() if out.is_file() else ""), ""
    finally:
        out.unlink(missing_ok=True)


def load(root: Path) -> dict | None:
    try:
        return json.loads((root / FILE).read_text())
    except (OSError, ValueError):
        return None


def save(root: Path, status: str, cuts: list[float] | None = None, message: str = "") -> dict:
    record = {"status": status, "cuts": cuts or [], "message": message}
    root.mkdir(parents=True, exist_ok=True)
    (root / FILE).write_text(json.dumps(record))
    return record


async def run(root: Path, streams: list[Stream], duration: float, refresh=None) -> dict:
    """Detect, trying each address; `refresh` (async, → new streams) is called once if all are refused."""
    timeout = max(120.0, duration / 2)
    why = "没有可读取的视频地址"
    for attempt in range(2):
        for stream in pick_streams(streams):
            found, why = await detect(stream, root, timeout)
            if found is not None:
                return save(root, "done", found)
            if why != "forbidden":
                break
        if why != "forbidden" or attempt or refresh is None:
            break
        try:
            streams = await refresh()
        except Exception:  # noqa: BLE001 — a failed refresh is just a failed detection
            break
    message = {"forbidden": "视频地址无法访问", "timeout": "读取超时"}.get(why, "镜头切换检测失败")
    return save(root, "failed", message=message)
