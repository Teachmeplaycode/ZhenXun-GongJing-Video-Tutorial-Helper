"""YouTube resolver: parses the watch page's ytInitialPlayerResponse (address-only, never downloads).

YouTube has no anonymous play-url API like Bilibili; the watch page embeds the player response with
streamingData. Addresses that carry a signatureCipher (the `s` signature) or an untransformed `n`
throttling parameter are NOT readable as-is and are skipped — we do not implement the player's
changing client-side decipher, so a video whose only addresses need it reports no_stream.
Login-gated / region-restricted / private videos are mapped
from playabilityStatus to a clear ResolveError.
"""
from __future__ import annotations

import json
import re
import urllib.parse

import httpx

from .base import ResolveError, ResolvedVideo, Resolver, Stream

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
WATCH = "https://www.youtube.com/watch"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
# playabilityStatus → (code, message)
PLAYABILITY_ERRORS = {
    "UNPLAYABLE": ("unavailable", "这个视频暂时无法播放（可能地区限制或格式问题）"),
    "LOGIN_REQUIRED": ("login_required", "需要登录 YouTube 才能观看这个视频"),
    "AGE_CHECK_REQUIRED": ("login_required", "这个视频需要登录并确认年龄才能观看"),
    "AGE_VERIFICATION_REQUIRED": ("login_required", "这个视频需要完成年龄验证才能观看"),
    "PRIVATE": ("forbidden", "这是私密视频，无法观看"),
    "MEMBERS_ONLY": ("forbidden", "这是会员专属视频，无法观看"),
    "PREMIERE": ("unavailable", "这是首播，尚未开始或已结束"),
    "LIVE_STREAM_OFFLINE": ("unavailable", "直播未开始或已结束"),
    "ERROR": ("upstream", "YouTube 报告这个视频有错误"),
}


def parse_target(url: str) -> str:
    """Return the 11-char video id from a YouTube URL (watch/shorts/embed/youtu.be)."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path or ""
    query = urllib.parse.parse_qs(parts.query)
    if host == "youtu.be":
        vid = path.strip("/")
    elif "/shorts/" in path or "/embed/" in path:
        vid = path.rsplit("/", 1)[-1]
    else:
        vid = (query.get("v", [""])[0] or "").strip()
    vid = vid.split("?")[0].split("&")[0]
    if not VIDEO_ID_RE.match(vid):
        raise ResolveError("unsupported_link", "链接里没有找到有效的 YouTube 视频编号")
    return vid


def _extract_player_response(html: str) -> dict:
    """Find ytInitialPlayerResponse and decode it with a depth-aware JSON reader (handles nesting)."""
    marker = "ytInitialPlayerResponse"
    idx = (html or "").find(marker)
    if idx < 0:
        raise ResolveError("upstream", "YouTube 页面里没有找到播放信息，可能结构已变化", retryable=True)
    eq = html.find("=", idx)
    if eq < 0:
        raise ResolveError("upstream", "YouTube 页面里没有找到播放信息，可能结构已变化", retryable=True)
    start = eq + 1
    while start < len(html) and html[start] in " \t\n\r":
        start += 1
    if start >= len(html) or html[start] != "{":
        raise ResolveError("upstream", "YouTube 页面里没有找到播放信息，可能结构已变化", retryable=True)
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
    except ValueError:
        raise ResolveError("upstream", "YouTube 页面的播放信息无法解析", retryable=True) from None
    return obj


def _has_n(fmt: dict) -> bool:
    """True when the address still carries the `n` throttling parameter (needs a transform to read)."""
    url = fmt.get("url") or ""
    return "n" in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query, keep_blank_values=True)


def _needs_decipher(fmt: dict) -> bool:
    """True when the address is signed (`s`) or carries an untransformed `n`: not readable as-is."""
    return bool(fmt.get("signatureCipher") or fmt.get("cipher")) or _has_n(fmt)


def _stream_from_format(fmt: dict, headers: dict[str, str], kind: str) -> Stream | None:
    # Never hand out an address that is guaranteed to be refused: skip signed / n-throttled formats.
    if _needs_decipher(fmt):
        return None
    url = fmt.get("url")
    if not url:
        return None
    label = f"{kind}-{fmt.get('itag', '?')}-{fmt.get('qualityLabel') or fmt.get('quality', '')}"
    height = int(fmt.get("height") or 0)
    return Stream(url, headers, label, height)


def parse_player_response(payload: dict, video_id: str, headers: dict[str, str]) -> ResolvedVideo:
    """Pure parse of ytInitialPlayerResponse → ResolvedVideo (no network)."""
    playability = (payload.get("playabilityStatus") or {})
    status = playability.get("status", "")
    if status != "OK":
        err = PLAYABILITY_ERRORS.get(status)
        if err:
            raise ResolveError(*err)
        reason = playability.get("reason") or playability.get("messages") or ""
        raise ResolveError("unavailable", f"这个视频无法播放：{reason}" if reason else "这个视频无法播放")
    details = payload.get("videoDetails") or {}
    streaming = payload.get("streamingData") or {}
    duration = float(details.get("lengthSeconds") or streaming.get("lengthSeconds") or 0)
    if duration <= 0:
        raise ResolveError("upstream", "无法确定视频时长", retryable=True)
    streams: list[Stream] = []
    muxed: list[Stream] = []
    for fmt in (streaming.get("formats") or []):
        s = _stream_from_format(fmt, headers, "muxed")
        if s:
            streams.append(s)
            muxed.append(s)
    audio: list[Stream] = []
    for fmt in (streaming.get("adaptiveFormats") or []):
        s = _stream_from_format(fmt, headers, "adaptive")
        if not s:
            continue
        mime = (fmt.get("mimeType") or "").lower()
        if "audio" in mime:
            audio.append(s)
        elif "video" in mime and not streams:
            streams.append(s)
    if not streams:
        raise ResolveError("no_stream", "没有拿到可直接读取的播放地址（地址可能需要签名或 n 变换解码）", retryable=True)
    # Muxed formats already contain the audio: fall back to them when the video has no adaptive audio
    # track so transcription has something to read. A video-only adaptive stream is never used as audio.
    if not audio:
        audio = list(muxed)
    notes: list[str] = []
    all_fmts = (streaming.get("formats") or []) + (streaming.get("adaptiveFormats") or [])
    skipped = sum(1 for fmt in all_fmts if _needs_decipher(fmt))
    if skipped:
        notes.append(f"{skipped} 个地址需要签名或 n 变换解码，已跳过")
    canonical = f"https://www.youtube.com/watch?v={video_id}"
    thumbs = (details.get("thumbnail") or {}).get("thumbnails") or [{}]
    return ResolvedVideo(
        platform="youtube", video_id=video_id, canonical_url=canonical,
        title=details.get("title", ""), duration=duration, streams=streams,
        cover=thumbs[-1].get("url", "") if thumbs else "",
        author=details.get("author", ""), description=details.get("shortDescription", ""),
        notes=notes, audio_streams=audio,
        extra={"stats": {"views": details.get("viewCount")}},
    )


class YouTubeResolver(Resolver):
    platform = "youtube"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 15) -> None:
        self._transport = transport
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Referer": "https://www.youtube.com/",
                "Accept-Language": "zh-CN,zh;q=0.9"}

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
        return host in HOSTS or host.endswith(".youtube.com")

    async def resolve(self, url: str, part: int | None = None) -> ResolvedVideo:
        video_id = parse_target(url)
        try:
            response = await self._http().get(WATCH, params={"v": video_id, "hl": "zh", "gl": "CN"})
        except httpx.TimeoutException:
            raise ResolveError("timeout", "连接 YouTube 超时，请检查网络后重试", retryable=True) from None
        except httpx.HTTPError:
            raise ResolveError("network", "无法连接 YouTube，请检查网络（可能需要代理）后重试", retryable=True) from None
        if response.status_code == 404:
            raise ResolveError("not_found", "视频不存在或已被删除")
        if response.status_code >= 500:
            raise ResolveError("upstream", f"YouTube 返回了错误（HTTP {response.status_code}）", retryable=True)
        payload = _extract_player_response(response.text)
        return parse_player_response(payload, video_id, self.headers)
