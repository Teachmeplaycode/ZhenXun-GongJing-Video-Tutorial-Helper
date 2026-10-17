"""Slow-motion replay: planning, the up-front trigger, the tool, and serving its frames."""
import asyncio
import json

from fastapi.testclient import TestClient

from modules.agent.run import slowmo_ranges
from modules.agent.tools import AgentTools
from modules.frames import FrameJob, GrabResult
from modules.frames import replay as slowmo
from modules.video_source import ResolvedVideo, Stream


def test_plan_fills_the_frame_budget_and_respects_limits():
    p = slowmo.plan(12, 13, 600)
    assert (p.start, p.end, p.fps, p.count) == (12, 13, 15, 15)  # 1 s: capped at 15 fps
    p = slowmo.plan(114, 116, 600)
    assert (p.fps, p.count, p.times[:3]) == (8, 16, [114.0, 114.12, 114.25])
    p = slowmo.plan(10, 40, 600)
    assert p.clipped and p.end == 20 and p.count == 16
    p = slowmo.plan(5, 5, 600)  # one moment: the second around it
    assert (p.start, p.end) == (4.5, 5.5)
    p = slowmo.plan(598, 610, 600)  # past the end
    assert p.end == 600 and p.count <= 16
    assert slowmo.plan(12, 13, 600, fps=4).count == 4


def test_slow_motion_questions_name_their_stretch():
    assert slowmo_ranges("慢放 12 秒到 13 秒") == [("12", "13")]
    assert slowmo_ranges("逐帧看一下 01:05") == [("64.0", "66.0")]
    assert slowmo_ranges("复看 00:30 到 00:32 他做了什么") == [("30.0", "32.0")]
    assert slowmo_ranges("01:05 发生了什么") == []  # not slow motion: the ordinary close look
    assert slowmo_ranges("慢放 01:54.3 到 01:55.8：他拿着什么") == [("114.3", "115.8")]  # framed on the timeline


def job_for(tmp_path, platform="bilibili"):
    v = ResolvedVideo(platform, "BV1", "u", "t", 300.0, [Stream("https://a/720", {}, "s", 720)])
    return FrameJob("job1", v, None, tmp_path / "job1", count=2)


def test_replay_tool_grabs_once_tiles_and_caches(tmp_path, monkeypatch):
    calls = []

    async def grab(stream, p, folder, timeout=45):
        calls.append((p.start, p.end, p.fps))
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, p.count + 1):
            (folder / f"{i:02d}.jpg").write_bytes(b"jpg")
        return GrabResult(True)

    monkeypatch.setattr(slowmo, "grab_clip", grab)
    tools = AgentTools(job_for(tmp_path))
    r = asyncio.run(tools.run("replay", {"start": "01:54", "end": "01:56"}))
    assert not r.error and r.count == 16 and [label for label, _ in r.images[:2]] == ["复看 · 01:54.00", "复看 · 01:54.12"]
    assert r.images[0][1].name == "01.jpg" and "按时间顺序" in r.text
    assert r.data["frames"][0] == "/api/link-jobs/job1/replay/0011400-0011600-080/01.jpg"
    asyncio.run(tools.run("replay", {"start": "114", "end": "116"}))
    assert calls == [(114.0, 116.0, 8.0)]  # the second time comes from disk


def test_replay_explains_a_deleted_upload(tmp_path, monkeypatch):
    async def fail(stream, p, folder, timeout=45):
        return GrabResult(False, "error", "No such file")

    monkeypatch.setattr(slowmo, "grab_clip", fail)
    r = asyncio.run(AgentTools(job_for(tmp_path, "local")).run("replay", {"start": "10", "end": "11"}))
    assert r.error and "原视频已删除" in r.text


def test_replay_frames_are_served_only_from_their_folder(tmp_path, monkeypatch):
    import app

    folder = tmp_path / "jobs" / "job1" / "replay" / "0011400-0011600-080"
    folder.mkdir(parents=True)
    (folder / "01.jpg").write_bytes(b"\xff\xd8jpg")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/replay/0011400-0011600-080/01.jpg").content == b"\xff\xd8jpg"
    assert client.get("/api/link-jobs/job1/replay/..%2F..%2Fx/01.jpg").status_code == 404
    assert client.get("/api/link-jobs/job1/replay/0011400-0011600-080/secret.txt").status_code == 404


def test_extra_frames_are_served_only_from_their_folder(tmp_path, monkeypatch):
    import app

    folder = tmp_path / "jobs" / "job1" / "extra"
    folder.mkdir(parents=True)
    (folder / "00013000.jpg").write_bytes(b"\xff\xd8jpg")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/extra/00013000.jpg").content == b"\xff\xd8jpg"
    assert client.get("/api/link-jobs/job1/extra/..%2Fsecret.jpg").status_code == 404
    assert client.get("/api/link-jobs/job1/extra/00099999.jpg").status_code == 404


def test_a_hand_replay_right_before_the_question_reaches_the_model(tmp_path, monkeypatch):
    """"这个慢放的部分做了什么" after 直接慢放: the model gets that stretch's frames and is told what "这段" is."""
    import httpx
    from tests.test_agent import client_for, collect, make_job, sse_body
    from modules.agent.run import run_agent

    async def grab(stream, p, folder, timeout=45):
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, p.count + 1):
            (folder / f"{i:02d}.jpg").write_bytes(b"\xff\xd8jpg")
        return GrabResult(True)

    monkeypatch.setattr(slowmo, "grab_clip", grab)
    monkeypatch.setenv("LLM_TOOLS", "off")
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, text=sse_body({"choices": [{"delta": {"content": "他在拆礼盒"}, "finish_reason": "stop"}]}))

    job = make_job(tmp_path, ["ok", "ok"])
    events = collect(run_agent(job, client_for(handler), "这个慢放的部分做了什么", framed=[(10.0, 12.0), (54.0, 56.0)]))
    step = [e for e in events if e.get("call_id") == "zoom0" and e["type"] == "tool_call.input"]
    assert len(step) == 1 and step[0]["input"]["params"]["reason"] == "你刚在时间轴上手动慢放了这一段"  # the last one only
    texts = [part["text"] for part in sent[0]["messages"][-1]["content"] if part["type"] == "text"]
    assert any("手动慢放了 00:54.00–00:56.00" in t for t in texts) and texts[-1].endswith("这个慢放的部分做了什么")
    assert sum(part["type"] == "image_url" for part in sent[0]["messages"][-1]["content"]) >= 16

    # A question naming its own stretch keeps it: the hand replay isn't added on top.
    sent.clear()
    events = collect(run_agent(job, client_for(handler), "00:10 到 00:12 出现了什么", framed=[(54.0, 56.0)]))
    assert not any("手动慢放" in part.get("text", "") for part in sent[0]["messages"][-1]["content"])


def test_framed_lists_the_hand_replays_since_the_last_question(tmp_path):
    from modules.store import SessionStore

    store = SessionStore(tmp_path / "db.sqlite3")
    store.create(job_for(tmp_path), "u")

    def hand(a, b):
        store.add_message("job1", "assistant", "", data={"manual": "replay", "events": [
            {"type": "tool_call.output", "call_id": "m", "data": {"start": a, "end": b, "frames": []}}]})

    hand(1.0, 2.0)
    store.add_message("job1", "user", "q")
    store.add_message("job1", "assistant", "a")
    assert store.framed("job1") == []
    hand(54.0, 56.0)
    hand(60.5, 61.5)
    assert store.framed("job1") == [(54.0, 56.0), (60.5, 61.5)]
    store.add_message("job1", "user", "这段做了什么")
    assert store.framed("job1") == []
