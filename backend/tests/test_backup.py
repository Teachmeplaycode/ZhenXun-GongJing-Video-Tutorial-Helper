"""The daily backup: consistent copies of the databases and the secret, old days dropped."""
import json
import os
import sqlite3

from modules import backup


def test_databases_and_secret_are_copied_consistently(tmp_path):
    data, dest = tmp_path / "data", tmp_path / "bucket" / "backups"
    data.mkdir()
    db = sqlite3.connect(data / "sessions.sqlite3")
    db.execute("CREATE TABLE t (x)")
    db.execute("INSERT INTO t VALUES (42)")
    db.commit()
    open_tx = sqlite3.connect(data / "members.sqlite3")  # a write in progress elsewhere
    open_tx.execute("CREATE TABLE u (y)")
    open_tx.commit()
    open_tx.execute("BEGIN")
    open_tx.execute("INSERT INTO u VALUES (1)")  # not committed: not in the copy
    (data / "visitor_secret").write_bytes(b"k" * 64)
    (data / "jobs").mkdir()  # job folders are not copied

    folder = backup.run(data, dest, day="2026-10-23")
    assert sqlite3.connect(folder / "sessions.sqlite3").execute("SELECT x FROM t").fetchall() == [(42,)]
    assert sqlite3.connect(folder / "members.sqlite3").execute("SELECT y FROM u").fetchall() == []
    assert (folder / "visitor_secret").read_bytes() == b"k" * 64 and os.stat(folder / "visitor_secret").st_mode & 0o077 == 0
    assert json.loads((folder / "manifest.json").read_text())["files"] == ["members.sqlite3", "sessions.sqlite3", "visitor_secret"]
    assert not (folder / "jobs").exists() and not list(folder.glob("*.partial"))
    open_tx.rollback()


def test_old_days_go_and_today_is_not_redone(tmp_path, monkeypatch):
    data, dest = tmp_path / "data", tmp_path / "backups"
    data.mkdir()
    sqlite3.connect(data / "sessions.sqlite3").close()
    for day in ("2026-10-01", "2026-10-09", "2026-10-10"):
        (dest / day).mkdir(parents=True)
    backup.run(data, dest, day="2026-10-23")
    assert sorted(p.name for p in dest.iterdir()) == ["2026-10-09", "2026-10-10", "2026-10-23"]  # 14 days kept
    monkeypatch.setattr(backup, "today", lambda: "2026-10-23")
    assert backup.due(dest) is False
    monkeypatch.setattr(backup, "today", lambda: "2026-10-24")
    assert backup.due(dest) is True
