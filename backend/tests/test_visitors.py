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


def test_an_account_carries_its_sessions_to_another_browser(api, monkeypatch):
    app, store = api
    laptop, anon = visitor(app)
    session(app, store, "job_a", anon, monkeypatch)

    assert laptop.post("/api/auth/register", json={"name": "评委1", "password": "123"}).status_code == 422
    r = laptop.post("/api/auth/register", json={"name": "评委1", "password": "secret1"})
    assert r.status_code == 200 and r.json()["user"]["name"] == "评委1"
    assert [s["id"] for s in laptop.get("/api/sessions").json()["sessions"]] == ["job_a"]  # moved to the account
    me = laptop.get("/api/health").json()["user"]
    assert me["name"] == "评委1" and me["plan"] == "free" and me["questions"] == {"used": 0, "limit": 10}

    phone = TestClient(app.app)
    assert phone.post("/api/auth/login", json={"name": "评委1", "password": "wrong!"}).status_code == 403
    assert phone.post("/api/auth/login", json={"name": "评委1", "password": "secret1"}).status_code == 200
    assert [s["id"] for s in phone.get("/api/sessions").json()["sessions"]] == ["job_a"]
    assert phone.post("/api/auth/logout").status_code == 200
    assert phone.get("/api/sessions").json()["sessions"] == []  # signed out: a fresh anonymous browser
    assert laptop.post("/api/auth/register", json={"name": "评委1", "password": "secret2"}).status_code == 409


def test_wrong_passwords_are_limited(api):
    app, _ = api
    client = TestClient(app.app)
    client.post("/api/auth/register", json={"name": "someone", "password": "secret1"})
    other = TestClient(app.app)
    codes = [other.post("/api/auth/login", json={"name": "someone", "password": f"x{i}xxxxx"}).status_code for i in range(11)]
    assert codes[:10] == [403] * 10 and codes[10] == 429


def test_signed_out_visitors_cannot_import_and_accounts_get_a_daily_allowance(api, monkeypatch):
    app, _ = api
    monkeypatch.setenv("PLAN_LIMITS", '{"free": {"imports": 2}}')

    class Bili:
        platform = "bilibili"

    monkeypatch.setattr(app.registry, "find", lambda url: Bili())

    async def no_network(url, part=None):  # resolves, then stops before any real work
        raise app.ResolveError("network", "测试里不联网") if "bad" in url else RuntimeError("stop")

    async def resolved(url, part=None):
        return None, ResolvedVideo("bilibili", "BV1", url, "t", 60.0, [])

    monkeypatch.setattr(app.registry, "resolve", no_network)
    monkeypatch.setattr(app, "FrameJob", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop")))
    anon = TestClient(app.app)
    r = anon.post("/api/link-jobs", json={"url": "https://www.bilibili.com/video/BV1"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "login_required"

    user = TestClient(app.app)
    user.post("/api/auth/register", json={"name": "评委2", "password": "secret1"})
    assert user.post("/api/link-jobs", json={"url": "https://www.bilibili.com/video/bad"}).status_code == 422
    assert user.get("/api/health").json()["user"]["imports"]["used"] == 0  # a link that doesn't resolve is free
    for _ in range(2):
        monkeypatch.setattr(app.registry, "resolve", resolved)
        with pytest.raises(RuntimeError):
            user.post("/api/link-jobs", json={"url": "https://www.bilibili.com/video/BV1"})
    r = user.post("/api/link-jobs", json={"url": "https://www.bilibili.com/video/BV1"})
    assert r.status_code == 429 and "2 次" in r.json()["detail"]["message"]
    assert user.get("/api/health").json()["user"]["imports"] == {"used": 2, "limit": 2}


def test_owner_accounts_have_no_limit(api, monkeypatch):
    app, _ = api
    monkeypatch.setenv("OWNER_ACCOUNTS", "linyi")
    client = TestClient(app.app)
    client.post("/api/auth/register", json={"name": "linyi", "password": "secret1"})
    me = client.get("/api/health").json()["user"]
    assert me["plan"] == "owner" and me["questions"]["limit"] is None


def test_oauth_buttons_show_only_when_configured(api, monkeypatch):
    app, _ = api
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.setenv("GITHUB_CLIENT_ID", "id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PUBLIC_URL", "https://linyi.work/ZhenXun")
    client = TestClient(app.app)
    assert client.get("/api/health").json()["oauth"] == ["github"]
    r = client.get("/api/auth/github/start", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"].startswith("https://github.com/login/oauth/authorize?")
    assert "redirect_uri=https%3A%2F%2Flinyi.work%2FZhenXun%2Fapi%2Fauth%2Fgithub%2Fcallback" in r.headers["location"]
    assert client.get("/api/auth/google/start", follow_redirects=False).status_code == 404
    bad = client.get("/api/auth/github/callback?code=x&state=forged", follow_redirects=False)
    assert bad.headers["location"].endswith("?login=failed")
