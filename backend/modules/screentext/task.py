"""Read the text on screen across the whole video, once per second, alongside frames and transcript.

The 64 sampled frames show the model only a few percent of a long video's subtitles (one frame per
~31 s on a 33-minute video, subtitles change every 2–3 s). This reads one frame per second with
ffmpeg in a single pass (a 480p stream: 33 minutes in ~45 s), recognizes the text locally and keeps
it as timed captions, which the model gets like the speech transcript. Frames are deleted afterwards.
"""
from __future__ import annotations

import asyncio
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..frames import FrameJob
from ..frames.grabber import GrabResult, classify, input_args
from ..video_source import ResolveError, Stream
from . import ocr
from .merge import Caption, build

FPS = 1
HEIGHT = 540        # frames are scaled to this height for OCR
TARGET_HEIGHT = 480  # preferred stream height: subtitles stay legible, the download stays small
BATCH = 40          # frames recognized per thread hop (progress is reported between batches)

# pending · running · done · empty (no text on screen) · unavailable (no OCR here) · failed
FINISHED = {"done", "empty", "unavailable"}


@dataclass
class ScreenText:
    status: str = "pending"
    message: str = ""
    segments: list[Caption] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.status == "running"

    def summary(self) -> dict:
        return {"status": self.status, "message": self.message, "count": len(self.segments)}

    def as_dict(self) -> dict:
        return {**self.summary(), "segments": [c.as_dict() for c in self.segments]}

    @classmethod
    def from_dict(cls, data: dict | None) -> ScreenText:
        if not data:  # saved before on-screen text existed; a retry fills it in
            return cls("failed", "这个会话创建时还没有画面文字识别，点补抓可以生成")
        segments = [Caption(s["start"], s["end"], s["text"], s.get("pos", "bottom")) for s in data.get("segments") or []]
        status = data.get("status", "pending")
        if status in ("pending", "running"):
            return cls("failed", "识别被中断（后端重启），可以重试", segments)
        return cls(status, data.get("message", ""), segments)


async def read_frames(stream: Stream, folder: Path, timeout: float) -> GrabResult:
    """One pass over the stream, one JPEG per second into `folder` (00001.jpg = 0 s)."""
    folder.mkdir(parents=True, exist_ok=True)
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *input_args(stream), "-an",
            "-vf", f"fps={FPS},scale=-2:{HEIGHT}", "-q:v", "5", str(folder / "%05d.jpg")]
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        return GrabResult(False, "error", "未安装 ffmpeg")
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return GrabResult(False, "timeout", f"超过 {timeout:.0f}s")
    text = stderr.decode(errors="replace")
    if proc.returncode == 0 and any(folder.glob("*.jpg")):
        return GrabResult(True)
    detail = " ".join(w for w in text.split() if "://" not in w)[-300:]
    return GrabResult(False, classify(text), detail or f"ffmpeg 退出码 {proc.returncode}")


def pick_streams(streams: list[Stream]) -> list[Stream]:
    """Readable addresses, the one nearest 480p first (subtitles legible, download small)."""
    usable = [s for s in streams if not s.expired()]
    return sorted(usable, key=lambda s: abs((s.height or TARGET_HEIGHT) - TARGET_HEIGHT))


ReadFrames = Callable[[Stream, Path, float], Awaitable[GrabResult]]
Recognize = Callable[[str], list]


async def run_screentext(job: FrameJob, *, read: ReadFrames = read_frames, recognize: Recognize | None = None) -> None:
    """Fill `job.screentext`; never raises. Emits `screentext` events with status and message."""
    state: ScreenText = job.screentext

    def finish(status: str, message: str = "") -> None:
        state.status, state.message = status, message
        job.emit({"type": "screentext", **state.summary()})

    recognize = recognize or (ocr.recognize if ocr.available() else None)
    if recognize is None:
        return finish("unavailable", "本机不支持画面文字识别（需要 macOS），只看抽样画面")

    state.status, state.segments = "running", []
    job.emit({"type": "screentext", **state.summary(), "message": "正在读取画面"})
    folder = job.root / "screentext"
    timeout = max(120.0, job.video.duration / 2)
    try:
        result = None
        for attempt in range(2):
            for stream in pick_streams(job.video.streams):
                shutil.rmtree(folder, ignore_errors=True)
                result = await read(stream, folder, timeout)
                if result.ok or result.kind != "forbidden":
                    break
            if (result and result.ok) or (result and result.kind != "forbidden") or attempt:
                break
            try:  # every address refused (expired): re-acquire them once
                job.video = await job.resolver.refresh(job.video)
            except ResolveError as exc:
                return finish("failed", f"视频地址获取失败：{exc.message}")
        if result is None or not result.ok:
            reason = {"forbidden": "视频地址无法访问", "timeout": "读取画面超时"}.get(result.kind if result else "", "读取画面失败")
            return finish("failed", reason)

        files = sorted(folder.glob("*.jpg"))
        frames = []
        for i in range(0, len(files), BATCH):
            batch = files[i:i + BATCH]
            lines = await asyncio.to_thread(lambda b=batch: [recognize(str(f)) for f in b])
            frames += [((int(f.stem) - 1) / FPS, found) for f, found in zip(batch, lines)]
            job.emit({"type": "screentext", **state.summary(), "message": f"正在识别文字 {min(i + BATCH, len(files))}/{len(files)}"})
        state.segments = build(frames, 1 / FPS)
        if state.segments:
            finish("done", f"识别到 {len(state.segments)} 段画面文字")
        else:
            finish("empty", "画面上没有识别到文字")
    except Exception as exc:  # decoding / OCR failures are reported, not raised
        return finish("failed", f"画面文字识别失败：{type(exc).__name__}")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
