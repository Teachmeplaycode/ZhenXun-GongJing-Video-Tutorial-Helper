"""What the public site spends on paid services each day, and a cap on it.

Every model call (tokens in, cached, out) and every speech transcription (seconds of audio) is
priced and added to today's total (Beijing time, like the accounts' daily allowances). Once the
total reaches DAILY_BUDGET_YUAN, new imports and questions are refused with 「今日额度已满」 until
midnight — except for owner accounts, so a demo still works. Prices are the providers' list prices
by default and can be set:

  LLM_PRICE           yuan per million tokens "in,cached-in,out"  (DeepSeek: 2,0.5,8)
  ASR_PRICE_PER_HOUR  yuan per hour of audio                       (百炼 paraformer-v2: 0.288)
  DAILY_BUDGET_YUAN   the cap; 0 turns it off                      (10)

Only the public site keeps the ledger (visitors on, and the app gave it a place with use()); the
desktop app spends nothing against a cap.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from fastapi import HTTPException

BEIJING = timezone(timedelta(hours=8))
_path: Callable[[], Path] | None = None
_lock = threading.Lock()


def _on() -> bool:
    from . import visitors  # the public site only
    return _path is not None and visitors.enabled()


def use(path: Callable[[], Path]) -> None:
    """Start keeping the ledger in the SQLite file `path()` returns."""
    global _path
    _path = path


def _floats(name: str, default: str) -> list[float]:
    try:
        return [float(x) for x in (os.environ.get(name) or default).split(",")]
    except ValueError:
        return [float(x) for x in default.split(",")]


def budget() -> float:
    return _floats("DAILY_BUDGET_YUAN", "10")[0]


def today() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d")


def _db() -> sqlite3.Connection:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS spend (day TEXT, kind TEXT, yuan REAL, units REAL, n INTEGER, PRIMARY KEY (day, kind))")
    return db


def record(kind: str, yuan: float, units: float = 0) -> None:
    """Add a cost (and its units: tokens, seconds) to today's total for `kind`."""
    if not _on() or yuan <= 0:
        return
    with _lock, _db() as db:
        db.execute("INSERT INTO spend VALUES (?, ?, ?, ?, 1) ON CONFLICT (day, kind) DO UPDATE SET "
                   "yuan = yuan + excluded.yuan, units = units + excluded.units, n = n + 1", (today(), kind, yuan, units))


def llm(prompt: int | None, cached: int | None, completion: int | None) -> None:
    """Price one model call from its token counts."""
    p_in, p_cached, p_out = (_floats("LLM_PRICE", "2,0.5,8") + [0, 0, 0])[:3]
    prompt, cached, completion = prompt or 0, min(cached or 0, prompt or 0), completion or 0
    yuan = ((prompt - cached) * p_in + cached * p_cached + completion * p_out) / 1_000_000
    record("llm", yuan, prompt + completion)


def asr(seconds: float) -> None:
    """Price one transcription from its length."""
    record("asr", seconds / 3600 * _floats("ASR_PRICE_PER_HOUR", "0.288")[0], seconds)


def total(day: str | None = None) -> dict:
    """{yuan, by kind: {yuan, units, calls}} for a day (today by default)."""
    if not _on():
        return {"yuan": 0.0, "kinds": {}}
    with _lock, _db() as db:
        rows = db.execute("SELECT kind, yuan, units, n FROM spend WHERE day = ?", (day or today(),)).fetchall()
    kinds = {k: {"yuan": round(y, 4), "units": u, "calls": n} for k, y, u, n in rows}
    return {"yuan": round(sum(r[1] for r in rows), 4), "kinds": kinds}


def status() -> dict:
    return {"day": today(), "limit": budget(), **total()}


def check() -> None:
    """Refuse new work once today's total has reached the budget (429 budget_exceeded)."""
    cap = budget()
    if not _on() or cap <= 0:
        return
    spent = total()["yuan"]
    if spent >= cap:
        raise HTTPException(429, detail={"code": "budget_exceeded",
                                         "message": "今日额度已满：网站今天的模型费用已到上限，明天 0 点（北京时间）恢复。"})
