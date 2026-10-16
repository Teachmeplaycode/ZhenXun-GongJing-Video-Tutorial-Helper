"""Replay a short stretch of the video in slow motion: many frames from a few seconds, in one ffmpeg run.

view_frames spreads up to 6 frames over a range with one remote seek per frame. A replay seeks once and
decodes a short clip at a chosen rate (up to MAX_FRAMES frames, e.g. 15 frames in 1 s), so the model can
see how a movement unfolds. Each frame goes to the model as its own image labelled with its time: tiled
into one grid (tried first, 2026-10-16) the model misread the order and missed a cut between two shots.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from pathlib import Path

from .grabber import GrabResult, classify, input_args
from ..video_source import Stream

MAX_SPAN = 10.0     # seconds one replay covers
MAX_FRAMES = 16     # frames per replay (a 4×4 grid)
MAX_FPS = 15.0      # finer than this rarely shows more on 25–30 fps video
WIDTH = 640         # decoded frame width, as the sampled keyframes


@dataclass
class Plan:
    start: float
    end: float
    fps: float
    count: int
    clipped: bool = False  # the asked span was longer than MAX_SPAN

    @property
    def times(self) -> list[float]:
        return [round(self.start + i / self.fps, 2) for i in range(self.count)]

    @property
    def key(self) -> str:
        """Folder name: the same replay asked twice is served from disk."""
        return f"{round(self.start * 100):07d}-{round(self.end * 100):07d}-{round(self.fps * 10):03d}"


def plan(start: float, end: float, duration: float, fps: float | None = None) -> Plan:
    """Clamp a request to the video and the limits; a single moment becomes the second around it."""
    start, end = max(0.0, min(start, duration)), max(0.0, min(end, duration))
    if end < start:
        start, end = end, start
    if end - start < 0.2:
        start, end = max(0.0, start - 0.5), min(duration, start + 0.5)
    clipped = end - start > MAX_SPAN
    if clipped:
        end = start + MAX_SPAN
    span = max(0.2, end - start)
    rate = min(MAX_FPS, MAX_FRAMES / span) if not fps else max(0.5, min(float(fps), MAX_FPS, MAX_FRAMES / span))
    count = max(1, min(MAX_FRAMES, math.floor(span * rate + 1e-6)))
    return Plan(round(start, 2), round(end, 2), round(rate, 2), count, clipped)


async def _ffmpeg(args: list[str], timeout: float) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        return -1, "未安装 ffmpeg"
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -2, f"超过 {timeout:.0f}s"
    return proc.returncode, stderr.decode(errors="replace")


async def grab_clip(stream: Stream, p: Plan, folder: Path, timeout: float = 45) -> GrabResult:
    """Frames 01.jpg… for the plan, decoded from one seek."""
    folder.mkdir(parents=True, exist_ok=True)
    *before, i, url = input_args(stream)
    code, text = await _ffmpeg([
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *before, "-ss", f"{p.start:.3f}", i, url,
        "-t", f"{p.end - p.start + 1 / p.fps:.3f}", "-an", "-vf", f"fps={p.fps},scale='min({WIDTH},iw)':-2",
        "-frames:v", str(p.count), "-q:v", "3", str(folder / "%02d.jpg")], timeout)
    if code == 0 and any(folder.glob("[0-9][0-9].jpg")):
        return GrabResult(True)
    if code == -2:
        return GrabResult(False, "timeout", text)
    detail = " ".join(w for w in text.split() if "://" not in w)[-300:]
    return GrabResult(False, classify(text) if code > 0 else "error", detail)
