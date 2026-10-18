"""Keyframes for shots the uniform pass missed: planning, adding slots, and the import flow."""
import asyncio

from modules.frames import FrameJob, GrabResult
from modules.frames.job import shot_fill
from modules.video_source import ResolvedVideo, Stream


def test_every_shot_without_a_frame_gets_its_middle():
    # frames every 10 s; shots 0–12, 12–14.5 (short, no frame), 14.5–15 (a flash), 15–40
    assert shot_fill([12, 14.5, 15], 40, [5, 15.5, 25, 35]) == [13.25]
    assert shot_fill([12, 14.5, 15], 40, [5, 15.5, 25, 35], min_shot=3) == []  # 2.5 s counts as a flash then
    assert shot_fill([], 40, [5]) == []  # one shot, already covered


def test_the_longest_missed_shots_come_first_when_room_runs_out():
    cuts = [1, 3, 10, 12, 30]  # missed shots: 1–3 (2 s), 3–10 (7 s), 10–12 (2 s), 12–30 (18 s)
    assert shot_fill(cuts, 40, [0.5, 35], cap=4) == [6.5, 21.0]
    assert shot_fill(cuts, 40, [0.5, 35], cap=2) == []


def job(tmp_path, n=4, duration=40.0):
    taken = []

    async def grab(stream, t, out):
        taken.append(t)
        out.write_bytes(b"\xff\xd8jpg")
        return GrabResult(True)

    v = ResolvedVideo("bilibili", "BV1", "u", "t", duration, [Stream("https://a/480", {}, "s", 480)])
    return FrameJob("job1", v, None, tmp_path / "job1", count=n, grab=grab), taken


def test_added_slots_keep_old_indexes_and_are_announced(tmp_path):
    j, _ = job(tmp_path)
    assert j.add_slots([13.25, 2.0]) == [4, 5]
    assert [s.index for s in j.slots] == [0, 1, 2, 3, 4, 5]
    assert [s.time for s in j.in_time_order()] == [2.0, 5.0, 13.25, 15.0, 25.0, 35.0]
    assert j.events[-1] == {"seq": 0, "type": "slots", "slots": [
        {"index": 4, "time": 13.25, "status": "pending", "reason": ""}, {"index": 5, "time": 2.0, "status": "pending", "reason": ""}]}


def test_missing_ranges_follow_the_neighbours_in_time(tmp_path):
    j, _ = job(tmp_path)
    j.add_slots([13.25])
    for s in j.slots:
        s.status = "ok"
    j.slots[4].status = "missing"  # 13.25 s, between frames at 5 and 15
    assert j.coverage()["missing_ranges"] == [[9.12, 14.12]]


def test_import_fills_shots_after_the_uniform_pass(tmp_path, monkeypatch):
    import app
    from modules.frames import cuts
    j, taken = job(tmp_path)
    monkeypatch.setattr(app, "sample", lambda job, indexes=None: job.run(indexes))
    cuts.save(j.root, "done", [12, 14.5])
    asyncio.run(app.sample_with_shots(j))
    assert sorted(taken) == [5.0, 13.25, 15.0, 25.0, 35.0]
    assert [e["type"] for e in j.events if e["type"] in ("slots", "done")] == ["done", "slots", "done"]
    assert not j.filling and not app.busy(type("J", (), {"running": False, "filling": False,
                                                          "transcript": type("T", (), {"running": False})(),
                                                          "screentext": type("T", (), {"running": False})()})())
