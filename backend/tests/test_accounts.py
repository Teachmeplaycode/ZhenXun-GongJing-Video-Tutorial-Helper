"""Platform logins: where cookies are saved, B 站's QR flow, and who may call the endpoints."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from modules import accounts, settings as settings_module


@pytest.fixture
def files(tmp_path, monkeypatch):
    env, saved = tmp_path / ".env", tmp_path / ".env.accounts"
    for module in (settings_module, accounts):
        monkeypatch.setattr(module, "ENV_FILE", env)
        monkeypatch.setattr(module, "ACCOUNTS_FILE", saved)
    for key in ("BILIBILI_COOKIE", "YUANBAO_COOKIE", "BILIBILI_COOKIE_USER", "BILIBILI_COOKIE_EXPIRES"):
        monkeypatch.delenv(key, raising=False)
    accounts._checks.clear()
    accounts.logins.clear()
    return env, saved


def bili(monkeypatch, *, poll_codes=(86101,), logged_in=True):
    codes = list(poll_codes)
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        path = request.url.path
        if path.endswith("/qrcode/generate"):
            return httpx.Response(200, json={"code": 0, "data": {"url": "https://account.bilibili.com/h5/scan?k=1", "qrcode_key": "key1"}})
        if path.endswith("/qrcode/poll"):
            code = codes.pop(0) if len(codes) > 1 else codes[0]
            url = ("https://passport.biligame.com/crossDomain?DedeUserID=42&DedeUserID__ckMd5=ab&Expires=1800000000"
                   "&SESSDATA=s3%2C1800000000%2Cx*b1&bili_jct=jct&gourl=x") if code == 0 else ""
            return httpx.Response(200, json={"code": 0, "data": {"code": code, "url": url, "message": ""}})
        if path.endswith("/nav"):
            return httpx.Response(200, json={"code": 0, "data": {"isLogin": logged_in, "uname": "测试用户" if logged_in else ""}})
        return httpx.Response(404)

    monkeypatch.setattr(accounts, "transport", httpx.MockTransport(handler))
    return seen


def test_save_keeps_other_lines_and_removes_with_none(files):
    _, saved = files
    saved.write_text("# 说明\nOTHER=1\n", encoding="utf-8")
    accounts.save({"BILIBILI_COOKIE": 'SESSDATA=a"b\n', "X": "y"})
    accounts.save({"X": None})
    assert saved.read_text(encoding="utf-8") == '# 说明\nOTHER=1\nBILIBILI_COOKIE="SESSDATA=ab"\n'
    assert oct(saved.stat().st_mode & 0o777) == "0o600"


def test_ui_login_wins_over_env_file_but_not_environment(files, monkeypatch):
    env, saved = files
    env.write_text('YUANBAO_COOKIE="hy_user=old; hy_token=old"\n', encoding="utf-8")
    assert accounts.source("YUANBAO_COOKIE") == "env"
    accounts.save({"YUANBAO_COOKIE": "hy_user=new; hy_token=new"})
    assert settings_module.settings()["YUANBAO_COOKIE"].endswith("new") and accounts.source("YUANBAO_COOKIE") == "ui"
    monkeypatch.setenv("YUANBAO_COOKIE", "hy_user=e; hy_token=e")
    assert accounts.source("YUANBAO_COOKIE") == "environment"


def test_bilibili_qr_login_saves_cookie_and_name(files, monkeypatch):
    _, saved = files
    bili(monkeypatch, poll_codes=(86101, 86090, 0))

    async def flow():
        login = await accounts.start("bilibili")
        assert login.qr.startswith("data:image/svg+xml") and "qr" not in login.public(qr=False)
        states = [(await accounts.poll(login.id)).state for _ in range(3)]
        return login, states

    login, states = asyncio.run(flow())
    assert states == ["waiting", "scanned", "done"] and login.user == "测试用户"
    env = settings_module.settings()
    # SESSDATA stays percent-encoded, as a browser stores it.
    assert env["BILIBILI_COOKIE"] == "SESSDATA=s3%2C1800000000%2Cx*b1; bili_jct=jct; DedeUserID=42; DedeUserID__ckMd5=ab"
    status = asyncio.run(accounts.status("bilibili"))
    assert status == status | {"configured": True, "source": "ui", "user": "测试用户", "valid": True, "expires": 1800000000.0}
    assert "SESSDATA" not in str({k: v for k, v in status.items()})  # the value itself is never reported


def test_expired_qr_and_unknown_login(files, monkeypatch):
    bili(monkeypatch, poll_codes=(86038,))

    async def flow():
        login = await accounts.start("bilibili")
        return await accounts.poll(login.id)

    assert asyncio.run(flow()).state == "expired"
    with pytest.raises(accounts.AccountError):
        asyncio.run(accounts.poll("nope"))


def test_pasted_cookie_is_checked(files, monkeypatch):
    bili(monkeypatch, logged_in=False)
    with pytest.raises(accounts.AccountError, match="SESSDATA"):
        asyncio.run(accounts.set_cookie("bilibili", "foo=bar"))
    with pytest.raises(accounts.AccountError, match="没有登录"):
        asyncio.run(accounts.set_cookie("bilibili", "SESSDATA=x"))
    status = asyncio.run(accounts.set_cookie("yuanbao", "hy_user=u; hy_token=t"))
    assert status["configured"] and status["source"] == "ui"
    accounts.logout("yuanbao")
    assert not asyncio.run(accounts.status("yuanbao"))["configured"]


def test_endpoints_refuse_other_sites(files, monkeypatch):
    import app

    bili(monkeypatch)
    client = TestClient(app.app)
    assert client.get("/api/accounts", headers={"Origin": "http://localhost:5173"}).status_code == 200
    assert client.post("/api/accounts/bilibili/login", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.delete("/api/accounts/yuanbao", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/accounts/nothing/login").status_code == 404
    body = client.get("/api/accounts").json()["accounts"]
    assert [a["id"] for a in body] == ["bilibili", "yuanbao", "xiaohongshu"] and all("cookie" not in a for a in body)


def test_xiaohongshu_offers_a_scan_and_still_takes_a_pasted_cookie(files):
    with pytest.raises(accounts.AccountError, match="web_session"):
        asyncio.run(accounts.set_cookie("xiaohongshu", "a1=x"))
    status = asyncio.run(accounts.set_cookie("xiaohongshu", "a1=x; web_session=y"))
    assert status["configured"] and status["qr"] is True


def test_xiaohongshu_scan_saves_the_logged_in_cookies(files):
    class Context:
        def __init__(self):
            self.jar = [{"name": "a1", "value": "A"}, {"name": "web_session", "value": "guest"}]

        async def cookies(self, url):
            return self.jar

    ctx, seen = Context(), {"status": None}
    login = accounts.Login("id", "xiaohongshu", "data:image/png;base64,", handle={"context": ctx, "seen": seen})
    asyncio.run(accounts._xhs_poll(login))
    assert login.state == "waiting"  # a guest session is not a login
    seen["status"] = 1
    asyncio.run(accounts._xhs_poll(login))
    assert login.state == "scanned"
    ctx.jar = [{"name": "a1", "value": "A"}, {"name": "web_session", "value": "S", "expires": 1793000000},
               {"name": "id_token", "value": "T"}]
    asyncio.run(accounts._xhs_poll(login))
    assert login.state == "done"
    assert accounts.settings()["XHS_COOKIE"] == "a1=A; web_session=S; id_token=T"
    assert asyncio.run(accounts.status("xiaohongshu"))["expires"] == 1793000000
