"""Where an import's transcription spends its time, stage by stage, for the `transcript` log line.

run_transcript sets a fresh dict for the job; the stages it calls (reading the audio, the cloud
recognizer's squeeze / upload / recognize) add their milliseconds to it. A context variable, so
the recognizer's signature stays (path) → segments and concurrent imports don't mix.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar

STAGES: ContextVar[dict | None] = ContextVar("transcript_stages", default=None)


def note(**fields) -> None:
    stages = STAGES.get()
    if stages is not None:
        stages.update(fields)


@contextmanager
def stage(name: str):
    """Adds `<name>_ms` with the wall time of the block."""
    start = time.perf_counter()
    try:
        yield
    finally:
        note(**{f"{name}_ms": round((time.perf_counter() - start) * 1000)})
