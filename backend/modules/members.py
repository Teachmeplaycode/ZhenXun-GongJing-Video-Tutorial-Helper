"""Accounts and daily allowances for the public web demo (only when PUBLIC_DEMO is on).

Anyone can open the page; importing a video or asking a question needs an account. An account
is made with a name and a password (scrypt), or by signing in with GitHub or Google (OAuth, when
their client id and secret are set). Signing up or in makes the browser's visitor id
"u<account id>", and the sessions that browser made before move to the account, so the same
history shows wherever the person signs in. Signing out gives the browser a fresh anonymous id.

Each account has a plan, and a plan allows so many questions and so many new videos a day
(Beijing time). New accounts are on `free`; names in OWNER_ACCOUNTS are on `owner` (no limits).
PLAN_LIMITS overrides the numbers, e.g. {"free": {"questions": 20}}.

  GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET   an OAuth app; callback <PUBLIC_URL>/api/auth/github/callback
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET   an OAuth client; callback <PUBLIC_URL>/api/auth/google/callback
  PUBLIC_URL                                where the app is reached, e.g. https://linyi.work/ZhenXun
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from modules import visitors

NAME = re.compile(r"^[\w一-鿿-]{2,20}$")
MIN_PASSWORD = 6
TRIES, WINDOW = 10, 600  # wrong passwords per address and name per window (seconds)
STATE_COOKIE = "fj_oauth"

PLANS = {
    "free": {"label": "免费", "questions": 10, "imports": 3},
    "plus": {"label": "进阶", "questions": 100, "imports": 20},
    "owner": {"label": "管理员", "questions": None, "imports": None},  # None: no limit
}
KINDS = {"questions": "提问", "imports": "导入视频"}

PROVIDERS = {
    "github": {
        "label": "GitHub",
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "user": "https://api.github.com/user",
        "scope": "read:user",
    },
    "google": {
        "label": "Google",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "user": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid profile email",
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password TEXT NOT NULL,          -- scrypt$<salt hex>$<hash hex>; '' for an account made through OAuth
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
  user_id INTEGER NOT NULL,
  day TEXT NOT NULL,               -- YYYY-MM-DD, Beijing time
  kind TEXT NOT NULL,              -- questions | imports
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day, kind)
);
"""
COLUMNS = {"plan": "TEXT NOT NULL DEFAULT 'free'", "github_id": "TEXT", "google_id": "TEXT"}


def plans() -> dict:
    merged = {k: dict(v) for k, v in PLANS.items()}
    try:
        for plan, limits in json.loads(os.environ.get("PLAN_LIMITS") or "{}").items():
            merged.setdefault(plan, {"label": plan}).update(limits)
    except (ValueError, AttributeError):
        pass
    return merged


def owners() -> set[str]:
    return {n.strip().lower() for n in os.environ.get("OWNER_ACCOUNTS", "").split(",") if n.strip()}


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 8 * 3600))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$")
        return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), stored)
    except ValueError:
        return False


def account_of(visitor: str) -> int | None:
    return int(visitor[1:]) if re.fullmatch(r"u\d+", visitor or "") else None


def public_url(request: Request) -> str:
    configured = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def provider_keys(provider: str) -> tuple[str, str] | None:
    prefix = provider.upper()
    cid, secret = os.environ.get(f"{prefix}_CLIENT_ID", "").strip(), os.environ.get(f"{prefix}_CLIENT_SECRET", "").strip()
    return (cid, secret) if cid and secret else None


class Users:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        have = {row["name"] for row in self.db.execute("PRAGMA table_info(users)")}
        for column, kind in COLUMNS.items():
            if column not in have:
                self.db.execute(f"ALTER TABLE users ADD COLUMN {column} {kind}")

    def create(self, name: str, password: str = "", **ids) -> int:
        plan = "owner" if name.lower() in owners() else "free"
        with self.db:
            return self.db.execute(
                "INSERT INTO users (name, password, created, plan, github_id, google_id) VALUES (?, ?, ?, ?, ?, ?)",
                (name, hash_password(password) if password else "", time.time(), plan,
                 ids.get("github_id"), ids.get("google_id"))).lastrowid

    def find(self, name: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()

    def get(self, user_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def by_provider(self, provider: str, external_id: str) -> sqlite3.Row | None:
        return self.db.execute(f"SELECT * FROM users WHERE {provider}_id = ?", (external_id,)).fetchone()

    def free_name(self, wanted: str) -> str:
        base = re.sub(r"[^\w一-鿿-]", "", wanted)[:16] or "user"
        base = base if len(base) >= 2 else f"{base}_u"
        name, n = base, 1
        while self.find(name) is not None:
            n += 1
            name = f"{base}{n}"
        return name

    def plan(self, row: sqlite3.Row) -> str:
        return "owner" if row["name"].lower() in owners() else row["plan"]

    def used(self, user_id: int, kind: str) -> int:
        row = self.db.execute("SELECT count FROM usage WHERE user_id = ? AND day = ? AND kind = ?",
                              (user_id, today(), kind)).fetchone()
        return row[0] if row else 0

    def add(self, user_id: int, kind: str) -> None:
        with self.db:
            self.db.execute("INSERT INTO usage (user_id, day, kind, count) VALUES (?, ?, ?, 1) "
                            "ON CONFLICT (user_id, day, kind) DO UPDATE SET count = count + 1", (user_id, today(), kind))


class Limiter:
    """At most TRIES failures per key per WINDOW seconds."""

    def __init__(self):
        self.failures: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now, seen = time.time(), self.failures[key]
        while seen and now - seen[0] > WINDOW:
            seen.popleft()
        if len(seen) >= TRIES:
            raise HTTPException(429, "尝试次数太多，请 10 分钟后再试")

    def fail(self, key: str) -> None:
        self.failures[key].append(time.time())


class Credentials(BaseModel):
    name: str
    password: str


def address(request: Request) -> str:
    return request.client.host if request.client else "?"


class Members:
    def __init__(self, path, key, claim):
        """`path()` is where accounts are kept (opened on first use), `key()` the cookie signing key,
        `claim(old, new)` moves sessions between visitor ids."""
        self.path, self.key, self.claim = path, key, claim
        self._users: dict[Path, Users] = {}
        self.limiter = Limiter()
        self.router = APIRouter()
        self.router.add_api_route("/api/auth/register", self.register, methods=["POST"])
        self.router.add_api_route("/api/auth/login", self.login, methods=["POST"])
        self.router.add_api_route("/api/auth/logout", self.logout, methods=["POST"])
        self.router.add_api_route("/api/auth/{provider}/start", self.oauth_start, methods=["GET"])
        self.router.add_api_route("/api/auth/{provider}/callback", self.oauth_callback, methods=["GET"])

    @property
    def users(self) -> Users:
        path = self.path()
        if path not in self._users:
            self._users[path] = Users(path)
        return self._users[path]

    # ---- who, and how much is left -----------------------------------------------------------
    def quota(self, row: sqlite3.Row) -> dict:
        plan_id = self.users.plan(row)
        plan = plans().get(plan_id, plans()["free"])
        return {"plan": plan_id, "label": plan.get("label", plan_id),
                **{kind: {"used": self.users.used(row["id"], kind), "limit": plan.get(kind)} for kind in KINDS}}

    def status(self) -> dict:
        """What /api/health adds: who is signed in, what's left today, which sign-in buttons to show."""
        user_id = account_of(visitors.current.get())
        row = self.users.get(user_id) if user_id is not None else None
        return {"user": {"name": row["name"], **self.quota(row)} if row else None,
                "oauth": [p for p in PROVIDERS if provider_keys(p)]}

    def require(self, kind: str) -> None:
        """Refuse before any work when signed out or today's allowance is used up (counts nothing)."""
        self.charge(kind, count=False)

    def charge(self, kind: str, count: bool = True) -> None:
        """Count one question or import against today's allowance; 401 signed out, 429 when used up."""
        if not visitors.enabled():
            return
        user_id = account_of(visitors.current.get())
        row = self.users.get(user_id) if user_id is not None else None
        if row is None:
            raise HTTPException(401, detail={"code": "login_required", "message": "登录后才能导入视频和提问"})
        quota = self.quota(row)[kind]
        if quota["limit"] is not None and quota["used"] >= quota["limit"]:
            raise HTTPException(429, detail={"code": "quota_exceeded",
                                             "message": f"今天的{KINDS[kind]}次数（{quota['limit']} 次）已用完，明天 0 点（北京时间）恢复"})
        if count:
            self.users.add(row["id"], kind)

    # ---- password accounts ----------------------------------------------------------------
    def _cookie(self, response, request: Request, name: str, value: str, max_age: int = visitors.MAX_AGE) -> None:
        response.set_cookie(name, visitors.sign(value, self.key()), max_age=max_age, path=visitors.cookie_path(),
                            httponly=True, samesite="lax", secure=request.url.scheme == "https"
                            or public_url(request).startswith("https"))

    def _enabled(self) -> None:
        if not visitors.enabled():
            raise HTTPException(404, "本机版没有账号")

    def _sign_in(self, response, request: Request, user_id: int):
        """Move this browser's anonymous sessions to the account and make it the visitor id."""
        current = visitors.current.get()
        if account_of(current) is None and current:
            self.claim(current, f"u{user_id}")
        self._cookie(response, request, visitors.COOKIE, f"u{user_id}")
        return response

    def _signed_in(self, request: Request, user_id: int) -> JSONResponse:
        row = self.users.get(user_id)
        return self._sign_in(JSONResponse({"ok": True, "user": {"name": row["name"], **self.quota(row)}}), request, user_id)

    async def register(self, body: Credentials, request: Request):
        self._enabled()
        name = body.name.strip()
        if not NAME.match(name):
            raise HTTPException(422, "用户名 2～20 个字，可用中文、字母、数字、下划线和短横线")
        if len(body.password) < MIN_PASSWORD:
            raise HTTPException(422, f"密码至少 {MIN_PASSWORD} 位")
        if self.users.find(name) is not None:
            raise HTTPException(409, "这个用户名已经有人用了")
        return self._signed_in(request, self.users.create(name, body.password))

    async def login(self, body: Credentials, request: Request):
        self._enabled()
        key = f"{address(request)}:{body.name.strip().lower()}"
        self.limiter.check(key)
        row = self.users.find(body.name.strip())
        if row is None or not row["password"] or not check_password(body.password, row["password"]):
            self.limiter.fail(key)
            raise HTTPException(403, "用户名或密码不对")
        return self._signed_in(request, row["id"])

    async def logout(self, request: Request):
        self._enabled()
        response = JSONResponse({"ok": True})
        self._cookie(response, request, visitors.COOKIE, visitors.new())  # a fresh anonymous browser
        return response

    # ---- GitHub / Google ------------------------------------------------------------------
    def _provider(self, provider: str) -> tuple[dict, tuple[str, str]]:
        self._enabled()
        keys = provider_keys(provider) if provider in PROVIDERS else None
        if keys is None:
            raise HTTPException(404, "没有开通这种登录方式")
        return PROVIDERS[provider], keys

    async def oauth_start(self, provider: str, request: Request):
        spec, (client_id, _) = self._provider(provider)
        state = secrets.token_urlsafe(16)
        params = {"client_id": client_id, "redirect_uri": f"{public_url(request)}/api/auth/{provider}/callback",
                  "scope": spec["scope"], "state": state}
        if provider == "google":
            params["response_type"] = "code"
        response = RedirectResponse(f"{spec['authorize']}?{urlencode(params)}")
        self._cookie(response, request, STATE_COOKIE, f"{provider}:{state}", max_age=600)
        return response

    async def oauth_callback(self, provider: str, request: Request, code: str = "", state: str = ""):
        spec, (client_id, secret) = self._provider(provider)
        home = f"{public_url(request)}/"
        expected = visitors.verify(request.cookies.get(STATE_COOKIE), self.key())
        if not code or expected != f"{provider}:{state}":
            return RedirectResponse(f"{home}?login=failed")
        try:
            async with httpx.AsyncClient(timeout=15, headers={"Accept": "application/json"}) as client:
                token = (await client.post(spec["token"], data={
                    "client_id": client_id, "client_secret": secret, "code": code, "grant_type": "authorization_code",
                    "redirect_uri": f"{public_url(request)}/api/auth/{provider}/callback"})).json()["access_token"]
                profile = (await client.get(spec["user"], headers={"Authorization": f"Bearer {token}"})).json()
        except (httpx.HTTPError, KeyError, ValueError):
            return RedirectResponse(f"{home}?login=failed")
        external = str(profile.get("id") or profile.get("sub") or "")
        if not external:
            return RedirectResponse(f"{home}?login=failed")
        row = self.users.by_provider(provider, external)
        if row is None:
            wanted = profile.get("login") or profile.get("name") or (profile.get("email") or "").split("@")[0]
            user_id = self.users.create(self.users.free_name(wanted), **{f"{provider}_id": external})
        else:
            user_id = row["id"]
        response = RedirectResponse(home)
        response.delete_cookie(STATE_COOKIE, path=visitors.cookie_path())
        return self._sign_in(response, request, user_id)
