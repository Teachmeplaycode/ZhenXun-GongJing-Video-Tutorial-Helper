"""Cutting a stretch of the original video out as a GIF or an MP4 — for a reaction image, or to keep
the one step of a tutorial — from the same original the player shows (playback.find): a kept
upload, or the platform's MP4 relayed with its headers.

The stretch is first cut as an MP4 (one quick seek into the original; kept), and a GIF is made from
that local file — reading the remote original straight into the palette filters is many times
slower. A GIF's look is the caller's: frame rate, width, speed, dithering, and an optional size cap
(WeChat won't autoplay a GIF over 1 MB): over the cap, frame rate and width come down step by step.
Every finished file is kept in the job's folder under its settings, so asking again is instant.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

from .frames import FrameJob
from .frames.grabber import input_args
from . import playback

MAX = {"gif": 30.0, "mp4": 60.0}  # seconds a cut may be
MP4_WIDTH = 1280
DITHERS = {"bayer": "dither=bayer:bayer_scale=4", "sierra": "dither=sierra2_4a", "none": "dither=none"}
_slots = asyncio.Semaphore(2)  # cuts at once: ffmpeg on the original is heavy
KEEP_FILES = 40  # cuts kept per video (every look of a GIF is its own file)…
KEEP_BYTES = 200 * 1024 * 1024  # …and at most this much of them: the oldest go first


class ClipError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Look:
    """How a GIF is drawn (an MP4 uses only the speed)."""
    fps: int = 12
    width: int = 480
    speed: float = 1.0
    dither: str = "bayer"
    max_mb: float = 0.0  # 0: no cap

    @staticmethod
    def of(fps: float = 12, width: float = 480, speed: float = 1.0, dither: str = "bayer", max_mb: float = 0.0) -> "Look":
        if dither not in DITHERS:
            raise ClipError(400, "抖动只能是 bayer、sierra 或 none")
        return Look(int(min(30, max(5, fps))), int(min(960, max(160, width)) // 2 * 2), round(min(2.0, max(0.5, speed)), 2),
                    dither, round(min(20.0, max(0.0, max_mb)), 2))

    def key(self) -> str:
        return f"f{self.fps}w{self.width}s{self.speed:g}{self.dither[0]}m{self.max_mb:g}"


@dataclass
class Clip:
    path: Path
    filename: str
    media_type: str
    fps: int = 0  # what the GIF ended up with (lower than asked when it had to fit the size cap)
    width: int = 0
    notes: list[str] = field(default_factory=list)


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


def _cut_args(source: list[str], start: float, end: float, speed: float, out: Path) -> list[str]:
    """The stretch as an MP4 (sound kept; sped up or slowed down when asked)."""
    *before, i, url = source
    video = f"scale='min({MP4_WIDTH},iw)':-2" + (f",setpts=PTS/{speed}" if speed != 1 else "")
    audio = ["-af", f"atempo={speed}"] if speed != 1 else []
    return ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *before, "-ss", f"{start:.3f}", i, url, "-t", f"{end - start:.3f}",
            "-vf", video, *audio, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]


def _gif_args(src: Path, fps: int, width: int, dither: str, out: Path) -> list[str]:
    graph = (f"fps={fps},scale='min({width},iw)':-2:flags=lanczos,split[a][b];"
             f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse={DITHERS[dither]}")
    return ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", "-i", str(src), "-an", "-vf", graph, "-loop", "0", str(out)]


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


async def _cut(job: FrameJob, start: float, end: float, speed: float, out: Path) -> None:
    """Cut the stretch from the original into `out` (MP4)."""
    playable = await playback.find(job)
    if playable is None:
        raise ClipError(404, "原视频不可用（链接已失效或上传的文件已删除），截不了片段")
    source = ["-i", str(playable.path)] if playable.kind == "file" else input_args(playable.stream)
    tmp = out.with_suffix(".part.mp4")
    async with _slots:
        code, _ = await _run(_cut_args(source, start, end, speed, tmp), timeout=40 if playable.kind == "stream" else 150)
        if code != 0 and playable.kind == "stream":  # the platform address may have expired: once more, fresh
            playable = await playback.find(job, fresh=True)
            if playable is not None and playable.stream is not None:
                code, _ = await _run(_cut_args(input_args(playable.stream), start, end, speed, tmp), timeout=150)
    if code != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise ClipError(504 if code == -2 else 502, "截取超时，请截短一点再试" if code == -2 else "截取失败，原视频暂时读不到，请稍后再试")
    tmp.rename(out)


def _trim(folder: Path, keep: set[Path]) -> None:
    """Drop the least recently made cuts beyond the limits (never the ones in `keep`)."""
    files = sorted((p for p in folder.iterdir() if p.suffix in (".gif", ".mp4") and ".part" not in p.name), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    for p in files:
        if len(files) <= KEEP_FILES and total <= KEEP_BYTES:
            break
        if p in keep:
            continue
        total -= p.stat().st_size
        files.remove(p)
        p.unlink(missing_ok=True)
        p.with_suffix(".txt").unlink(missing_ok=True)


async def make(job: FrameJob, start: float, end: float, fmt: str, look: Look | None = None) -> Clip:
    look = look or Look()
    start, end = span(start, end, job.video.duration or 0, fmt)
    folder = job.root / "clips"
    folder.mkdir(parents=True, exist_ok=True)
    name = _name(job.video.title, start, end, fmt)
    mp4 = folder / f"{start:.2f}-{end:.2f}-s{look.speed:g}.mp4"
    if not (mp4.is_file() and mp4.stat().st_size > 0):
        await _cut(job, start, end, look.speed, mp4)
    if fmt == "mp4":
        _trim(folder, {mp4})
        return Clip(mp4, name, "video/mp4")
    out = folder / f"{start:.2f}-{end:.2f}-{look.key()}.gif"
    meta = out.with_suffix(".txt")
    if out.is_file() and out.stat().st_size > 0 and meta.is_file():
        fps, width = (int(x) for x in meta.read_text().split())
        return Clip(out, name, "image/gif", fps, width)
    # Over the size cap: frame rate and width come down together, a few times at most.
    fps, width, notes = look.fps, look.width, []
    tmp = out.with_suffix(".part.gif")
    for _ in range(5):
        async with _slots:
            code, _err = await _run(_gif_args(mp4, fps, width, look.dither, tmp), timeout=90)
        if code != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            raise ClipError(502, "GIF 生成失败，请稍后再试")
        size = tmp.stat().st_size / 1_000_000
        if not look.max_mb or size <= look.max_mb or (fps <= 5 and width <= 160):
            break
        shrink = max(0.55, min(0.9, (look.max_mb / size) ** 0.5))
        fps, width = max(5, int(fps * shrink)), max(160, int(width * shrink) // 2 * 2)
    if fps != look.fps or width != look.width:
        notes.append(f"为了压到 {look.max_mb:g} MB 以内，降到了 {fps} fps、{width} px")
    if look.max_mb and tmp.stat().st_size / 1_000_000 > look.max_mb:
        notes.append(f"已经降到最低还是超过 {look.max_mb:g} MB，可以再截短一点")
    tmp.rename(out)
    meta.write_text(f"{fps} {width}")
    _trim(folder, {mp4, out})
    return Clip(out, name, "image/gif", fps, width, notes)
