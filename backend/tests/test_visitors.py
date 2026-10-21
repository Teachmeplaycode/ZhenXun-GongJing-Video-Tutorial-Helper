"""Public demo: each browser sees only its own sessions; accounts and other platforms are closed."""
import pytest
from fastapi.testclient import TestClient

from modules import members, visitors
from modules.frames import FrameJob
from modules.screentext import ScreenText
from modules.store import SessionStore
from modules.transcript import Transcript
from modules.video_source import ResolvedVideo


@pytest.fixture
def api(tmp_path, monkeypatch):
    import app

    store = SessionStore(tmp_path / "db.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(app, "store", store)
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    monkeypatch.setenv("VISITOR_SECRET", "test-secret")
    monkeypatch.setattr(visitors, "_keys", {})
    monkeypatch.setattr(app.member_service, "limiter", members.Limiter())
    return app, store


def session(app, store, job_id, owner, monkeypatch):
    video = ResolvedVideo("bilibili", job_id, f"https://www.bilibili.com/video/{job_id}", f"视频 {job_id}", 60.0, [])
    job = FrameJob(job_id, video, None, app.DATA_DIR / job_id, count=1)
    job.transcript, job.screentext = Transcript(), ScreenText()
    monkeypatch.setitem(app.jobs, job_id, job)
    store.create(job, f"https://www.bilibili.com/video/{job_id}", owner=owner)
    return job


def visitor(app) -> tuple[TestClient, str]:
    client = TestClient(app.app)
    client.get("/api/health")
    return client, visitors.verify(client.cookies.get(visitors.COOKIE), b"test-secret")


def test_a_browser_gets_a_signed_id_that_a_forged_cookie_cannot_replace(api):
    app, _ = api
    client, who = visitor(app)
    assert who and client.get("/api/health").json()["public"] is True
    r = TestClient(app.app).get("/api/health", headers={"Cookie": f"{visitors.COOKIE}={who}.0000"})
    fresh = r.cookies.get(visitors.COOKIE)
    assert fresh and visitors.verify(fresh, b"test-secret") not in (None, who)  # a new id, not the claimed one


def test_visitors_see_only_their_own_sessions(api, monkeypatch):
    app, store = api
    alice, a = visitor(app)
    bob, b = visitor(app)
    session(app, store, "job_a", a, monkeypatch)
    session(app, store, "job_b", b, monkeypatch)

    assert [s["id"] for s in alice.get("/api/sessions").json()["sessions"]] == ["job_a"]
    assert alice.get("/api/sessions/job_a").status_code == 200
    for path in ("/api/sessions/job_b", "/api/link-jobs/job_b", "/api/link-jobs/job_b/transcript",
                 "/api/link-jobs/job_b/frames/0.jpg", "/api/sessions/job_b/export"):
        assert alice.get(path).status_code == 404, path
    assert alice.delete("/api/sessions/job_b").status_code == 404
    assert store.exists("job_b")
    assert TestClient(app.app).get("/api/sessions").json()["sessions"] == []  # a new browser has nothing


def test_locally_everything_stays_one_user(api, monkeypatch):
    app, store = api
    monkeypatch.setenv("PUBLIC_DEMO", "")
    session(app, store, "job_a", "", monkeypatch)
    client = TestClient(app.app)
    assert [s["id"] for s in client.get("/api/sessions").json()["sessions"]] == ["job_a"]
    assert client.get("/api/link-jobs/job_a").status_code == 200
    assert visitors.COOKIE not in client.cookies


def test_accounts_and_unlisted_platforms_are_closed(api, monkeypatch):
    app, _ = api
    client, _ = visitor(app)
    assert client.get("/api/accounts").status_code == 403
    assert client.put("/api/accounts/bilibili", json={"cookie": "x"}).status_code == 403

    class Channels:
        platform = "wechat_channels"

    monkeypatch.setattr(app.registry, "find", lambda url: Channels())
    r = client.post("/api/link-jobs", json={"url": "https://channels.weixin.qq.com/x"})
    assert r.status_code == 403 and "B站" in r.json()["detail"]
    assert "wechat_channels" not in client.get("/api/health").json()["platforms"]


def test_old_databases_gain_the_owner_column(tmp_path):
    import sqlite3

    db = sqlite3.connect(tmp_path / "old.sqlite3")
    db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL, source TEXT NOT NULL,"
               " task TEXT NOT NULL DEFAULT '', video TEXT NOT NULL, slots TEXT NOT NULL)")
    db.execute("INSERT INTO sessions VALUES ('old', 0, 0, 'u', '', '{}', '[]')")
    db.commit()
    db.close()
    assert SessionStore(tmp_path / "old.sqlite3").owner("old") == ""


def test_the_access_code_lets_a_browser_in(api, monkeypatch):
    app, _ = api
    monkeypatch.setenv("ACCESS_CODES", "frame2026, other")
    client = TestClient(app.app)
    health = client.get("/api/health").json()
    assert health["access_required"] and not health["access_granted"] and health["user"] is None
    r = client.get("/api/sessions")
    assert r.status_code == 401 and r.json()["code"] == "access_required"
    assert client.post("/api/access", json={"code": "nope"}).status_code == 403
    assert client.post("/api/access", json={"code": "frame2026"}).status_code == 200
    assert client.get("/api/health").json()["access_granted"] is True
    assert client.get("/api/sessions").status_code == 200


def test_wrong_codes_are_limited(api, monkeypatch):
    app, _ = api
    monkeypatch.setenv("ACCESS_CODES", "frame2026")
    client = TestClient(app.app)
    codes = [client.post("/api/access", json={"code": f"x{i}"}).status_code for i in range(11)]
    assert codes[:10] == [403] * 10 and codes[10] == 429


def test_an_account_carries_its_sessions_to_another_browser(api, monkeypatch):
    app, store = api
    monkeypatch.setenv("ACCESS_CODES", "frame2026")
    laptop, anon = visitor(app)
    laptop.post("/api/access", json={"code": "frame2026"})
    session(app, store, "job_a", anon, monkeypatch)

    assert laptop.post("/api/auth/register", json={"name": "评委1", "password": "123"}).status_code == 422
    r = laptop.post("/api/auth/register", json={"name": "评委1", "password": "secret1"})
    assert r.status_code == 200 and r.json()["user"]["name"] == "评委1"
    assert [s["id"] for s in laptop.get("/api/sessions").json()["sessions"]] == ["job_a"]  # moved to the account
    assert laptop.get("/api/health").json()["user"] == {"name": "评委1"}

    phone = TestClient(app.app)  # no access code: signing in is enough
    assert phone.post("/api/auth/login", json={"name": "评委1", "password": "wrong!"}).status_code == 403
    assert phone.post("/api/auth/login", json={"name": "评委1", "password": "secret1"}).status_code == 200
    assert [s["id"] for s in phone.get("/api/sessions").json()["sessions"]] == ["job_a"]
    assert phone.get("/api/link-jobs/job_a").status_code == 200

    assert phone.post("/api/auth/logout").status_code == 200
    assert phone.get("/api/sessions").json()["sessions"] == []  # signed out: a fresh anonymous browser
    assert laptop.post("/api/auth/register", json={"name": "评委1", "password": "secret2"}).status_code == 409
