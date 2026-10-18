"""Notice when a whole-video read stopped early, so the reader can carry on from there.

A platform's server may drop the connection part-way through a long video (seen on a 42-minute
Bilibili lecture: speech stopped at 8:24, on-screen text at 1:33). ffmpeg treats the dropped
connection as the end of the file and exits 0, so the read looks complete. Readers run ffmpeg at
info level, take the input's duration from its header and how far they got from what they wrote
(or ffmpeg's last progress line), and read the rest with an input seek (-ss) until it is all there.
"""
from __future__ import annotations

import re

from ..video_source import Stream
from .grabber import input_args

MAX_RESUMES = 4      # further reads after the first one stopped short
TOLERANCE = 3.0      # seconds a read may end before the stated duration and still count as complete

DURATION_RE = re.compile(r"Duration: (\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
TIME_RE = re.compile(r"time=(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")

# ffmpeg logging for a resumable read: the header (with Duration) and a progress line every 5 s.
LOG_ARGS = ["-v", "info", "-stats_period", "5"]


def _seconds(m: re.Match) -> float:
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def input_duration(stderr: str) -> float | None:
    """The input's duration from ffmpeg's header, if it stated one."""
    m = DURATION_RE.search(stderr or "")
    return _seconds(m) if m else None


def reached(stderr: str) -> float | None:
    """How far into the input ffmpeg got, from its last progress line."""
    found = list(TIME_RE.finditer(stderr or ""))
    return _seconds(found[-1]) if found else None


def short(covered: float, duration: float | None) -> bool:
    """True when a read ended clearly before the input's end."""
    return bool(duration) and covered < duration - max(TOLERANCE, duration * 0.005)


def error_text(stderr: str) -> str:
    """The stderr of an info-level run without its progress lines and addresses (for error details)."""
    lines = [line for line in (stderr or "").splitlines() if "time=" not in line and "://" not in line]
    return " ".join(" ".join(lines).split())[-300:]


def clock(seconds: float | None) -> str:
    t = max(0, int(seconds or 0))
    return f"{t // 60:02d}:{t % 60:02d}"


def seek_args(stream: Stream, offset: float) -> list[str]:
    """ffmpeg input options that start reading `offset` seconds in (an input seek: no bytes before it)."""
    args = input_args(stream)
    if offset <= 0:
        return args
    i = args.index("-i")
    return [*args[:i], "-ss", f"{offset:.3f}", *args[i:]]
