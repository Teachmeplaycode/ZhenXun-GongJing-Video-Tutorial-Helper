"""小红书 comments, read the way a logged-in browser reads them.

The comment API (edith.xiaohongshu.com …/comment/page) wants request signatures computed by the
page's own scripts, and a logged-out visitor is sent from the note to /login. So a headless browser
carrying the user's cookie (XHS_COOKIE, pasted in 账号) opens the note, and the comment pages the
page itself requests are captured; scrolling the note's panel loads the next ones.

One browser visit per note collects up to MAX_PAGES pages, kept for CACHE_TTL; the agent's
read_comments pages through them.
"""
from __future__ import annotations

import asyncio
import time

from ..settings import settings
from .base import Comment, CommentPage, ResolveError
from .post_text import clean

MAX_PAGES = 3          # pages of top-level comments per visit (about 10 each)
# Seconds for the first page. From this machine the page's security check (as.xiaohongshu.com) hangs
# about 20 s before giving up, and only then does the page load its comments (~28 s in all).
WAIT = 45.0
SCROLL_WAIT = 4.0      # seconds for each further page
CACHE_TTL = 600
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
LOGIN = "小红书评论要登录才能读：在右上角「账号」里粘贴小红书的 Cookie"

_cache: dict[str, tuple[float, list[CommentPage]]] = {}


def cookies_of(cookie: str) -> list[dict]:
    out = []
    for part in cookie.split(";"):
        name, _, value = part.strip().partition("=")
        if name and value:
            out.append({"name": name, "value": value, "domain": ".xiaohongshu.com", "path": "/"})
    return out


def _int(value) -> int:
    s = str(value or "").strip()
    try:
        return round(float(s[:-1]) * 10000) if s.endswith("万") else int(s or 0)
    except ValueError:
        return 0


def to_comment(c: dict) -> Comment:
    user = c.get("user_info") or {}
    return Comment(
        author=user.get("nickname") or "",
        text=clean(c.get("content") or ""),  # sticker codes ([皱眉R]) and topic marks out
        likes=_int(c.get("like_count")),
        reply_count=_int(c.get("sub_comment_count")),
        time=(c.get("create_time") or 0) / 1000,
        pinned=any((t == "is_author") or (isinstance(t, dict) and t.get("type") == "is_author") for t in c.get("show_tags") or []),
        replies=[to_comment(s) for s in (c.get("sub_comments") or [])[:3]],
    )


def to_pages(raw: list[dict], total: int | None) -> list[CommentPage]:
    """The captured responses' data → pages; each page's cursor names the next one ("1", "2" …)."""
    pages = []
    for i, data in enumerate(raw):
        more = i + 1 < len(raw)
        note = "" if more or not data.get("has_more") else f"小红书一次只读前 {len(raw)} 页评论"
        pages.append(CommentPage([to_comment(c) for c in data.get("comments") or []], total,
                                 str(i + 1) if more else None, note))
    return pages


async def _visit(url: str, cookie: str) -> list[CommentPage]:
    from ..agent import browser

    if not browser.available():
        raise ResolveError("unsupported", "读小红书评论需要浏览器：在 backend 里运行 uv run playwright install --only-shell chromium")
    context = await (await browser.browser()).new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN", user_agent=UA)
    raw: list[dict] = []
    arrived = asyncio.Event()

    async def on_response(resp):
        if "/comment/page" not in resp.url:
            return
        try:
            body = await resp.json()
        except Exception:
            return
        if body.get("success") and isinstance(body.get("data"), dict):
            raw.append(body["data"])
            arrived.set()

    try:
        await context.add_cookies(cookies_of(cookie))
        page = await context.new_page()
        page.on("response", on_response)
        await page.goto(url, wait_until="commit", timeout=20_000)  # the page's scripts may take a while
        if "/login" in page.url or "/404" in page.url:
            raise ResolveError("login_required", "小红书登录已失效或这条笔记打不开：请在「账号」里重新粘贴 Cookie")
        try:
            await asyncio.wait_for(arrived.wait(), WAIT)
        except asyncio.TimeoutError:
            raise ResolveError("upstream", "小红书没有返回评论（可能需要重新登录，或评论区已关闭）") from None
        while len(raw) < MAX_PAGES and raw[-1].get("has_more"):
            arrived.clear()
            await page.evaluate("document.querySelector('.note-scroller')?.scrollBy(0, 100000)")
            try:
                await asyncio.wait_for(arrived.wait(), SCROLL_WAIT)
            except asyncio.TimeoutError:
                break
        total = None
        try:
            text = await page.locator(".comments-container .total").first.inner_text(timeout=1000)
            total = _int("".join(ch for ch in text if ch.isdigit() or ch in ".万")) or None
        except Exception:
            pass
        return to_pages(raw, total)
    finally:
        await context.close()


async def comments(url: str, cursor: str | None = None) -> CommentPage:
    cookie = settings().get("XHS_COOKIE", "").strip()
    if not cookie:
        raise ResolveError("login_required", LOGIN)
    hit = _cache.get(url)
    if not hit or time.time() - hit[0] > CACHE_TTL:
        hit = _cache[url] = (time.time(), await _visit(url, cookie))
    pages = hit[1]
    index = int(cursor) if cursor and cursor.isdigit() else 0
    if not pages:
        return CommentPage([], 0, None, "这条笔记还没有评论")
    return pages[min(index, len(pages) - 1)]
