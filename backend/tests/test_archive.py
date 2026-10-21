"""Kept uploads move to the bucket (ARCHIVE_DIR) and stay readable through a symlink."""
from modules import archive


def test_an_upload_moves_to_the_archive_and_reads_the_same(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIVE_DIR", str(tmp_path / "bucket"))
    job_dir = tmp_path / "jobs" / "job1"
    job_dir.mkdir(parents=True)
    source = job_dir / "source.mp4"
    source.write_bytes(b"video" * 1000)

    target = archive.keep(source, "job1")
    assert target == tmp_path / "bucket" / "job1" / "source.mp4"
    assert source.is_symlink() and source.read_bytes() == b"video" * 1000
    assert not list(target.parent.glob("*.partial"))
    assert archive.keep(source, "job1") == source  # already archived: nothing to do

    archive.remove_job(job_dir, "source.*")
    assert not target.exists() and not target.parent.exists() and not source.exists()


def test_without_an_archive_uploads_stay_where_they_are(tmp_path, monkeypatch):
    monkeypatch.delenv("ARCHIVE_DIR", raising=False)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"v")
    assert archive.keep(source, "job1") == source and not source.is_symlink()
    archive.unlink(source)
    assert not source.exists()
