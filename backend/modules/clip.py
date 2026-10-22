"""Cutting a stretch of the original video out as a GIF or an MP4 — for a reaction image, or to keep
the one step of a tutorial — from the same original the player shows (playback.find): a kept
upload, or the platform's MP4 relayed with its headers. GIFs are short and small (a palette made
from the clip itself); MP4s keep the sound. A finished cut is kept in the job's folder, so asking
again is instant. A GIF is made from the MP4 of the same stretch (cut first, and kept).
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from .frames import FrameJob
from .frames.grabber import input_args
from . import playback

MAX = {"gif": 10.0, "mp4": 60.0}  # seconds a cut may be
GIF_FPS = 12
GIF_WIDTH = 480
MP4_WIDTH = 1280
_slots = asyncio.Semaphore(2)  # cuts at once: ffmpeg on the original is heavy


class ClipError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Clip:
    path: Path
    filename: str
    media_type: str


def _stamp(t: float) -> str:
    return f"{int(t // 60):02d}{int(t % 60):02d}"


def _name(title: str, start: float, end: float, fmt: str) -> str:
    safe = re.sub(r"[\\/:*?\"<>|\s]+", "_", title or "视频").strip("_")[:40] or "视频"
    return f"帧寻_{safe}_{_stamp(start)}-{_stamp(end)}.{fmt}"


def span(start: float, end: float, duration: float, fmt: str) -> tuple[float, float]:
    """The stretch clamped to the video and to the format's limit (a GIF is at most MAX['gif'] s)."""
    if fmt not in MAX:
        raise ClipError(400, "格式只能是 gif 或 mp4")
    if duration > 0:
        start, end = max(0.0, min(start, duration)), max(0.0, min(end, duration))
    if end < start:
        start, end = end, start
    if end - start < 0.3:
        raise ClipError(400, "片段太短，至少 0.3 秒")
    return round(start, 2), round(min(end, start + MAX[fmt]), 2)


def _args(source: list[str], start: float, end: float, fmt: str, out: Path) -> list[str]:
    *before, i, url = source
    head = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *before, "-ss", f"{start:.3f}", i, url, "-t", f"{end - start:.3f}"]
    if fmt == "gif":
        graph = (f"fps={GIF_FPS},scale='min({GIF_WIDTH},iw)':-2:flags=lanczos,split[a][b];"
                 "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
        return [*head, "-an", "-vf", graph, "-loop", "0", str(out)]
    return [*head, "-vf", f"scale='min({MP4_WIDTH},iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]


async def _run(args: list[str], timeout: float) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        return -1, "未安装 ffmpeg"
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -2, "timeout"
    return proc.returncode, err.decode(errors="replace")


async def make(job: FrameJob, start: float, end: float, fmt: str) -> Clip:
    start, end = span(start, end, job.video.duration or 0, fmt)
    folder = job.root / "clips"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{start:.2f}-{end:.2f}.{fmt}"
    clip = Clip(out, _name(job.video.title, start, end, fmt), "image/gif" if fmt == "gif" else "video/mp4")
    if out.is_file() and out.stat().st_size > 0:
        return clip
    if fmt == "gif":
        # Cut the stretch as an MP4 first (one quick seek into the original, and kept), then make the
        # GIF from that local file: reading the remote original straight into the palette filters is
        # many times slower.
        mp4 = await make(job, start, end, "mp4")
        tmp = out.with_suffix(".part.gif")
        async with _slots:
            code, _ = await _run(_args(["-i", str(mp4.path)], 0, end - start, "gif", tmp), timeout=60)
        if code != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            raise ClipError(502, "GIF 生成失败，请稍后再试")
        tmp.rename(out)
        return clip
    playable = await playback.find(job)
    if playable is None:
        raise ClipError(404, "原视频不可用（链接已失效或上传的文件已删除），截不了片段")
    source = ["-i", str(playable.path)] if playable.kind == "file" else input_args(playable.stream)
    tmp = out.with_suffix(f".part.{fmt}")
    async with _slots:
        code, err = await _run(_args(source, start, end, fmt, tmp), timeout=40 if playable.kind == "stream" else 150)
        if code != 0 and playable.kind == "stream":  # the platform address may have expired: once more, fresh
            playable = await playback.find(job, fresh=True)
            if playable is not None and playable.stream is not None:
                code, err = await _run(_args(input_args(playable.stream), start, end, fmt, tmp), timeout=150)
    if code != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise ClipError(504 if code == -2 else 502, "截取超时，请截短一点再试" if code == -2 else "截取失败，原视频暂时读不到，请稍后再试")
    tmp.rename(out)
    return clip
