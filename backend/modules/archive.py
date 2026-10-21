"""Kept uploads in a bucket: ARCHIVE_DIR, e.g. the COS bucket mounted on the server with cosfs.

Once an upload has been read (frames, speech, on-screen text), the video moves to
ARCHIVE_DIR/<job>/source.<ext> and the job folder keeps a symlink to it, so playing it back and
reopening the session work as before while the server's own disk holds only frames and text.
The session database and frames stay on local disk: a bucket mount is slow for many small files
and unsafe for SQLite. Without ARCHIVE_DIR uploads stay in the job folder.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def root() -> Path | None:
    value = os.environ.get("ARCHIVE_DIR", "").strip()
    return Path(value) if value else None


def keep(path: Path, job_id: str) -> Path:
    """Move `path` into the archive and leave a symlink in its place; where it ended up."""
    base = root()
    if base is None or path.is_symlink() or not path.is_file():
        return path
    target = base / job_id / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    shutil.copyfile(path, partial)  # copy, then rename: a cut-off copy never looks complete
    partial.replace(target)
    path.unlink()
    path.symlink_to(target)
    return target


def unlink(path: Path) -> None:
    """Delete a kept upload, the archived file behind a symlink included."""
    if path.is_symlink():
        target = path.resolve()
        path.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        try:
            target.parent.rmdir()
        except OSError:
            pass
    else:
        path.unlink(missing_ok=True)


def remove_job(job_dir: Path, pattern: str) -> None:
    """Before a job folder is deleted: delete what its symlinks point to in the archive."""
    for path in job_dir.glob(pattern):
        unlink(path)
