"""Access code and accounts for the public web demo (only when PUBLIC_DEMO is on).

  ACCESS_CODES   comma-separated codes. When set, a browser enters one once before it can use the
                 app (a signed cookie remembers it); signing in to an account also lets it in.

An account is a name and a password (scrypt). Signing up or in makes the browser's visitor id
"u<account id>", and the sessions that browser made anonymously move to the account, so the same
history shows on every browser the person signs in on. Signing out gives the browser a fresh
anonymous id. Accounts live in their own SQLite file next to the sessions database.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules import visitors

ACCESS_COOKIE = "fj_access"
ACCESS_TOKEN = "access"
NAME = re.compile(r"^[\w一-鿿-]{2,20}$")
MIN_PASSWORD = 6
TRIES, WINDOW = 10, 600  # wrong codes or passwords per address per window (seconds)
OPEN = {"/api/health", "/api/access", "/api/auth/login"}  # reachable before the access code

granted: ContextVar[bool] = ContextVar("access_granted", default=False)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password TEXT NOT NULL,          -- scrypt$<salt hex>$<hash hex>
  created REAL NOT NULL
);
"""


def codes() -> set[str]:
    return {c.strip() for c in os.environ.get("ACCESS_CODES", "").split(",") if c.strip()}


def required() -> bool:
    return visitors.enabled() and bool(codes())


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


class Users:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def create(self, name: str, password: str) -> int:
        with self.db:
            return self.db.execute("INSERT INTO users (name, password, created) VALUES (?, ?, ?)",
                                   (name, hash_password(password), time.time())).lastrowid

    def find(self, name: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()

    def name(self, user_id: int) -> str | None:
        row = self.db.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None


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


class Code(BaseModel):
    code: str


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
        self.router.add_api_route("/api/access", self.access, methods=["POST"])
        self.router.add_api_route("/api/auth/register", self.register, methods=["POST"])
        self.router.add_api_route("/api/auth/login", self.login, methods=["POST"])
        self.router.add_api_route("/api/auth/logout", self.logout, methods=["POST"])

    @property
    def users(self) -> Users:
        path = self.path()
        if path not in self._users:
            self._users[path] = Users(path)
        return self._users[path]

    # ---- middleware ---------------------------------------------------------------------
    def has_access(self, request: Request, visitor: str) -> bool:
        if account_of(visitor) is not None:
            return True
        return visitors.verify(request.cookies.get(ACCESS_COOKIE), self.key()) == ACCESS_TOKEN

    def gate(self, request: Request) -> JSONResponse | None:
        """The 401 a request gets before the access code, or None when it may go on."""
        if not required() or granted.get() or not request.url.path.startswith("/api/") or request.url.path in OPEN:
            return None
        return JSONResponse({"detail": "请先输入访问码", "code": "access_required"}, status_code=401)

    def status(self) -> dict:
        """What /api/health adds: whether a code is needed, whether this browser is in, who is signed in."""
        user_id = account_of(visitors.current.get())
        return {"access_required": required(), "access_granted": granted.get(),
                "user": {"name": self.users.name(user_id)} if user_id is not None else None}

    # ---- routes -------------------------------------------------------------------------
    def _cookie(self, response: JSONResponse, request: Request, name: str, value: str) -> None:
        response.set_cookie(name, visitors.sign(value, self.key()), max_age=visitors.MAX_AGE, path=visitors.cookie_path(),
                            httponly=True, samesite="lax", secure=request.url.scheme == "https")

    def _enabled(self) -> None:
        if not visitors.enabled():
            raise HTTPException(404, "本机版没有账号")

    async def access(self, body: Code, request: Request):
        self._enabled()
        self.limiter.check(address(request))
        if body.code.strip() not in codes():
            self.limiter.fail(address(request))
            raise HTTPException(403, "访问码不对")
        response = JSONResponse({"ok": True})
        self._cookie(response, request, ACCESS_COOKIE, ACCESS_TOKEN)
        return response

    def _signed_in(self, request: Request, user_id: int) -> JSONResponse:
        """Move this browser's anonymous sessions to the account and make it the visitor id."""
        current = visitors.current.get()
        if account_of(current) is None and current:
            self.claim(current, f"u{user_id}")
        response = JSONResponse({"ok": True, "user": {"name": self.users.name(user_id)}})
        self._cookie(response, request, visitors.COOKIE, f"u{user_id}")
        self._cookie(response, request, ACCESS_COOKIE, ACCESS_TOKEN)
        return response

    async def register(self, body: Credentials, request: Request):
        self._enabled()
        if required() and not granted.get():
            raise HTTPException(401, "请先输入访问码")
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
        if row is None or not check_password(body.password, row["password"]):
            self.limiter.fail(key)
            raise HTTPException(403, "用户名或密码不对")
        return self._signed_in(request, row["id"])

    async def logout(self, request: Request):
        self._enabled()
        response = JSONResponse({"ok": True})
        self._cookie(response, request, visitors.COOKIE, visitors.new())  # a fresh anonymous browser
        return response
