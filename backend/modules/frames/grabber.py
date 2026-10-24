"""Read one frame at a timestamp straight from a remote stream (HTTP range seek, no download)."""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..video_source import Stream

FRAME_WIDTH = 640


@dataclass
class GrabResult:
    ok: bool
    # forbidden: address refused/expired (refresh it) · timeout · error: anything else
    kind: str = ""
    detail: str = ""


# Whole-word status codes only: ffmpeg logs hex addresses such as 0xc50c44000.
REFUSED_RE = re.compile(r"\b(403|404|410)\b|forbidden|not found")


def input_args(stream: Stream) -> list[str]:
    """ffmpeg input options: network ones only for URLs (ffmpeg rejects them for local files)."""
    if "://" not in stream.url:
        return ["-i", stream.url]
    headers = "".join(f"{k}: {v}\r\n" for k, v in stream.headers.items())
    return ["-rw_timeout", "15000000",  # µs without data before giving up on the socket
            "-headers", headers, "-i", stream.url]


def classify(stderr: str) -> str:
    text = stderr.lower()
    if REFUSED_RE.search(text):
        return "forbidden"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "error"


async def grab_frame(stream: Stream, time_sec: float, out: Path, timeout: float = 40, width: int = FRAME_WIDTH) -> GrabResult:
    tmp = out.with_suffix(".part.jpg")
    *before, i, url = input_args(stream)
    args = [
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *before,
        "-ss", f"{max(0.0, time_sec):.3f}", i, url,
        "-frames:v", "1", "-an", "-vf", f"scale='min({width},iw)':-2", "-q:v", "4", str(tmp),
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
    if proc.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 0:
        os.replace(tmp, out)
        return GrabResult(True)
    tmp.unlink(missing_ok=True)
    # Keep signed addresses out of logs and messages.
    detail = " ".join(w for w in text.split() if "://" not in w)[-300:]
    return GrabResult(False, classify(text), detail or f"ffmpeg 退出码 {proc.returncode}")
