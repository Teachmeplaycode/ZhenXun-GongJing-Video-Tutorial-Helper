"""Douyin (抖音) resolver: expands short links and parses the share page (address-only).

v.douyin.com/<code>/ redirects to www.douyin.com/video/<id>. The share page embeds the aweme either
in `<script id="RENDER_DATA">URL-encoded JSON</script>` (current) or `window._ROUTER_DATA = {...}`
(legacy); we read the play_addr url (rewriting the watermarked playwm to play). Douyin signs its web
API, so we parse the public HTML rather than calling the signed aweme/detail endpoint. Login-gated,
region-restricted, throttled and deleted videos map to a clear ResolveError.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from html.parser import HTMLParser

import httpx

from .base import ResolveError, ResolvedVideo, Resolver, Stream

USER_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")
HOSTS = {"douyin.com", "www.douyin.com", "v.douyin.com", "iesdouyin.com", "www.iesdouyin.com"}
SHORT_HOSTS = {"v.douyin.com", "www.iesdouyin.com", "iesdouyin.com"}
VIDEO_RE = re.compile(r"/video/(\d+)")
NOTE_RE = re.compile(r"/note/(\d+)")


class _RenderDataParser(HTMLParser):
    """Read the actual script body, regardless of attribute order, case or whitespace."""

    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] | None = None
        self.capture = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "RENDER_DATA" and self.chunks is None:
            self.chunks = []
            self.capture = True

    def handle_data(self, data: str) -> None:
        if self.capture and self.chunks is not None:
            self.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.capture = False


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
    """Find the aweme JSON.

    Current pages embed it as URL-encoded JSON in `<script id="RENDER_DATA" type="application/json">`;
    legacy pages assign `window._ROUTER_DATA = {...}`. Both are handled, depth-aware.
    """
    html = html or ""
    parser = _RenderDataParser()
    parser.feed(html)
    if parser.chunks is not None:
        raw = urllib.parse.unquote("".join(parser.chunks).strip())
        try:
            return json.loads(raw)
        except ValueError:
            raise ResolveError("upstream", "抖音页面的视频信息无法解析", retryable=True) from None
    idx = html.find("window._ROUTER_DATA")
    if idx >= 0:
        eq = html.find("=", idx)
        if eq >= 0:
            start = eq + 1
            while start < len(html) and html[start] in " \t\n\r":
                start += 1
            if start < len(html) and html[start] == "{":
                try:
                    obj, _ = json.JSONDecoder().raw_decode(html[start:])
                    return obj
                except ValueError:
                    raise ResolveError("upstream", "抖音页面的视频信息无法解析", retryable=True) from None
    raise ResolveError("upstream", "抖音页面里没有找到视频信息，可能结构已变化", retryable=True)


def _find_aweme(blob: dict, video_id: str) -> dict | None:
    """Walk the parsed share data looking for the aweme block that carries a video play_addr."""
    stack = [blob]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            video = cur.get("video")
            if isinstance(video, dict) and ("play_addr" in video or "bit_rate" in video):
                if str(cur.get("aweme_id", "")) == video_id:
                    return cur
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _scan_status(blob: dict) -> list[tuple[int | None, str, bool]]:
    """Collect statuses; a successful outer envelope must not hide a nested restriction."""
    statuses = []
    stack = [blob]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            raw_code = cur.get("status_code")
            try:
                code = int(raw_code) if raw_code is not None and not isinstance(raw_code, bool) else None
            except (TypeError, ValueError, OverflowError):
                code = None
            messages = [cur.get(key) for key in ("status_msg", "status_info")]
            msg = " ".join(value for value in messages if isinstance(value, str))
            statuses.append((code, msg, bool(cur.get("filter_list"))))
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return statuses


def _raise_missing(blob: dict) -> None:
    """A decoded page without an aweme is not always not_found: read the explicit status first."""
    statuses = _scan_status(blob)
    codes = {code for code, _, _ in statuses}
    message = " ".join(msg for _, msg, _ in statuses).lower()
    if 8 in codes or any(k in message for k in ("登录", "login")):
        raise ResolveError("login_required", "需要登录抖音才能观看这个内容")
    if (2095 in codes or any(filtered for _, _, filtered in statuses)
            or any(k in message for k in ("地区", "区域", "region", "country", "访问限制", "访问受限"))):
        raise ResolveError("forbidden", "该内容有地区或访问限制，当前无法观看")
    if codes.intersection({2049, 2100}) or any(k in message for k in ("已删除", "不存在", "已失效", "下架", "deleted", "not found")):
        raise ResolveError("not_found", "抖音内容不存在或已删除")
    raise ResolveError("upstream", "抖音页面结构无法识别，请稍后重试", retryable=True)


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
    aweme = _find_aweme(blob, video_id)
    if not aweme:
        _raise_missing(blob)
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


def _http_error(status: int) -> ResolveError | None:
    """Map an HTTP status from a share/redirect response to a clear ResolveError (else None)."""
    if status == 401:
        return ResolveError("login_required", "抖音需要登录后才能观看该内容")
    if status == 403:
        return ResolveError("forbidden", "该内容在当前地区或条件下受限，无法观看")
    if status == 429:
        return ResolveError("rate_limited", "请求过于频繁，请稍后重试", retryable=True)
    return None


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
        err = _http_error(response.status_code)
        if err:
            raise err
        final = str(response.url)
        if not (VIDEO_RE.search(final) or NOTE_RE.search(final)):
            raise ResolveError("unsupported_link", "抖音短链接没有指向视频或图文页面")
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
        err = _http_error(response.status_code)
        if err:
            raise err
        if response.status_code == 404:
            raise ResolveError("not_found", "视频不存在或已被删除")
        if response.status_code >= 500:
            raise ResolveError("upstream", f"抖音返回了错误（HTTP {response.status_code}）", retryable=True)
        return parse_share_data(response.text, ident, self.headers)
