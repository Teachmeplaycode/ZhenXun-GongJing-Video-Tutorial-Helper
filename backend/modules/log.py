"""Structured logs: one JSON object per line in <data>/logs/YYYY-MM-DD.jsonl, and a short line on the console.

Every record has `ts` (unix seconds), `event` and the event's fields. Events:

- link.resolve   job_id, platform, video_id, duration, ms | ok=false, code
- link.frames    job_id, ok, missing, total, ms
- transcript     job_id, status, segments, ms
- upload         job_id, size, ms
- answer         run_id, job_id, platform, question, status (done/error/stopped), code, elapsed_ms, model,
                 prompt_tokens, completion_tokens, web, papers, tools: [{name, ms, ok, count}]
- account.login  platform, state
- error          where, type, message, trace (unhandled exceptions)

`scripts/log_stats.py` summarizes them. Files older than KEEP_DAYS are deleted on startup.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from datetime import date
from pathlib import Path

KEEP_DAYS = 30
logger = logging.getLogger("gongjing")
_dir: Path | None = None


class DailyJsonl(logging.Handler):
    """Appends each record's JSON to the file for its day (local time)."""

    def __init__(self, folder: Path):
        super().__init__()
        self.folder = folder

    def emit(self, record: logging.LogRecord) -> None:
        try:
            path = self.folder / f"{date.fromtimestamp(record.created).isoformat()}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.payload, ensure_ascii=False, default=str) + "\n")
        except Exception:
            self.handleError(record)


class Console(logging.Handler):
    """`[log] answer done 12.3s 35k→0.8k tokens tools=read_danmaku,read_comments` — enough to follow along."""

    def emit(self, record: logging.LogRecord) -> None:
        p = dict(record.payload)
        p.pop("ts", None)
        kind = p.pop("event")
        bits = []
        for key in ("status", "ok", "state", "code", "platform"):
            if key in p and p[key] not in (None, ""):
                bits.append(f"{key}={p[key]}")
        for key in ("ms", "elapsed_ms"):
            if isinstance(p.get(key), (int, float)):
                bits.append(f"{p[key] / 1000:.1f}s")
        if p.get("prompt_tokens") is not None:
            bits.append(f"{(p['prompt_tokens'] or 0) / 1000:.1f}k→{(p.get('completion_tokens') or 0) / 1000:.1f}k tokens")
        if p.get("tools"):
            bits.append("tools=" + ",".join(t["name"] for t in p["tools"]))
        if p.get("message"):
            bits.append(str(p["message"])[:120])
        sys.stderr.write(f"[log] {kind} {' '.join(bits)}\n")


def setup(folder: Path, console: bool = True) -> None:
    """Idempotent; called once at startup with <data>/logs."""
    global _dir
    folder.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - KEEP_DAYS * 86400
    for old in folder.glob("*.jsonl"):
        if old.stat().st_mtime < cutoff:
            old.unlink(missing_ok=True)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(DailyJsonl(folder))
    if console:
        logger.addHandler(Console())
    _dir = folder


def folder() -> Path | None:
    return _dir


def event(kind: str, **fields) -> None:
    record = logger.makeRecord(logger.name, logging.INFO, "", 0, kind, (), None)
    record.payload = {"ts": round(time.time(), 3), "event": kind, **fields}
    logger.handle(record)


def error(where: str, exc: BaseException, **fields) -> None:
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)[-6:])
    event("error", where=where, type=type(exc).__name__, message=str(exc)[:500], trace=trace, **fields)


class Timer:
    def __init__(self):
        self.start = time.perf_counter()

    @property
    def ms(self) -> int:
        return round((time.perf_counter() - self.start) * 1000)
