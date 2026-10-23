"""A daily copy of what can't be rebuilt — the databases (sessions, accounts, spend) and the site's
secret (it signs the visitors' cookies and encrypts their platform logins) — into the COS bucket
(ARCHIVE_DIR/backups/<date>/, Beijing date), the last KEEP_DAYS days kept.

Databases are copied with SQLite's online backup, so a copy is consistent while the site writes.
Frames and transcripts (the job folders) are not copied: they are large and a link can be read again.
Runs at about 04:00 Beijing time, and once at startup when today's copy is missing.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import archive, log

BEIJING = timezone(timedelta(hours=8))
KEEP_DAYS = 14
SECRETS = ("visitor_secret",)
HOUR = 4


def today() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d")


def run(data_root: Path, dest_root: Path, day: str | None = None) -> Path:
    """Copy the databases and secrets of `data_root` into dest_root/<day>/; returns that folder."""
    day = day or today()
    dest = dest_root / day
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    with tempfile.TemporaryDirectory() as tmp:
        for db in sorted(data_root.glob("*.sqlite3")):
            local = Path(tmp) / db.name  # snapshot locally (the bucket mount is no place for SQLite), then upload
            src, out = sqlite3.connect(db), sqlite3.connect(local)
            try:
                src.backup(out)
            finally:
                src.close()
                out.close()
            shutil.copyfile(local, dest / f"{db.name}.partial")
            (dest / f"{db.name}.partial").replace(dest / db.name)
            copied.append(db.name)
    for name in SECRETS:
        if (data_root / name).is_file():
            shutil.copyfile(data_root / name, dest / name)
            os.chmod(dest / name, 0o600)
            copied.append(name)
    (dest / "manifest.json").write_text(json.dumps({"day": day, "at": datetime.now(BEIJING).isoformat(timespec="seconds"), "files": copied},
                                                   ensure_ascii=False))
    prune(dest_root, day)
    return dest


def prune(dest_root: Path, day: str) -> None:
    """Drop backups older than KEEP_DAYS before `day`."""
    cutoff = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for folder in dest_root.iterdir():
        if folder.is_dir() and len(folder.name) == 10 and folder.name < cutoff:
            shutil.rmtree(folder, ignore_errors=True)


def due(dest_root: Path) -> bool:
    return not (dest_root / today() / "manifest.json").is_file()


def seconds_to_next(hour: int = HOUR) -> float:
    now = datetime.now(BEIJING)
    nxt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


async def daily(data_root: Path) -> None:
    """The backup loop (started by the app when there is a bucket)."""
    base = archive.root()
    if base is None:
        return
    dest_root = base / "backups"
    while True:
        try:
            if due(dest_root):
                folder = await asyncio.to_thread(run, data_root, dest_root)
                log.event("backup", folder=str(folder), ok=True)
        except Exception as exc:  # a failed night is logged and tried again the next one
            log.error("backup", exc)
        await asyncio.sleep(seconds_to_next())
