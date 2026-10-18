"""Douyin (抖音) resolver: expands short links and parses the share page (address-only).

v.douyin.com/<code>/ redirects to www.douyin.com/video/<id>. The share page embeds the aweme in
`window._ROUTER_DATA` (or RENDER_DATA); we read the play_addr url (rewriting the watermarked playwm
to play). Douyin signs its web API, so we parse the public HTML rather than calling the signed
aweme/detail endpoint. Login-gated or region-restricted videos map to a clear ResolveError.
"""
from __future__ import annotations

import json
import re
import urllib.parse

import httpx

from .base import ResolveError, ResolvedVideo, Resolver, Stream

USER_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")
HOSTS = {"douyin.com", "www.douyin.com", "v.douyin.com", "iesdouyin.com", "www.iesdouyin.com"}
SHORT_HOSTS = {"v.douyin.com", "www.iesdouyin.com", "iesdouyin.com"}
VIDEO_RE = re.compile(r"/video/(\d+)")
NOTE_RE = re.compile(r"/note/(\d+)")


def parse_target(url: str) -> tuple[str, str | None]:
    """Return (kind, id) from a Douyin URL; kind is 'video', 'note' or 'short' (code only)."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path or ""
    m = VIDEO_RE.search(path)
    if m:
        return "video", m.group(1)
    m = NOTE_RE.search(path)
    if m:
        return "note", m.group(1)
    if host in SHORT_HOSTS and path.strip("/"):
        return "short", path.strip("/").split("/")[0]
    raise ResolveError("unsupported_link", "链接里没有找到抖音视频编号")


def _extract_share_data(html: str) -> dict:
    """Find window._ROUTER_DATA (or RENDER_DATA) and decode it depth-aware."""
    html = html or ""
    marker = "window._ROUTER_DATA"
    idx = html.find(marker)
    if idx < 0:
        idx = html.find("RENDER_DATA")
    if idx < 0:
        raise ResolveError("upstream", "抖音页面里没有找到视频信息，可能结构已变化", retryable=True)
    eq = html.find("=", idx)
    if eq < 0:
        raise ResolveError("upstream", "抖音页面里没有找到视频信息，可能结构已变化", retryable=True)
    start = eq + 1
    while start < len(html) and html[start] in " \t\n\r":
        start += 1
    # RENDER_DATA is sometimes a URI-encoded JSON string in quotes.
    if start < len(html) and html[start] == '"':
        end = html.find('"', start + 1)
        raw = html[start + 1:end] if end > 0 else html[start + 1:]
        try:
            raw = urllib.parse.unquote(raw)
        except Exception:
            pass
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw)
            return obj
        except ValueError:
            raise ResolveError("upstream", "抖音页面的视频信息无法解析", retryable=True) from None
    if start >= len(html) or html[start] != "{":
        raise ResolveError("upstream", "抖音页面里没有找到视频信息，可能结构已变化", retryable=True)
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
    except ValueError:
        raise ResolveError("upstream", "抖音页面的视频信息无法解析", retryable=True) from None
    return obj


def _find_aweme(blob: dict) -> dict | None:
    """Walk the parsed share data looking for the aweme block that carries a video play_addr."""
    stack = [blob]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            video = cur.get("video")
            if isinstance(video, dict) and ("play_addr" in video or "bit_rate" in video):
                if "aweme_id" in cur or "desc" in cur or "author" in cur:
                    return cur
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _urls_from_play_addr(play: dict) -> list[str]:
    urls: list[str] = []
    for key in ("url_list", "download_addr_list"):
        for item in (play.get(key) or []):
            u = item.get("url") if isinstance(item, dict) else item
            if u:
                urls.append(u.replace("playwm", "play"))
    return urls


def parse_share_data(raw: str, video_id: str, headers: dict[str, str]) -> ResolvedVideo:
    """Pure parse of a Douyin share page → ResolvedVideo (no network)."""
    blob = _extract_share_data(raw)
    aweme = _find_aweme(blob)
    if not aweme:
        raise ResolveError("not_found", "抖音内容不存在、已删除或仅作者可见")
    video = aweme.get("video") or {}
    urls = _urls_from_play_addr(video.get("play_addr") or {})
    if not urls:
        for br in (video.get("bit_rate") or []):
            urls += _urls_from_play_addr(br.get("play_addr") or {})
    if not urls:
        raise ResolveError("no_stream", "抖音没有返回可读取的视频地址", retryable=True)
    streams = [Stream(u, headers, f"douyin-{i}") for i, u in enumerate(urls[:3])]
    duration = float(video.get("duration") or 0) / 1000.0
    if duration <= 0:
        raise ResolveError("upstream", "无法确定视频时长", retryable=True)
    author = (aweme.get("author") or {}).get("nickname") or ""
    desc = aweme.get("desc") or ""
    title = desc.split("#")[0].strip()[:60] or f"抖音视频 {video_id}"
    cover = ((video.get("cover") or {}).get("url_list") or [""])[0]
    canonical = f"https://www.douyin.com/video/{video_id}"
    stats = aweme.get("statistics") or {}
    return ResolvedVideo(
        platform="douyin", video_id=video_id, canonical_url=canonical, title=title,
        duration=duration, streams=streams, cover=cover, author=author, description=desc,
        audio_streams=streams, extra={"stats": {"likes": stats.get("digg_count")}},
    )


class DouyinResolver(Resolver):
    platform = "douyin"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 15) -> None:
        self._transport = transport
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Referer": "https://www.douyin.com/"}

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=self._timeout,
                                             follow_redirects=True, transport=self._transport)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def matches(self, url: str) -> bool:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        return host in HOSTS or host.endswith(".douyin.com")

    async def _expand(self, url: str) -> str:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if host not in SHORT_HOSTS:
            return url
        try:
            response = await self._http().get(url)
        except httpx.TimeoutException:
            raise ResolveError("timeout", "连接抖音超时，请检查网络后重试", retryable=True) from None
        except httpx.HTTPError:
            raise ResolveError("network", "无法连接抖音，请检查网络后重试", retryable=True) from None
        final = str(response.url)
        if not VIDEO_RE.search(final):
            raise ResolveError("unsupported_link", "抖音短链接没有指向视频页面")
        return final

    async def resolve(self, url: str, part: int | None = None) -> ResolvedVideo:
        url = await self._expand(url)
        kind, ident = parse_target(url)
        if kind == "note":
            raise ResolveError("unsupported_content", "这是抖音图文，不是视频")
        if kind != "video" or not ident:
            raise ResolveError("unsupported_link", "链接里没有找到抖音视频编号")
        try:
            response = await self._http().get(f"https://www.douyin.com/video/{ident}")
        except httpx.TimeoutException:
            raise ResolveError("timeout", "连接抖音超时，请检查网络后重试", retryable=True) from None
        except httpx.HTTPError:
            raise ResolveError("network", "无法连接抖音，请检查网络后重试", retryable=True) from None
        if response.status_code == 404:
            raise ResolveError("not_found", "视频不存在或已被删除")
        if response.status_code >= 500:
            raise ResolveError("upstream", f"抖音返回了错误（HTTP {response.status_code}）", retryable=True)
        return parse_share_data(response.text, ident, self.headers)
