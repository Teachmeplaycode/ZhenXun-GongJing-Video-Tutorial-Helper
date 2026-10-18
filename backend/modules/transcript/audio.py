"""Read a remote audio-only stream into a 16 kHz mono WAV for speech recognition (no video bytes).

A read the server cut off part-way (ffmpeg exits 0 at a dropped connection) is carried on from where
it stopped, in further reads appended to the WAV, until the whole stated duration is there
(modules/frames/resume.py). If it still falls short the result says how much was read.
"""
from __future__ import annotations

import asyncio
import os
import wave
from pathlib import Path

from ..frames import resume
from ..frames.grabber import GrabResult, classify
from ..video_source import Stream

RATE = 16000  # samples per second, mono, 16-bit


def wav_seconds(path: Path) -> float:
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    except (OSError, wave.Error, EOFError):
        return 0.0


def append_wav(into: Path, part: Path) -> None:
    """Append `part`'s samples to `into` (both 16 kHz mono 16-bit, as ffmpeg wrote them)."""
    with wave.open(str(into)) as a, wave.open(str(part)) as b:
        params = a.getparams()
        head, tail = a.readframes(a.getnframes()), b.readframes(b.getnframes())
    joined = into.with_suffix(".join.wav")
    with wave.open(str(joined), "wb") as w:
        w.setparams(params)
        w.writeframes(head + tail)
    os.replace(joined, into)


async def _ffmpeg(stream: Stream, offset: float, out: Path, timeout: float) -> tuple[int | None, str]:
    """(exit code, stderr) of one read from `offset`; exit code None on timeout."""
    args = ["ffmpeg", "-nostdin", "-hide_banner", *resume.LOG_ARGS, "-y", *resume.seek_args(stream, offset),
            "-vn", "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", str(out)]
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None, ""
    return proc.returncode, stderr.decode(errors="replace")


async def read_audio(stream: Stream, out: Path, timeout: float) -> GrabResult:
    tmp = out.with_suffix(".part.wav")
    piece = out.with_suffix(".piece.wav")
    try:
        try:
            code, text = await _ffmpeg(stream, 0.0, tmp, timeout)
        except FileNotFoundError:
            return GrabResult(False, "error", "未安装 ffmpeg")
        if code is None:
            return GrabResult(False, "timeout", f"超过 {timeout:.0f}s")
        if code != 0 or not tmp.is_file() or tmp.stat().st_size <= 44:  # nothing beyond a WAV header
            return GrabResult(False, classify(text), resume.error_text(text) or f"ffmpeg 退出码 {code}")
        duration = resume.input_duration(text)
        covered = wav_seconds(tmp)
        for _ in range(resume.MAX_RESUMES):
            if not resume.short(covered, duration):
                break
            code, _ = await _ffmpeg(stream, covered, piece, timeout)
            got = wav_seconds(piece) if code == 0 and piece.is_file() else 0.0
            if got < 1:
                break  # no progress: keep what there is rather than loop
            append_wav(tmp, piece)
            covered += got
        os.replace(tmp, out)
        if resume.short(covered, duration):
            return GrabResult(True, "partial", f"只读到 {resume.clock(covered)}（共 {resume.clock(duration)}）")
        return GrabResult(True)
    finally:
        tmp.unlink(missing_ok=True)
        piece.unlink(missing_ok=True)
