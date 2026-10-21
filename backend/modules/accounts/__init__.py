"""Platform logins from the UI: scan a QR code, and the cookie lands in backend/.env.accounts.

- B 站: the official web QR login (passport.bilibili.com …/qrcode/generate, then poll). The QR is drawn
  here (segno) from the address B 站 returns; once the user confirms in the B 站 App, the poll answer
  carries SESSDATA / bili_jct / DedeUserID, saved as BILIBILI_COOKIE. Checked with /x/web-interface/nav.
- 小红书: like 元宝, a headless browser keeps xiaohongshu.com open until its login dialog draws the QR
  (about 30 s: the page first waits out a security request that hangs from here). The QR is the
  image the page draws; the page's own polling answers code_status (1 scanned, 2 confirmed), and the
  logged-in cookies (id_token, a fresh web_session) are saved as XHS_COOKIE.
- 腾讯元宝: it only offers WeChat QR login, inside its own page. A headless browser keeps
  yuanbao.tencent.com open; the WeChat QR image's address is read from the login iframe and downloaded
  here (the headless page doesn't paint it). After the scan the page receives hy_user / hy_token,
  saved as YUANBAO_COOKIE.

Cookie values never leave the backend: the API reports only whether one is set, the account name,
when it expires, and where it came from. A value from .env or the environment is shown but not
removed from the UI; a UI login is saved to .env.accounts, which wins over .env.
"""
from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
import time
from dataclasses import dataclass, field

import httpx

from modules.settings import ACCOUNTS_FILE, ENV_FILE, overlay, parse_assignment, read_env_file, settings, vault

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
LOGIN_TTL = 240        # seconds a QR stays usable here (B 站 codes last 180 s, WeChat's a few minutes)
CHECK_TTL = 600        # seconds a "still logged in" check is reused
transport: httpx.AsyncBaseTransport | None = None  # tests swap in a mock

PLATFORMS = {
    "bilibili": {"key": "BILIBILI_COOKIE", "label": "B 站", "app": "B 站 App",
                 "purpose": "读更多评论（未登录只能读前 3 条热门）", "needs": ("SESSDATA=",)},
    "yuanbao": {"key": "YUANBAO_COOKIE", "label": "腾讯元宝", "app": "微信",
                "purpose": "解析视频号链接", "needs": ("hy_user=", "hy_token=")},
    "xiaohongshu": {"key": "XHS_COOKIE", "label": "小红书", "app": "小红书 App",
                    "purpose": "读小红书笔记的评论区（也让解析更稳）", "needs": ("a1=", "web_session=")},
}


class AccountError(Exception):
    """User-facing reason (Chinese)."""


# ---- the saved values ---------------------------------------------------------------------------
def _clean(value: str) -> str:
    return re.sub(r'[\r\n"\']', "", value).strip()


def save(values: dict[str, str | None]) -> None:
    """Set (or with None, remove) keys in .env.accounts, keeping the other lines; in the web demo,
    in the signed-in person's own store instead (settings.vault)."""
    keep = vault.get()
    if keep is not None:
        keep(values)
        return
    lines = ACCOUNTS_FILE.read_text().splitlines() if ACCOUNTS_FILE.exists() else []
    out, done = [], set()
    for line in lines:
        name = parse_assignment(line.strip())[0] if "=" in line and not line.strip().startswith("#") else ""
        if name in values:
            done.add(name)
            if values[name] is not None:
                out.append(f'{name}="{_clean(values[name])}"')
            continue
        out.append(line)
    out += [f'{k}="{_clean(v)}"' for k, v in values.items() if k not in done and v is not None]
    if not lines:
        out.insert(0, "# 在界面上扫码登录后自动写入；优先于 .env。不要提交到 git。")
    ACCOUNTS_FILE.write_text("\n".join(out) + "\n")
    os.chmod(ACCOUNTS_FILE, 0o600)


def source(key: str) -> str | None:
    if (overlay.get() or {}).get(key):
        return "ui"
    if os.environ.get(key):
        return "environment"
    if read_env_file(ACCOUNTS_FILE).get(key):
        return "ui"
    if read_env_file(ENV_FILE).get(key):
        return "env"
    return None


_checks: dict[str, tuple[float, dict]] = {}


async def bilibili_check(cookie: str) -> dict:
    """{"valid": bool, "user": name} from B 站's own "who am I"."""
    cached = _checks.get(cookie)
    if cached and time.time() - cached[0] < CHECK_TTL:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Cookie": cookie}) as c:
            data = ((await c.get("https://api.bilibili.com/x/web-interface/nav")).json() or {}).get("data") or {}
    except (httpx.HTTPError, ValueError):
        return {"valid": None, "user": ""}  # unknown: network trouble, not a bad cookie
    result = {"valid": bool(data.get("isLogin")), "user": data.get("uname", "")}
    _checks[cookie] = (time.time(), result)
    return result


async def status(platform: str) -> dict:
    info = PLATFORMS[platform]
    key = info["key"]
    env = settings()
    value = env.get(key, "").strip()
    out = {"id": platform, "label": info["label"], "purpose": info["purpose"], "app": info["app"], "qr": info.get("qr", True),
           "configured": bool(value), "source": source(key) if value else None,
           "user": env.get(f"{key}_USER", ""), "expires": None, "valid": None}
    try:
        out["expires"] = float(env.get(f"{key}_EXPIRES", "")) or None
    except ValueError:
        pass
    if value and platform == "bilibili":
        out.update({k: v for k, v in (await bilibili_check(value)).items() if v not in ("", None) or k == "valid"})
    if out["expires"] and out["expires"] < time.time():
        out["valid"] = False
    return out


async def set_cookie(platform: str, cookie: str) -> dict:
    """A cookie pasted by hand."""
    info = PLATFORMS[platform]
    cookie = _clean(cookie)
    if not all(n in cookie for n in info["needs"]):
        raise AccountError(f"{info['label']} 的 Cookie 里要有 {'、'.join(n.rstrip('=') for n in info['needs'])}")
    user = ""
    if platform == "bilibili":
        check = await bilibili_check(cookie)
        if check["valid"] is False:
            raise AccountError("B 站说这个 Cookie 没有登录（可能已过期），请重新复制")
        user = check["user"]
    save({info["key"]: cookie, f"{info['key']}_USER": user or None, f"{info['key']}_EXPIRES": None})
    return await status(platform)


def logout(platform: str) -> None:
    key = PLATFORMS[platform]["key"]
    save({key: None, f"{key}_USER": None, f"{key}_EXPIRES": None})


# ---- QR logins ----------------------------------------------------------------------------------
@dataclass
class Login:
    id: str
    platform: str
    qr: str                      # data URL
    state: str = "waiting"       # waiting → scanned → done | expired | error
    message: str = ""
    user: str = ""
    created: float = field(default_factory=time.time)
    handle: object = None        # B 站: qrcode_key; 元宝: the browser context
    owner: str = ""              # the web demo: whose login this is (only they may poll it)

    def public(self, qr: bool = True) -> dict:
        out = {"id": self.id, "platform": self.platform, "state": self.state, "message": self.message,
               "user": self.user, "expires_in": max(0, round(self.created + LOGIN_TTL - time.time()))}
        return out | {"qr": self.qr} if qr else out


logins: dict[str, Login] = {}


async def start(platform: str, owner: str = "") -> Login:
    for old in [x for x in logins.values()
                if (x.platform == platform and x.owner == owner) or time.time() - x.created > LOGIN_TTL * 2]:
        await cancel(old.id)
    if not PLATFORMS[platform].get("qr", True):
        raise AccountError(f"{PLATFORMS[platform]['label']} 不支持在这里扫码，请手动粘贴 Cookie")
    login = await {"bilibili": _bilibili_start, "yuanbao": _yuanbao_start, "xiaohongshu": _xhs_start}[platform]()
    login.owner = owner
    logins[login.id] = login
    return login


async def poll(login_id: str, owner: str = "") -> Login:
    login = logins.get(login_id)
    if login is None or login.owner != owner:
        raise AccountError("这次登录已经结束，请重新扫码")
    if login.state in ("done", "expired", "error"):
        return login
    if time.time() - login.created > LOGIN_TTL:
        login.state, login.message = "expired", "二维码已过期，请刷新"
        await _close(login)
        return login
    try:
        await {"bilibili": _bilibili_poll, "yuanbao": _yuanbao_poll, "xiaohongshu": _xhs_poll}[login.platform](login)
    except (httpx.HTTPError, ValueError):
        login.message = "暂时连不上，正在重试"
    if login.state in ("done", "expired", "error"):
        await _close(login)
    return login


async def cancel(login_id: str, owner: str | None = None) -> None:
    if owner is not None and getattr(logins.get(login_id), "owner", owner) != owner:
        return
    login = logins.pop(login_id, None)
    if login is not None:
        await _close(login)


async def shutdown() -> None:
    for login_id in list(logins):
        await cancel(login_id)


async def _close(login: Login) -> None:
    if login.platform in ("yuanbao", "xiaohongshu") and login.handle is not None:
        try:
            await (login.handle["context"] if isinstance(login.handle, dict) else login.handle).close()
        except Exception:
            pass
        login.handle = None


def _qr_svg(text: str) -> str:
    import segno
    return segno.make(text, error="m").svg_data_uri(scale=6, border=2, dark="#111111")


# B 站 ---------------------------------------------------------------------------------------------
PASSPORT = "https://passport.bilibili.com/x/passport-login/web/qrcode"
BILI_HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}


async def _bilibili_start() -> Login:
    async with httpx.AsyncClient(timeout=10, transport=transport, headers=BILI_HEADERS) as c:
        try:
            data = ((await c.get(f"{PASSPORT}/generate")).json() or {}).get("data") or {}
        except (httpx.HTTPError, ValueError):
            raise AccountError("连不上 B 站，请检查网络") from None
    if not data.get("url"):
        raise AccountError("B 站没有返回二维码，请稍后再试")
    return Login(secrets.token_urlsafe(9), "bilibili", _qr_svg(data["url"]), handle=data["qrcode_key"])


def raw_query(url: str) -> dict[str, str]:
    """Query parameters as sent: SESSDATA must stay percent-encoded, as a browser stores it."""
    query = url.split("?", 1)[1] if "?" in url else ""
    return dict(p.split("=", 1) for p in query.split("&") if "=" in p)


async def _bilibili_poll(login: Login) -> None:
    async with httpx.AsyncClient(timeout=10, transport=transport, headers=BILI_HEADERS) as c:
        response = await c.get(f"{PASSPORT}/poll", params={"qrcode_key": login.handle})
    data = (response.json() or {}).get("data") or {}
    code = data.get("code")
    if code == 86101:
        login.state, login.message = "waiting", ""
    elif code == 86090:
        login.state, login.message = "scanned", "已扫码，请在手机上确认登录"
    elif code == 86038:
        login.state, login.message = "expired", "二维码已过期，请刷新"
    elif code == 0:
        params = raw_query(data.get("url", ""))
        jar = {k: v for k, v in response.cookies.items()}
        parts = {k: jar.get(k) or params.get(k) for k in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5")}
        if not parts["SESSDATA"]:
            login.state, login.message = "error", "B 站没有返回登录凭证"
            return
        cookie = "; ".join(f"{k}={v}" for k, v in parts.items() if v)
        check = await bilibili_check(cookie)
        expires = params.get("Expires")
        save({"BILIBILI_COOKIE": cookie, "BILIBILI_COOKIE_USER": check.get("user") or None,
              "BILIBILI_COOKIE_EXPIRES": expires if expires and expires.isdigit() else None})
        login.state, login.user, login.message = "done", check.get("user", ""), "登录成功"
    else:
        login.state, login.message = "error", data.get("message") or f"B 站返回 {code}"


# 腾讯元宝 -----------------------------------------------------------------------------------------
YUANBAO = "https://yuanbao.tencent.com/chat"


async def _yuanbao_start() -> Login:
    from modules.agent import browser

    if not browser.available():
        raise AccountError("元宝扫码需要浏览器：在 backend 里运行 uv run playwright install --only-shell chromium")
    context = await (await browser.browser()).new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN", user_agent=UA)
    try:
        page = await context.new_page()
        await page.goto(YUANBAO, wait_until="domcontentloaded", timeout=20_000)
        src = ""
        for _ in range(20):  # the login dialog opens by itself; its WeChat iframe fills in after a moment
            await page.wait_for_timeout(750)
            frame = next((f for f in page.frames if "open.weixin.qq.com/connect/qrconnect" in f.url), None)
            if frame is not None:
                srcs = await frame.evaluate("Array.from(document.images).map(i => i.src)")
                src = next((s for s in srcs if "/connect/qrcode/" in s), "")
                if src:
                    break
        if not src:
            raise AccountError("元宝没有显示微信登录二维码，请稍后再试")
        async with httpx.AsyncClient(timeout=10, transport=transport, headers={"User-Agent": UA, "Referer": "https://open.weixin.qq.com/"}) as c:
            image = await c.get(src)
        if image.status_code != 200:
            raise AccountError("微信登录二维码下载失败，请稍后再试")
        kind = image.headers.get("content-type", "image/jpeg").split(";")[0]
        qr = f"data:{kind};base64," + base64.b64encode(image.content).decode()
    except AccountError:
        await context.close()
        raise
    except Exception:
        await context.close()
        raise AccountError("打不开腾讯元宝，请检查网络") from None
    return Login(secrets.token_urlsafe(9), "yuanbao", qr, handle=context)


async def _yuanbao_poll(login: Login) -> None:
    context = login.handle
    cookies = {c["name"]: c for c in await context.cookies("https://yuanbao.tencent.com")}
    if cookies.get("hy_token") and cookies.get("hy_user"):
        token = cookies["hy_token"]
        expires = token.get("expires") or -1
        save({"YUANBAO_COOKIE": f"hy_user={cookies['hy_user']['value']}; hy_token={token['value']}",
              "YUANBAO_COOKIE_USER": None,
              "YUANBAO_COOKIE_EXPIRES": str(int(expires)) if expires and expires > 0 else None})
        login.state, login.message = "done", "登录成功"
        return
    for page in context.pages:
        for frame in page.frames:
            if "open.weixin.qq.com/connect" not in frame.url:
                continue
            try:
                text = await frame.evaluate("document.body ? document.body.innerText : ''")
            except Exception:
                continue
            if "扫描成功" in text or "确认登录" in text:
                login.state, login.message = "scanned", "已扫码，请在微信里确认登录"
            elif "已失效" in text or "过期" in text:
                login.state, login.message = "expired", "二维码已过期，请刷新"


# 小红书 ------------------------------------------------------------------------------------------
XHS = "https://www.xiaohongshu.com/explore"
XHS_QR_WAIT = 60  # seconds for the login dialog to draw its QR


async def _xhs_start() -> Login:
    from modules.agent import browser

    if not browser.available():
        raise AccountError("小红书扫码需要浏览器：在 backend 里运行 uv run playwright install --only-shell chromium")
    context = await (await browser.browser()).new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN", user_agent=UA)
    seen = {"status": None}

    async def on_response(resp):
        if "/login/qrcode/status" not in resp.url:
            return
        try:
            seen["status"] = ((await resp.json()).get("data") or {}).get("code_status")
        except Exception:
            pass

    try:
        page = await context.new_page()
        page.on("response", on_response)
        await page.goto(XHS, wait_until="commit", timeout=20_000)
        src = ""
        for _ in range(XHS_QR_WAIT):  # the login dialog opens by itself once the page's scripts run
            await page.wait_for_timeout(1000)
            src = await page.evaluate("(() => { const i = document.querySelector('.qrcode img'); return i ? i.src : '' })()")
            if src.startswith("data:image/"):
                break
        if not src.startswith("data:image/"):
            raise AccountError("小红书没有显示登录二维码，请稍后再试")
    except AccountError:
        await context.close()
        raise
    except Exception:
        await context.close()
        raise AccountError("打不开小红书，请检查网络") from None
    return Login(secrets.token_urlsafe(9), "xiaohongshu", src, handle={"context": context, "seen": seen})


async def _xhs_poll(login: Login) -> None:
    context, seen = login.handle["context"], login.handle["seen"]
    cookies = {c["name"]: c for c in await context.cookies("https://www.xiaohongshu.com")}
    if cookies.get("id_token") and cookies.get("web_session"):  # only a logged-in browser has id_token
        expires = cookies["web_session"].get("expires") or -1
        save({"XHS_COOKIE": "; ".join(f"{n}={c['value']}" for n, c in cookies.items()),
              "XHS_COOKIE_USER": None,
              "XHS_COOKIE_EXPIRES": str(int(expires)) if expires and expires > 0 else None})
        login.state, login.message = "done", "登录成功"
    elif seen["status"] == 1:
        login.state, login.message = "scanned", "已扫码，请在小红书 App 里确认登录"
    elif seen["status"] == 3:
        login.state, login.message = "expired", "二维码已过期，请刷新"


async def all_status() -> list[dict]:
    return list(await asyncio.gather(*(status(p) for p in PLATFORMS)))
