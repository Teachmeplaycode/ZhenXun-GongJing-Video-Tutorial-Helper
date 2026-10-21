"""Settings from the environment, falling back to `backend/.env` (real environment variables win)."""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
# Logins saved from the UI (modules/accounts). A separate file, because dev.sh restarts the backend
# whenever .env changes, which would cut off answers in progress.
ACCOUNTS_FILE = ENV_FILE.with_name(".env.accounts")


def parse_assignment(line: str) -> tuple[str, str]:
    """`[export ]NAME=value` with optional quotes → (NAME, value); a bare value gives ("", value)."""
    name, sep, value = line.removeprefix("export ").partition("=")
    if not sep:
        name, value = "", name
    return name.strip(), value.strip().strip("'\"")


def read_env_file(path: Path) -> dict[str, str]:
    """Minimal .env reader: NAME=value lines, `#` comments; no variable expansion."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return {}
    pairs = (parse_assignment(line.strip()) for line in lines if "=" in line and not line.strip().startswith("#"))
    return {name: value for name, value in pairs if name}


# The web demo sets these per request (app.py): `overlay` holds the signed-in person's own platform
# logins and blanks out everyone else's; `vault` is where a new login of theirs is saved instead of
# .env.accounts (modules/members.py). Unset locally.
overlay: ContextVar[dict | None] = ContextVar("settings_overlay", default=None)
vault: ContextVar[object | None] = ContextVar("settings_vault", default=None)


def cn_proxy() -> str | None:
    """CN_PROXY: an HTTP proxy in mainland China for the platforms that turn away overseas servers
    (小红书, 元宝 / 视频号 …); None when unset, e.g. on a machine that is in mainland China already."""
    return settings().get("CN_PROXY", "").strip() or None


# Hosts of mainland platforms whose pages, APIs and video CDNs are steadier from a mainland address:
# with CN_PROXY set, requests to them (resolving, ffmpeg reading streams, playback relay) go through it.
# B 站 is left out: it serves the overseas server well, and the proxy's bandwidth is better spent
# elsewhere. CN_PROXY_HOSTS (comma-separated domains) replaces the list.
MAINLAND_HOSTS = (
    "douyin.com", "iesdouyin.com", "douyinvod.com", "douyinpic.com", "douyinstatic.com", "zjcdn.com", "snssdk.com",
    "amemv.com", "bytecdn.cn", "byteimg.com", "ixigua.com",
    "xiaohongshu.com", "xhscdn.com", "xhslink.com",
    "kuaishou.com", "kwaicdn.com", "yximgs.com", "gifshow.com", "chenzhongtech.com", "kuaishouzt.com",
    "weixin.qq.com", "finder.video.qq.com", "channels.weixin.qq.com",
    "weibo.com", "weibo.cn", "sinaimg.cn", "miaopai.com", "youku.com", "iqiyi.com", "acfun.cn", "zhihu.com",
)


def mainland_proxy(url: str) -> str | None:
    """CN_PROXY when `url` is on a mainland platform's host (and the proxy is set), else None."""
    proxy = cn_proxy()
    if not proxy or "://" not in (url or ""):
        return None
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    custom = settings().get("CN_PROXY_HOSTS", "").strip()
    hosts = [h.strip().lower() for h in custom.split(",") if h.strip()] if custom else MAINLAND_HOSTS
    return proxy if any(host == h or host.endswith("." + h) for h in hosts) else None


def settings() -> dict[str, str]:
    """Read on every call so an edited .env applies to the next request.

    Precedence: .env < .env.accounts (logins from the UI) < real environment variables < the
    request's overlay (the web demo: this person's own logins).
    """
    return {**read_env_file(ENV_FILE), **read_env_file(ACCOUNTS_FILE), **os.environ, **(overlay.get() or {})}
