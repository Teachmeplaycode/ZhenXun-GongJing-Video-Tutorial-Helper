"""Who is asking, when the app runs as a public web demo (PUBLIC_DEMO=1).

Locally the app has one user and nothing here applies. As a public demo each browser gets an
anonymous visitor id in a signed cookie, and a session belongs to the visitor who created it:
nobody else can list, open, question or delete it (another visitor's id answers 404, as if it
did not exist). Platform logins are the owner's own accounts, so they are closed to visitors,
and only the platforms in PUBLIC_PLATFORMS (default: Bilibili and uploads) can be imported.

  PUBLIC_DEMO        1 / true / on turns the demo mode on
  PUBLIC_PLATFORMS   comma-separated platforms visitors may import (bilibili,local)
  VISITOR_SECRET     key signing the cookie; without it one is made and kept in the data folder
  PUBLIC_PATH        the path the app is served under (e.g. /GongJing), so the cookie stays with it
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from contextvars import ContextVar
from pathlib import Path

from fastapi import HTTPException

COOKIE = "fj_visitor"
MAX_AGE = 180 * 24 * 3600
SECRET_FILE = "visitor_secret"
NAMES = {"bilibili": "B站", "local": "本地上传", "wechat_channels": "视频号", "alcedo": "小红书、抖音等"}

current: ContextVar[str] = ContextVar("visitor", default="")


def enabled() -> bool:
    return os.environ.get("PUBLIC_DEMO", "").strip().lower() in ("1", "true", "on", "yes")


def cookie_path() -> str:
    return "/" + os.environ.get("PUBLIC_PATH", "").strip("/ ")


def platforms() -> set[str]:
    raw = os.environ.get("PUBLIC_PLATFORMS", "bilibili,local")
    return {p.strip() for p in raw.split(",") if p.strip()}


_keys: dict[Path, bytes] = {}


def secret(root: Path) -> bytes:
    """VISITOR_SECRET, else a random key kept in `root` so cookies outlive a restart."""
    if root not in _keys:
        _keys[root] = _load(root)
    return _keys[root]


def _load(root: Path) -> bytes:
    if key := os.environ.get("VISITOR_SECRET", "").strip():
        return key.encode()
    path = root / SECRET_FILE
    try:
        return path.read_bytes()
    except OSError:
        root.mkdir(parents=True, exist_ok=True)
        key = secrets.token_hex(32).encode()
        path.write_bytes(key)
        path.chmod(0o600)
        return key


def new() -> str:
    return secrets.token_hex(12)


def sign(visitor: str, key: bytes) -> str:
    return f"{visitor}.{hmac.new(key, visitor.encode(), hashlib.sha256).hexdigest()[:32]}"


def verify(value: str | None, key: bytes) -> str | None:
    visitor, _, mac = (value or "").partition(".")
    if not visitor or not mac:
        return None
    return visitor if hmac.compare_digest(sign(visitor, key), value) else None


def owner() -> str:
    """The id a new session is saved under: the visitor in demo mode, '' locally."""
    return current.get() if enabled() else ""


def may_see(session_owner: str | None) -> bool:
    if not enabled():
        return True
    return session_owner is not None and session_owner == current.get() != ""


def check_platform(platform: str) -> None:
    if enabled() and platform not in platforms():
        allowed = "、".join(NAMES.get(p, p) for p in sorted(platforms())) or "无"
        raise HTTPException(403, f"演示版只支持这些来源：{allowed}")


def check_accounts() -> None:
    if enabled():
        raise HTTPException(403, "演示版不开放平台账号设置")
