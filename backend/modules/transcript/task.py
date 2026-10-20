"""Transcribe a link job's audio track alongside frame sampling; progress goes out as job events."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..frames import FrameJob
from ..video_source import ResolveError, Stream
from . import asr
from .asr import Segment, hallucinated
from .audio import read_audio

# pending · running · done · empty (no speech found) · none (no audio track) · unavailable (no ASR here) · failed
FINISHED = {"done", "empty", "none", "unavailable"}


@dataclass
class Transcript:
    status: str = "pending"
    message: str = ""
    segments: list[Segment] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.status == "running"

    def summary(self) -> dict:
        return {"status": self.status, "message": self.message, "count": len(self.segments)}

    def as_dict(self) -> dict:
        return {**self.summary(), "segments": [s.as_dict() for s in self.segments]}

    @classmethod
    def from_dict(cls, data: dict | None) -> Transcript:
        if not data:  # saved before transcription existed; a retry fills it in
            return cls("failed", "这个会话创建时还没有语音转写，点补抓可以生成")
        # Saved before a phrase joined the hallucination list: drop it on the way in.
        segments = [Segment(s["start"], s["end"], s["text"]) for s in data.get("segments") or [] if not hallucinated(s["text"])]
        status = data.get("status", "pending")
        if status in ("pending", "running"):
            return cls("failed", "转写被中断（后端重启），可以重试", segments)
        return cls(status, data.get("message", ""), segments)


ReadAudio = Callable[[Stream, Path, float], Awaitable]
Transcribe = Callable[[Path], Awaitable[list[Segment]]]


async def run_transcript(job: FrameJob, *, read: ReadAudio = read_audio, transcribe: Transcribe | None = None) -> None:
    """Fill `job.transcript`; never raises. Emits `transcript` events with status and message."""
    state: Transcript = job.transcript

    def finish(status: str, message: str = "") -> None:
        state.status, state.message = status, message
        job.emit({"type": "transcript", **state.summary()})

    transcribe = transcribe or (asr.transcribe if asr.available() else None)
    if transcribe is None:
        return finish("unavailable", "当前环境未安装可用的语音识别引擎，只分析画面")
    if not job.video.audio_streams:
        return finish("none", "该视频没有可读取的音轨，只分析画面")

    state.status, state.segments = "running", []
    job.emit({"type": "transcript", **state.summary(), "message": "正在读取音轨"})
    wav = job.root / "audio.wav"
    timeout = max(90.0, job.video.duration / 4)
    try:
        result = None
        for attempt in range(2):
            for stream in job.video.audio_streams:
                result = await read(stream, wav, timeout)
                if result.ok or result.kind != "forbidden":
                    break
            if result.ok or result.kind != "forbidden" or attempt:
                break
            # Every address refused (expired): re-acquire them once.
            try:
                fresh = await job.resolver.refresh(job.video)
                job.video.audio_streams = fresh.audio_streams
            except ResolveError as exc:
                return finish("failed", f"音轨地址获取失败：{exc.message}")
        if result is None or not result.ok:
            reason = {"forbidden": "音轨地址无法访问", "timeout": "读取音轨超时"}.get(result.kind if result else "", "读取音轨失败")
            return finish("failed", reason)

        job.emit({"type": "transcript", **state.summary(), "message": "正在识别语音"})
        try:
            state.segments = await transcribe(wav)
        except Exception as exc:  # model load / decode failures are reported, not raised
            return finish("failed", f"语音识别失败：{type(exc).__name__}")
        partial = {"partial": f"；{result.detail}，后面没能读取", "gaps": f"；{result.detail}"}.get(result.kind, "")
        if state.segments:
            finish("done", f"已转写 {len(state.segments)} 句{partial}")
        else:
            finish("empty", "没有识别到语音，只分析画面")
    finally:
        wav.unlink(missing_ok=True)
        wav.with_suffix(".part.wav").unlink(missing_ok=True)
