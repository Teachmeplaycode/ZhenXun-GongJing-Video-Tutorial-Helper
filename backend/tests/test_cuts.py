"""Shot changes for the timeline's marks, and the slow-motion replay framed by hand on the timeline."""
import asyncio
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from modules.agent.tools import ToolResult
from modules.frames import FrameJob, cuts
from modules.store import SessionStore
from modules.video_source import ResolvedVideo, Stream


def test_parse_keeps_one_cut_per_burst_and_skips_the_first_frame():
    out = "frame:0 pts:0 pts_time:0\nframe:9 pts:2.25 pts_time:2.25\nframe:10 pts_time:2.5\nframe:30 pts_time:7.75\n"
    assert cuts.parse(out) == [2.25, 7.75]  # 2.5 is the same cut (a flash, a whip pan) and 0 is no cut


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_detect_finds_the_cuts_of_a_real_video(tmp_path):
    # 3 s test pattern → 2 s red → 3 s fractal: cuts at 3 s and 5 s, none inside the moving pattern.
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=3",
                    "-f", "lavfi", "-i", "color=c=red:size=320x240:rate=25:duration=2",
                    "-f", "lavfi", "-i", "mandelbrot=size=320x240:rate=25",
                    "-filter_complex", "[2]trim=duration=3,setpts=PTS-STARTPTS[m];[0][1][m]concat=n=3:v=1:a=0", str(clip)],
                   check=True)
    found, why = asyncio.run(cuts.detect(Stream(str(clip), {}, "file"), tmp_path / "work", 60))
    assert why == "" and found == [3.0, 5.0]
    record = asyncio.run(cuts.run(tmp_path / "job", [Stream(str(clip), {}, "file")], 8))
    assert record == {"status": "done", "cuts": [3.0, 5.0], "message": ""} and cuts.load(tmp_path / "job") == record


def test_run_reports_an_unreadable_video(tmp_path):
    record = asyncio.run(cuts.run(tmp_path, [Stream(str(tmp_path / "missing.mp4"), {}, "file")], 8))
    assert record["status"] == "failed" and record["cuts"] == []



def test_a_stalled_detection_tries_the_next_address_and_once_more(tmp_path, monkeypatch):
    monkeypatch.setattr(cuts, "STALL_PAUSE", 0)
    tried = []

    async def detect(stream, folder, timeout):
        tried.append(stream.label)
        return ([4.0, 9.5], "") if len(tried) == 3 else (None, "timeout")
    monkeypatch.setattr(cuts, "detect", detect)
    streams = [Stream("https://a/720", {}, "s720", 720), Stream("https://a/480", {}, "s480", 480)]
    record = asyncio.run(cuts.run(tmp_path, streams, 60))
    assert record["status"] == "done" and record["cuts"] == [4.0, 9.5] and len(tried) == 3

@pytest.fixture
def api(tmp_path, monkeypatch):
    import app

    video = ResolvedVideo("bilibili", "BV1", "u", "t", 300.0, [Stream("https://a/720", {}, "s", 720)])
    job = FrameJob("job1", video, None, tmp_path / "jobs" / "job1", count=2)
    store = SessionStore(tmp_path / "db.sqlite3")
    store.create(job, "https://www.bilibili.com/video/BV1")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "store", store)
    monkeypatch.setitem(app.jobs, "job1", job)
    return app, job, store


def test_cuts_endpoint_serves_the_cache_and_starts_detection_once(api, monkeypatch):
    app, job, _ = api
    started = []

    async def fake(job):
        started.append(job.id)

    monkeypatch.setattr(app, "find_cuts", fake)
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/cuts").json()["status"] == "running"
    assert started == ["job1"]
    cuts.save(job.root, "done", [12.5, 40.0])
    assert client.get("/api/link-jobs/job1/cuts").json() == {"status": "done", "cuts": [12.5, 40.0], "message": ""}
    job.root.joinpath(cuts.FILE).unlink()
    job.video.platform, job.video.streams = "local", []  # an upload deleted after processing: nothing to read
    assert client.get("/api/link-jobs/job1/cuts").json()["status"] == "unavailable"


def test_manual_replay_is_saved_but_kept_out_of_the_models_history(api, monkeypatch):
    app, job, store = api
    asked = []

    async def run(self, name, args):
        asked.append((name, args))
        return ToolResult("复看 01:54.00–01:56.00", "01:54–01:56 · 16 帧", 16,
                          data={"start": 114.0, "end": 116.0, "fps": 8, "times": [114.0], "frames": ["/x/01.jpg"]})

    monkeypatch.setattr(app.AgentTools, "run", run)
    store.add_message("job1", "user", "他拿着什么？")
    store.add_message("job1", "assistant", "一个礼盒。")
    client = TestClient(app.app)
    body = client.post("/api/link-jobs/job1/replay", json={"start": 114, "end": 116}).json()
    assert asked == [("replay", {"start": 114.0, "end": 116.0})]
    assert [e["type"] for e in body["events"]] == ["tool_call.started", "tool_call.input", "tool_call.output", "tool_call.completed"]
    assert body["events"][0]["tool_name"] == "frames.replay" and body["events"][2]["data"]["fps"] == 8
    saved = store.messages("job1")[-1]
    assert saved["role"] == "assistant" and saved["manual"] == "replay" and saved["content"] == ""
    assert store.history("job1") == [{"role": "user", "content": "他拿着什么？"}, {"role": "assistant", "content": "一个礼盒。"}]


def test_manual_replay_reports_an_unreadable_stretch(api, monkeypatch):
    app, _, store = api

    async def run(self, name, args):
        return ToolResult("无法复看 01:54–01:56：这一段读取失败。", "读取失败", error=True)

    monkeypatch.setattr(app.AgentTools, "run", run)
    r = TestClient(app.app).post("/api/link-jobs/job1/replay", json={"start": 114, "end": 116})
    assert r.status_code == 409 and "读取失败" in r.json()["detail"] and store.messages("job1") == []
