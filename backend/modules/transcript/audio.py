"""Read a remote audio-only stream into a 16 kHz mono WAV for speech recognition (no video bytes)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from ..frames.grabber import GrabResult, classify, input_args
from ..video_source import Stream


async def read_audio(stream: Stream, out: Path, timeout: float) -> GrabResult:
    tmp = out.with_suffix(".part.wav")
    args = [
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *input_args(stream),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(tmp),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        return GrabResult(False, "error", "未安装 ffmpeg")
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        tmp.unlink(missing_ok=True)
        return GrabResult(False, "timeout", f"超过 {timeout:.0f}s")
    text = stderr.decode(errors="replace")
    if proc.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 44:  # more than a WAV header
        os.replace(tmp, out)
        return GrabResult(True)
    tmp.unlink(missing_ok=True)
    detail = " ".join(w for w in text.split() if "://" not in w)[-300:]
    return GrabResult(False, classify(text), detail or f"ffmpeg 退出码 {proc.returncode}")
