"""Sampling presets and overrides chosen on import, and what they change."""
import asyncio
import json

from fastapi.testclient import TestClient

from modules.frames import FrameJob, sampling
from modules.screentext import task as screen
from modules.screentext.task import ScreenText
from modules.video_source import ResolvedVideo, Stream


def test_presets():
    assert sampling.plan({"preset": "standard"}, 300).as_dict() == {"preset": "standard", "frames": 64, "shots": True, "cap": 128, "ocr_fps": 1}
    assert sampling.plan({"preset": "standard"}, 600).ocr_fps == 0.5  # past LONG_VIDEO: every 2 s
    assert sampling.plan({"preset": "quick"}, 600).as_dict() == {"preset": "quick", "frames": 32, "shots": False, "cap": 32, "ocr_fps": 0.5}
    assert sampling.plan({"preset": "fine"}, 2523).as_dict() == {"preset": "fine", "frames": 128, "shots": True, "cap": 256, "ocr_fps": 2}
    assert sampling.plan({"preset": "fine"}, 90).frames == 90  # about one a second


def test_overrides_are_bounded_and_bad_ones_ignored():
    p = sampling.plan({"preset": "standard", "frames": 999, "shots": False, "ocr_fps": 0}, 600)
    assert (p.frames, p.shots, p.cap, p.ocr_fps) == (256, False, 256, 0)
    p = sampling.plan({"preset": "nope", "frames": "x", "shots": "yes", "ocr_fps": 3}, 600)
    assert (p.preset, p.frames, p.shots, p.ocr_fps) == ("standard", 64, True, 0.5)
    assert sampling.plan({"frames": 200}, 600).cap == 200  # never fewer in all than asked for


def video(**extra):
    return ResolvedVideo("bilibili", "BV1", "u", "t", 6.0, [Stream("https://a/480", {}, "s", 480)], extra=extra)


def test_on_screen_text_follows_the_saved_rate_or_is_off(tmp_path):
    asked = []

    async def read(stream, folder, timeout, fps=1):
        asked.append(fps)
        folder.mkdir(parents=True, exist_ok=True)
        return screen.GrabResult(False, "error", "stop here")

    job = FrameJob("j", video(sampling={"ocr_fps": 2}), None, tmp_path / "j", count=2)
    job.screentext = ScreenText()
    asyncio.run(screen.run_screentext(job, read=read, recognize=lambda p: []))
    assert asked == [2.0]

    job = FrameJob("k", video(sampling={"ocr_fps": 0}), None, tmp_path / "k", count=2)
    job.screentext = ScreenText()
    asyncio.run(screen.run_screentext(job, read=read, recognize=lambda p: []))
    assert job.screentext.status == "unavailable" and "关闭" in job.screentext.message and asked == [2.0]


def test_the_import_uses_and_saves_the_plan(tmp_path, monkeypatch):
    import app
    from modules.store import SessionStore

    v = ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "t", 600.0, [Stream("https://a/480", {}, "s", 480)])

    async def resolve(url, part=None):
        return None, v

    started = []
    monkeypatch.setattr(app.registry, "resolve", resolve)
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "store", SessionStore(tmp_path / "db.sqlite3"))
    monkeypatch.setattr(app, "spawn", lambda coro: (started.append(coro.__name__), coro.close()))
    body = TestClient(app.app).post("/api/link-jobs", json={"url": v.canonical_url, "sampling": {"preset": "quick"}}).json()
    assert len(body["slots"]) == 32 and started[0] == "sample"  # quick: no shot fill
    saved = json.loads(app.store.get(body["job_id"])["video"])
    assert saved["extra"]["sampling"]["preset"] == "quick"
