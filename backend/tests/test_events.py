import importlib
import json

from fastapi.testclient import TestClient

from modules.frames import FrameJob
from modules.transcript import Transcript
from modules.video_source import ResolvedVideo, Stream


def load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("GONGJING_DATA_DIR", str(tmp_path))  # never touch backend/data
    import app as app_module
    return importlib.reload(app_module)


def test_late_subscriber_gets_every_event_of_a_finished_job(tmp_path, monkeypatch):
    app_module = load_app(tmp_path, monkeypatch)
    v = ResolvedVideo("local", "v", "local://v", "t", 10.0, [Stream("/x.mp4", {}, "s")])
    job = FrameJob("j1", v, None, tmp_path / "jobs" / "j1", count=2)
    job.transcript = Transcript("done", "已转写 1 句")
    # The order a fast job produces: transcript starts first, frames, then both finish.
    for event in ({"type": "transcript", "status": "running"}, {"type": "frame", "index": 0, "time": 2.5},
                  {"type": "frame", "index": 1, "time": 7.5}, {"type": "done", "coverage": {}},
                  {"type": "transcript", "status": "done", "count": 1}):
        job.emit(event)
    app_module.jobs["j1"] = job

    with TestClient(app_module.app) as client:
        body = client.get("/api/link-jobs/j1/events?since=0").text
        types = [json.loads(line[5:])["type"] for line in body.splitlines() if line.startswith("data:")]
        assert types == ["transcript", "frame", "frame", "done", "transcript"]
        # Nothing new after the end: closes at once instead of waiting.
        assert client.get("/api/link-jobs/j1/events?since=5").text == ""
