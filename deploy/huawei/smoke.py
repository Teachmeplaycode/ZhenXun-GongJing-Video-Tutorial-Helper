"""Run against a started cloud service using an explicitly supplied synthetic video."""
import argparse
import json
from pathlib import Path
import time

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("video", type=Path)
parser.add_argument("--base", default="http://127.0.0.1:17080")
args = parser.parse_args()
with httpx.Client(base_url=args.base, timeout=30) as client:
    health = client.get("/api/health")
    health.raise_for_status()
    print("HEALTH", health.json(), flush=True)
    assert client.get("/").status_code == 200
    assert client.get("/api/unknown-smoke-route").status_code == 404
    with args.video.open("rb") as video:
        response = client.post("/api/videos", files={"file": (args.video.name, video, "video/mp4")},
                               data={"task": "合成素材部署验证：红色圆形向右移动，文字 GONGJING TEST 123，测试音无口播。"})
    response.raise_for_status()
    job_id = response.json()["job_id"]
    print("JOB", job_id, flush=True)
    for _ in range(120):
        response = client.get(f"/api/link-jobs/{job_id}")
        response.raise_for_status()
        state = response.json()
        status = {"coverage": state["coverage"], "transcript": state["transcript"], "screentext": state["screentext"]}
        print(json.dumps(status, ensure_ascii=False), flush=True)
        if (not state["running"] and all(state[k]["status"] not in ("pending", "running")
                                        for k in ("transcript", "screentext"))):
            break
        time.sleep(2)
    assert state["coverage"]["ok"] > 0, "no frames decoded"
    first = next(slot for slot in state["slots"] if slot["status"] == "ok")
    frame = client.get(f"/api/link-jobs/{job_id}/frames/{first['index']}.jpg")
    assert frame.status_code == 200 and frame.content.startswith(b"\xff\xd8")
    captions = client.get(f"/api/link-jobs/{job_id}/screentext").json()
    print("CAPTIONS", json.dumps(captions, ensure_ascii=False), flush=True)
    assert captions["status"] == "done" and captions["segments"], "OCR did not produce captions"
    with client.stream("GET", f"/api/link-jobs/{job_id}/events") as events:
        assert events.status_code == 200 and "text/event-stream" in events.headers["content-type"]
        assert any(line.startswith("data:") for line in events.iter_lines()), "no SSE events"
    sessions = client.get("/api/sessions").text
    assert job_id in sessions
    print("PASS: page, API, upload, frames, OCR, SSE and saved session. ASR status above; speech accuracy not tested.", flush=True)
