"""Image posts and uploaded pictures: fetched whole, text read once per picture, no video steps."""
import asyncio
import io
import json

import cv2
import httpx
import numpy as np
from fastapi.testclient import TestClient

from modules.agent.run import allowed_tools, build_messages, pick_screentext
from modules.frames import FrameJob, cuts, images
from modules.screentext import ocr
from modules.screentext.task import ScreenText
from modules.transcript import Transcript
from modules.video_source import ResolvedVideo


def png(color=(255, 255, 255), size=(2400, 1200)):
    ok, data = cv2.imencode(".png", np.full((size[1], size[0], 3), color, np.uint8))
    return data.tobytes()


def picture_job(tmp_path, items):
    v = ResolvedVideo("redbook", "r1", "https://www.xiaohongshu.com/explore/1", "早餐图集", float(len(items)), [],
                      extra={"kind": "images", "images": items})
    job = FrameJob("job1", v, None, tmp_path / "job1", count=len(items))
    job.transcript, job.screentext = Transcript(), ScreenText()
    return job


def test_pictures_are_fetched_whole_with_their_headers_and_shrunk(tmp_path, monkeypatch):
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("referer")))
        if request.url.path == "/gone.webp":
            return httpx.Response(404)
        return httpx.Response(200, content=png())

    real = httpx.AsyncClient
    monkeypatch.setattr(images.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    local = tmp_path / "shot.png"
    local.write_bytes(png((0, 0, 0), (800, 1600)))
    job = picture_job(tmp_path, [{"url": "https://i/1.webp", "headers": {"Referer": "https://www.xiaohongshu.com/"}},
                                 {"url": "https://i/gone.webp", "headers": {}}, {"path": str(local)}])
    asyncio.run(images.fetch(job))
    assert seen[0] == ("https://i/1.webp", "https://www.xiaohongshu.com/")
    assert [s.status for s in job.slots] == ["ok", "missing", "ok"]
    assert cv2.imread(str(job.frame_path(0))).shape[1] == images.MAX_WIDTH  # wide picture shrunk
    assert cv2.imread(str(job.frame_path(2))).shape[:2] == (1600, 800)       # a long screenshot keeps its height
    assert [e["type"] for e in job.events][0] == "started" and job.events[-1]["type"] == "done"


def test_each_picture_is_read_once_and_its_text_keyed_to_it(tmp_path):
    job = picture_job(tmp_path, [{"path": "a"}, {"path": "b"}, {"path": "c"}])
    for s in job.slots:
        s.status = "ok"
        job.frame_path(s.index).parent.mkdir(parents=True, exist_ok=True)
        job.frame_path(s.index).write_bytes(b"jpg")
    texts = {0: "燕麦 50 克", 1: "", 2: "热量 320 千卡"}
    read = []

    def recognize(path):
        i = int(path.rsplit("/", 1)[1].split(".")[0])
        read.append(i)
        return [ocr.Line(texts[i], 0.9, 0.1, 0.4, 0.8, 0.05)] if texts[i] else []

    asyncio.run(images.read_text(job, recognize))
    assert sorted(read) == [0, 1, 2] and job.screentext.status == "done"
    lines, note = pick_screentext(job, None)
    assert lines == ["[第 1 张] 燕麦 50 克", "[第 3 张] 热量 320 千卡"]
    third = [s for s in job.slots if s.index == 2]
    assert pick_screentext(job, third)[0] == ["[第 3 张] 热量 320 千卡"]  # only that picture's text


def test_the_agent_sees_a_picture_set_and_only_picture_tools(tmp_path):
    job = picture_job(tmp_path, [{"path": "a"}, {"path": "b"}])
    for s in job.slots:
        s.status = "ok"
        job.frame_path(s.index).parent.mkdir(parents=True, exist_ok=True)
        job.frame_path(s.index).write_bytes(b"jpg")
    messages = build_messages(job, job.slots, "这两张图说了什么", [], scope_all=True)
    texts = [p["text"] for p in messages[-1]["content"] if p["type"] == "text"]
    assert texts[0].startswith("图集标题：早餐图集\n共 2 张图片\n这是一组图片") and "第 1 张" in texts and "第 2 张" in texts
    assert not any("时长" in t for t in texts)
    names = {d["function"]["name"] for d in allowed_tools(job, False, False, ())}
    assert names.isdisjoint({"view_frames", "replay", "read_transcript", "read_chapters", "measure_motion"})
    assert "search_transcript" in names


def test_an_image_post_never_starts_the_video_steps(tmp_path, monkeypatch):
    job = picture_job(tmp_path, [{"path": "a"}])

    async def fetch(job, indexes=None):
        job.slots[0].status = "ok"

    async def read_text(job, recognize=None):
        job.screentext.status = "empty"

    monkeypatch.setattr(images, "fetch", fetch)
    monkeypatch.setattr(images, "read_text", read_text)
    asyncio.run(images.process(job))
    assert job.transcript.status == "none" and "没有语音" in job.transcript.message
    assert cuts.load(job.root)["status"] == "unavailable"


def api(tmp_path, monkeypatch):
    import app
    from modules.store import SessionStore
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "store", SessionStore(tmp_path / "db.sqlite3"))
    started = []
    monkeypatch.setattr(app, "spawn", lambda coro: (started.append(coro.__name__), coro.close()))
    return app, started


def test_uploading_pictures_makes_an_image_job(tmp_path, monkeypatch):
    app, started = api(tmp_path, monkeypatch)
    client = TestClient(app.app)
    files = [("files", ("早餐.png", png(), "image/png")), ("files", ("热量.jpg", png(), "image/jpeg"))]
    body = client.post("/api/images", files=files, data={"task": "热量对吗"}).json()
    assert body["video"]["kind"] == "images" and body["video"]["image_count"] == 2 and body["video"]["title"] == "早餐.png 等 2 张图片"
    assert len(body["slots"]) == 2 and started == ["process_images"]
    assert client.post("/api/images", files=[("files", ("x.txt", b"hi", "text/plain"))]).status_code == 422
    chapters = client.get(f"/api/link-jobs/{body['job_id']}/chapters").json()
    assert chapters["status"] == "unavailable"


def test_an_image_post_link_skips_sampling(tmp_path, monkeypatch):
    app, started = api(tmp_path, monkeypatch)
    v = ResolvedVideo("redbook", "r1", "https://www.xiaohongshu.com/explore/1", "早餐", 3.0, [],
                      extra={"kind": "images", "images": [{"url": "https://i/1"}, {"url": "https://i/2"}, {"url": "https://i/3"}]})

    async def resolve(url, part=None):
        return None, v

    monkeypatch.setattr(app.registry, "resolve", resolve)
    body = TestClient(app.app).post("/api/link-jobs", json={"url": "https://www.xiaohongshu.com/explore/1"}).json()
    assert len(body["slots"]) == 3 and started == ["process_images"]  # no sampling, speech, text pass or cuts
