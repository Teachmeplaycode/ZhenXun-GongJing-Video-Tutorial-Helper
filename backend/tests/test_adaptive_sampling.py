"""Automatic imports bound long-video work without changing explicit quality settings."""
import asyncio

import pytest

from modules.frames import FrameJob, cuts, sampling
from modules.video_source import ResolvedVideo, Stream


def test_new_imports_default_to_a_bounded_automatic_plan():
    short = sampling.plan(None, 180)
    assert (short.preset, short.frames, short.shots) == ("auto", 48, True)
    for seconds in (600, 1123, 3732, 7200, 36000):
        plan = sampling.plan(None, seconds)
        assert plan.preset == "auto" and plan.frames == 48
        assert plan.shots is False and plan.cap == 48
        assert 0 < plan.ocr_fps * seconds <= 300.01
    assert sampling.plan(None, 86400).ocr_fps >= 1 / 120


def test_auto_custom_overrides_still_win():
    plan = sampling.plan({"preset": "auto", "frames": 100, "shots": True, "ocr_fps": 1}, 3732)
    assert (plan.frames, plan.shots, plan.cap, plan.ocr_fps) == (100, True, 128, 1)
    assert sampling.plan({"preset": "auto", "ocr_fps": 0}, 3732).ocr_fps == 0


@pytest.mark.parametrize("preset", ["quick", "auto"])
def test_disabling_shot_fill_skips_detection_for_every_entry_point(tmp_path, monkeypatch, preset):
    import app
    plan = sampling.plan({"preset": preset}, 3732)
    video = ResolvedVideo("bilibili", "BV1", "url", "lecture", 3732,
                          [Stream("https://source", {}, "s", 480)], extra={"sampling": plan.as_dict()})
    job = FrameJob("adaptive-cut", video, None, tmp_path, count=2)
    started = []

    async def detect(*args, **kwargs):
        started.append(True)
        return cuts.save(job.root, "done", [])

    monkeypatch.setattr(app.cuts, "run", detect)
    asyncio.run(app.find_cuts(job))
    assert started == []
    assert cuts.load(job.root)["status"] == "unavailable"
    assert job.id not in app.cutting


def test_legacy_or_explicit_fine_plan_still_detects_shots(tmp_path, monkeypatch):
    import app
    started = []

    async def detect(root, *args, **kwargs):
        started.append(True)
        return cuts.save(root, "done", [10])

    monkeypatch.setattr(app.cuts, "run", detect)
    for index, extra in enumerate(({}, {"sampling": sampling.plan({"preset": "fine"}, 3732).as_dict()})):
        video = ResolvedVideo("bilibili", "BV1", "url", "lecture", 3732,
                              [Stream("https://source", {}, "s", 480)], extra=extra)
        job = FrameJob(f"legacy-{index}", video, None, tmp_path / str(index), count=2)
        asyncio.run(app.find_cuts(job))
    assert len(started) == 2
