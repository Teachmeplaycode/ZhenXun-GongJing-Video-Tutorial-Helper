"""Playing the original: the three evidence states, kept uploads, and the relay of platform videos."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from modules import playback
from modules.frames import FrameJob
from modules.store import SessionStore
from modules.video_source import ResolvedVideo, Stream
from modules.video_source.base import Resolver

BODY = bytes(range(256)) * 400  # 102 400 bytes of "video"


class Platform(Resolver):
    """A platform whose addresses expire: the first one is refused, a refreshed one plays."""
    platform = "douyin"

    def __init__(self):
        self.refreshed = 0

    async def refresh(self, video):
        self.refreshed += 1
        fresh = Stream(f"https://cdn.example/v{self.refreshed}.mp4", {"Referer": "https://douyin.com/"}, "mp4")
        video.streams, video.audio_streams = [fresh], [fresh]
        return video


def job_for(tmp_path, platform="douyin", streams=None, ok=True, kind=None):
    s = streams if streams is not None else [Stream("https://cdn.example/v0.mp4", {"Referer": "https://douyin.com/"}, "mp4")]
    video = ResolvedVideo(platform, "v", "https://douyin.com/v", "t", 60.0, s, audio_streams=list(s),
                          extra={"kind": kind} if kind else {})
    job = FrameJob("job1", video, Platform(), tmp_path / "jobs" / "job1", count=2)
    if ok:
        job.slots[0].status = "ok"
    playback.forget("job1")
    return job


def test_the_three_states(tmp_path):
    upload = tmp_path / "source.mp4"
    upload.write_bytes(BODY)
    assert asyncio.run(playback.state(job_for(tmp_path, "local", [Stream(str(upload), {}, "local-file")])))["state"] == "original"
    gone = job_for(tmp_path, "local", [Stream(str(tmp_path / "deleted.mp4"), {}, "local-file")])
    cache = asyncio.run(playback.state(gone))
    assert cache["state"] == "cache" and "已删除" in cache["message"]
    assert asyncio.run(playback.state(job_for(tmp_path, "local", [], ok=False)))["state"] == "none"
    assert asyncio.run(playback.state(job_for(tmp_path, kind="images")))["state"] == "cache"  # pictures have their own viewer
    assert asyncio.run(playback.state(job_for(tmp_path)))["state"] == "original"  # a combined (picture + sound) stream


def test_bilibili_plays_its_html5_mp4_not_the_silent_dash_track(tmp_path):
    class Bili(Resolver):
        platform = "bilibili"

        async def play_streams(self, video):
            return [Stream("https://upos.example/html5-1080p.mp4", {}, "html5-mp4-hd")]

        async def fallback_streams(self, video):
            return [Stream("https://upos.example/html5.mp4", {}, "html5-mp4")]
    dash = [Stream("https://upos.example/dash-video.m4s", {}, "dash-avc-720p")]
    job = job_for(tmp_path, "bilibili", dash)
    job.video.audio_streams = [Stream("https://upos.example/dash-audio.m4s", {}, "audio")]
    job.resolver = Bili()
    found = asyncio.run(playback.find(job))
    assert found.kind == "stream" and found.stream.url.endswith("html5-1080p.mp4")  # the HD MP4, with sound


def test_span_reads_the_bytes_a_body_covers():
    assert playback.span("bytes 100-199/1000", "100") == (100, 199)
    assert playback.span(None, "1000") == (0, 999)
    assert playback.span(None, None) == (0, None)


@pytest.fixture
def api(tmp_path, monkeypatch):
    import app

    store = SessionStore(tmp_path / "db.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "store", store)
    return app, store


def cdn(monkeypatch, cut_first=False, refuse=("v0.mp4",)):
    """A fake CDN behind the relay: checks the Referer, honours Range, can refuse or cut a body short."""
    seen = []

    def handler(request):
        seen.append((request.url.path, request.headers.get("range")))
        if request.headers.get("referer") != "https://douyin.com/":
            return httpx.Response(403)
        if any(request.url.path.endswith(r) for r in refuse):
            return httpx.Response(403)
        first, last = 0, len(BODY) - 1
        if request.headers.get("range"):
            a, b = request.headers["range"].split("=")[1].split("-")
            first, last = int(a), int(b or last)
        part = BODY[first:last + 1]
        headers = {"content-type": "video/mp4", "content-range": f"bytes {first}-{last}/{len(BODY)}"}
        if cut_first and len(seen) == 1:  # the first body stops after 30 000 bytes
            return httpx.Response(206, headers=headers, stream=Broken(part[:30000]))
        return httpx.Response(206, headers=headers, content=part)

    real = httpx.AsyncClient
    monkeypatch.setattr(playback, "_http", {})  # the shared pools are built from the patched client

    def client(*args, **kwargs):
        kwargs.pop("follow_redirects", None)
        return real(transport=httpx.MockTransport(handler), follow_redirects=True, **{k: v for k, v in kwargs.items() if k == "timeout"})
    monkeypatch.setattr(httpx, "AsyncClient", client)
    return seen


class Broken(httpx.AsyncByteStream):
    """A body that stops part-way, as a CDN dropping the connection does."""

    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        yield self.data
        raise httpx.RemoteProtocolError("peer closed connection without sending complete message body")


def test_a_platform_video_is_relayed_with_its_headers_and_an_expired_address_renewed(api, tmp_path, monkeypatch):
    app, _ = api
    job = job_for(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)
    seen = cdn(monkeypatch)
    r = TestClient(app.app).get("/api/link-jobs/job1/media", headers={"Range": "bytes=1000-1999"})
    assert r.status_code == 206 and r.content == BODY[1000:2000]
    assert r.headers["content-range"] == f"bytes 1000-1999/{len(BODY)}" and r.headers["accept-ranges"] == "bytes"
    assert [p for p, _ in seen] == ["/v0.mp4", "/v1.mp4"] and job.resolver.refreshed == 1  # v0 was refused


def test_a_body_the_cdn_cuts_off_is_carried_on_from_the_next_byte(api, tmp_path, monkeypatch):
    app, _ = api
    job = job_for(tmp_path, streams=[Stream("https://cdn.example/v1.mp4", {"Referer": "https://douyin.com/"}, "mp4")])
    monkeypatch.setitem(app.jobs, "job1", job)
    seen = cdn(monkeypatch, cut_first=True, refuse=())
    r = TestClient(app.app).get("/api/link-jobs/job1/media", headers={"Range": "bytes=0-59999"})
    assert r.content == BODY[:60000]
    assert seen[1][1] == "bytes=30000-59999"


def test_a_kept_upload_is_served_with_ranges_and_can_be_deleted(api, tmp_path, monkeypatch):
    app, _ = api
    root = tmp_path / "jobs" / "job1"
    root.mkdir(parents=True)
    upload = root / "source.mp4"
    upload.write_bytes(BODY)
    job = job_for(tmp_path, "local", [Stream(str(upload), {}, "local-file")])
    monkeypatch.setitem(app.jobs, "job1", job)
    client = TestClient(app.app)
    r = client.get("/api/link-jobs/job1/media", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == BODY[10:20]
    assert client.get("/api/link-jobs/job1/source").json()["state"] == "original"
    assert client.delete("/api/link-jobs/job1/source").json()["state"] == "cache"
    assert not upload.exists() and client.get("/api/link-jobs/job1/media").status_code == 404


def test_only_uploads_can_have_their_original_deleted(api, tmp_path, monkeypatch):
    app, _ = api
    monkeypatch.setitem(app.jobs, "job1", job_for(tmp_path))
    assert TestClient(app.app).delete("/api/link-jobs/job1/source").status_code == 400


def test_uploads_are_kept_unless_turned_off(monkeypatch):
    import importlib
    import app
    monkeypatch.delenv("KEEP_UPLOADS", raising=False)
    assert importlib.reload(app).KEEP_UPLOADS is True
    monkeypatch.setenv("KEEP_UPLOADS", "off")
    assert importlib.reload(app).KEEP_UPLOADS is False
    monkeypatch.delenv("KEEP_UPLOADS")
    importlib.reload(app)
