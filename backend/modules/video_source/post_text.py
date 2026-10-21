"""The text of a post that alcedo leaves out: the body (正文), its topics and the interaction counts.

alcedo returns a post's title, author and media but not what the author wrote under it — for a
小红书 图文 that is often most of the content. The note page carries it in window.__INITIAL_STATE__
(readable without a login while the link's xsec_token is fresh; XHS_COOKIE is sent when set).
Best effort: any failure leaves the post as alcedo described it.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import httpx

from ..settings import cn_proxy, settings

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")
TIMEOUT = 15.0
MAX_CHARS = 6000
STATE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>", re.S)
EMOJI = re.compile(r"\[[^\[\]\s]{1,8}[RH]\]")          # 小红书 sticker codes: [笑哭R] [赞H]
TOPIC = re.compile(r"#([^#\[\]\n]{1,40})\[话题\]#")    # #催眠麦克风[话题]# → #催眠麦克风


def js_to_json(text: str) -> str:
    """The page's state is a JS literal: undefined, and (logged in) empty `new Map([])` / `new Set([])`."""
    text = re.sub(r"\bnew Map\(\[\]\)", "{}", re.sub(r"\bnew Set\(\[\]\)", "[]", text))
    return re.sub(r"\bundefined\b", "null", text)


def is_xiaohongshu(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host.endswith("xiaohongshu.com") or host.endswith("xhslink.com")


def clean(text: str) -> str:
    text = TOPIC.sub(r"#\1", EMOJI.sub("", text or ""))
    return re.sub(r"[ \t]+\n", "\n", text).strip()[:MAX_CHARS]


def _count(value) -> int | None:
    """'174' → 174, '1.2万' → 12000, '' → None."""
    s = str(value or "").strip()
    try:
        return round(float(s[:-1]) * 10000) if s.endswith("万") else int(s) if s else None
    except ValueError:
        return None


def parse_note(html: str) -> dict | None:
    """The note on a 小红书 page: {desc, tags, stats, ip}; None if the page doesn't carry one."""
    m = STATE.search(html)
    if not m:
        return None
    try:
        state = json.loads(js_to_json(m.group(1)))
        notes = state["note"]["noteDetailMap"]
    except (ValueError, KeyError, TypeError):
        return None
    for entry in (notes or {}).values():
        note = (entry or {}).get("note") or {}
        if not note.get("noteId"):
            continue
        info = note.get("interactInfo") or {}
        stats = {k: _count(info.get(src)) for k, src in
                 (("likes", "likedCount"), ("favorites", "collectedCount"), ("comments", "commentCount"), ("shares", "shareCount"))}
        return {
            "desc": clean(note.get("desc") or ""),
            "tags": [t["name"] for t in note.get("tagList") or [] if t.get("name")][:12],
            "stats": {k: v for k, v in stats.items() if v is not None},
            "ip": note.get("ipLocation") or "",
        }
    return None


async def fetch(url: str) -> dict | None:
    if not is_xiaohongshu(url):
        return None
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.xiaohongshu.com/"}
    cookie = settings().get("XHS_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, proxy=cn_proxy()) as client:
            r = await client.get(url, headers=headers)
        return parse_note(r.text) if r.status_code == 200 else None
    except httpx.HTTPError:
        return None
