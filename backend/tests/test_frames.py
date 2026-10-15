import asyncio
from pathlib import Path

from modules.frames import FrameJob, GrabResult, coarse_first, frame_count
from modules.video_source import ResolveError, ResolvedVideo, Resolver, Stream


def video(streams=("https://a", "https://b"), duration=100.0, playable=None):
    return ResolvedVideo("test", "v1", "https://x/v1", "t", duration,
                         [Stream(u, {}, f"s{i}") for i, u in enumerate(streams)], playable_duration=playable)


class FakeResolver(Resolver):
    platform = "test"

    def __init__(self, fresh=("https://fresh",), fallback=(), fail=False):
        self.fresh, self.fallback, self.fail, self.refreshes = fresh, fallback, fail, 0

    async def refresh(self, v):
        self.refreshes += 1
        if self.fail:
            raise ResolveError("x", "失败")
        return video(self.fresh, v.duration, v.playable_duration)

    async def fallback_streams(self, v):
        return [Stream(u, {}, "fb") for u in self.fallback]


def grabber(rule):
    """rule(url, t) -> GrabResult; writes a dummy jpg on success."""
    async def grab(stream, t, out: Path):
        result = rule(stream.url, t)
        if result.ok:
            out.write_bytes(b"jpg")
        return result
    return grab


def run_job(tmp_path, v, resolver, rule, count=8):
    job = FrameJob("j", v, resolver, tmp_path, count=count, grab=grabber(rule))
    asyncio.run(job.run())
    return job


def test_frame_count_and_coarse_order():
    assert frame_count(30) == 48 and frame_count(100) == 50 and frame_count(3600) == 64
    order = coarse_first(64)
    assert sorted(order) == list(range(64))
    assert order[:16] == list(range(0, 64, 4))  # first 16 spread across the whole video


def test_all_frames_ok(tmp_path):
    job = run_job(tmp_path, video(), FakeResolver(), lambda u, t: GrabResult(True))
    assert job.coverage()["ok"] == 8 and job.events[-1]["type"] == "done"
    assert all(job.frame_path(i).is_file() for i in range(8))


def test_backup_address_used_when_primary_refuses(tmp_path):
    job = run_job(tmp_path, video(), FakeResolver(), lambda u, t: GrabResult(u == "https://b", "forbidden"))
    assert job.coverage()["ok"] == 8


def test_partial_failure_reports_ranges_instead_of_failing(tmp_path):
    # Seconds 40–70 unreadable on every address: decode error, no refresh.
    resolver = FakeResolver()
    job = run_job(tmp_path, video(), resolver, lambda u, t: GrabResult(not (40 <= t <= 70), "error"), count=10)
    cov = job.coverage()
    assert cov["ok"] == 7 and cov["missing"] == 3 and cov["pending"] == 0
    assert cov["missing_ranges"] == [[40.0, 70.0]]
    assert resolver.refreshes == 0
    assert {e["type"] for e in job.events} >= {"frame", "missing", "done"}


def test_expired_addresses_are_refreshed_once_for_all_slots(tmp_path):
    resolver = FakeResolver(fresh=("https://fresh",))
    job = run_job(tmp_path, video(), resolver, lambda u, t: GrabResult(u == "https://fresh", "forbidden"))
    assert job.coverage()["ok"] == 8
    assert resolver.refreshes == 1


def test_fallback_after_refresh_fails(tmp_path):
    resolver = FakeResolver(fail=True, fallback=("https://h5",))
    job = run_job(tmp_path, video(), resolver, lambda u, t: GrabResult(u == "https://h5", "forbidden"))
    assert job.coverage()["ok"] == 8
    assert any(e.get("message") == "已切换到备用播放地址" for e in job.events)


def test_everything_unreachable_still_completes(tmp_path):
    resolver = FakeResolver(fresh=("https://dead",))
    job = run_job(tmp_path, video(), resolver, lambda u, t: GrabResult(False, "forbidden"))
    cov = job.coverage()
    assert cov["ok"] == 0 and cov["missing"] == 8 and cov["reasons"] == {"unreachable": 8}
    assert resolver.refreshes == 2  # bounded


def test_trial_limit_marks_tail_missing(tmp_path):
    job = run_job(tmp_path, video(playable=50), FakeResolver(), lambda u, t: GrabResult(True))
    cov = job.coverage()
    assert cov["reasons"] == {"trial": 4} and cov["ok"] == 4


def test_retry_only_missing(tmp_path):
    state = {"broken": True}
    job = FrameJob("j", video(), FakeResolver(), tmp_path, count=6,
                   grab=grabber(lambda u, t: GrabResult(not (state["broken"] and t > 50), "error")))
    asyncio.run(job.run())
    assert job.coverage()["missing"] == 3
    state["broken"] = False
    indexes = asyncio.run(job.retry_missing())
    assert indexes == [3, 4, 5]
    asyncio.run(job.run(indexes))
    assert job.coverage()["ok"] == 6


def test_last_frame_steps_back_when_stream_is_shorter_than_nominal(tmp_path):
    # Nominal 21 s, real stream ends at 20.33 s.
    job = run_job(tmp_path, video(duration=21.0), FakeResolver(), lambda u, t: GrabResult(t < 20.33, "error"), count=16)
    assert job.coverage()["ok"] == 16
    last = job.slots[-1]
    assert last.time < 20.33 and any(e["type"] == "frame" and e["index"] == 15 and e["time"] == last.time for e in job.events)


def test_decode_error_mid_video_does_not_step_back(tmp_path):
    job = run_job(tmp_path, video(duration=100.0), FakeResolver(), lambda u, t: GrabResult(not 40 < t < 50, "error"), count=10)
    assert [s.time for s in job.slots if s.status == "missing"] == [45.0]
