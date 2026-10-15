"""WeChat Channels (视频号) resolver.

Anonymous requests to the official preview API (`finder-preview/api/feed/get_feed_info`) return only
author, description and cover: the video address and title need a `generalToken` issued inside
WeChat. Following vendor/media-parser in the MVP, the token is obtained through Tencent Yuanbao's
"parse a Channels link" endpoint with the user's Yuanbao login cookie:

  1. POST yuanbao.tencent.com/api/weixin/get_parse_result → playable_url carrying `token` and `eid`
  2. POST get_feed_info {generalToken: token, exportId: eid} → feedInfo with an unencrypted MP4 URL

The cookie comes from YUANBAO_COOKIE (`hy_user=…; hy_token=…`) in backend/.env. Both endpoints are
undocumented and may change.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import urllib.parse

import httpx

from ..settings import settings
from .base import ResolveError, ResolvedVideo, Resolver, Stream

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
HOSTS = {"weixin.qq.com", "channels.weixin.qq.com"}
YUANBAO_API = "https://yuanbao.tencent.com/api/weixin/get_parse_result"
FEED_INFO_API = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
FEED_PAGE = "https://channels.weixin.qq.com/finder-preview/pages/feed"
SHORT_RE = re.compile(r"/sph/([A-Za-z0-9]+)")
MEDIA_VIDEO, MEDIA_ALBUM = 4, 2


def short_uri(url: str) -> str | None:
    parts = urllib.parse.urlsplit(url)
    found = SHORT_RE.search(parts.path)
    if found:
        return found.group(1)
    if parts.path.startswith("/finder-preview/pages/sph"):
        return urllib.parse.parse_qs(parts.query).get("id", [None])[0]
    return None


async def probe_duration(url: str, headers: dict[str, str], timeout: float = 30) -> float:
    """Read the duration from the MP4 header (a few range requests, no download)."""
    args = ["ffprobe", "-v", "error", "-headers", "".join(f"{k}: {v}\r\n" for k, v in headers.items()),
            "-show_entries", "format=duration", "-of", "json", url]
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return float(json.loads(out or b"{}").get("format", {}).get("duration") or 0)
    except (FileNotFoundError, asyncio.TimeoutError, ValueError):
        return 0.0


class WeChatChannelsResolver(Resolver):
    platform = "wechat_channels"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 15, probe=probe_duration) -> None:
        self._client = httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False,
                                         headers={"User-Agent": USER_AGENT})
        self.probe = probe
        self.headers = {"User-Agent": USER_AGENT, "Referer": "https://channels.weixin.qq.com/"}

    async def aclose(self) -> None:
        await self._client.aclose()

    def matches(self, url: str) -> bool:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        return host in HOSTS and short_uri(url) is not None

    async def _token(self, share_url: str) -> tuple[str, str]:
        cookie = settings().get("YUANBAO_COOKIE", "").strip()
        if not cookie:
            raise ResolveError("login_required", "解析视频号需要腾讯元宝的登录凭证：在 backend/.env 中设置 "
                                                 "YUANBAO_COOKIE=\"hy_user=…; hy_token=…\" 后重试")
        try:
            response = await self._client.post(YUANBAO_API, json={"type": "video_channel_url", "url": share_url, "scene": 1},
                                               headers={"Cookie": cookie, "Origin": "https://yuanbao.tencent.com",
                                                        "Referer": "https://yuanbao.tencent.com/chat", "x-source": "web"})
        except httpx.HTTPError:
            raise ResolveError("upstream", "无法连接腾讯元宝，请稍后重试", retryable=True) from None
        if response.status_code in (401, 403):
            raise ResolveError("login_expired", "腾讯元宝登录已失效，请重新获取 YUANBAO_COOKIE")
        try:
            payload = response.json()
        except ValueError:
            raise ResolveError("upstream", f"腾讯元宝返回了无法解析的内容（HTTP {response.status_code}）", retryable=True) from None
        playable = (payload.get("data") or {}).get("playable_url")
        if not playable:
            message = str(payload.get("msg") or payload.get("message") or "")
            if re.search(r"登录|login|auth|token", message, re.I) or response.status_code == 401:
                raise ResolveError("login_expired", "腾讯元宝登录已失效，请重新获取 YUANBAO_COOKIE")
            raise ResolveError("upstream", f"腾讯元宝没有返回视频号地址{f'：{message}' if message else ''}", retryable=True)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(playable).query)
        token, export_id = query.get("token", [""])[0], query.get("eid", [""])[0]
        if not token or not export_id:
            raise ResolveError("upstream", "腾讯元宝返回的地址缺少视频号凭证", retryable=True)
        return token, export_id

    async def _feed(self, token: str, export_id: str) -> dict:
        referer = FEED_PAGE + "?" + urllib.parse.urlencode(
            {"entry_card_type": 48, "comment_scene": 39, "appid": 0, "token": token, "entry_scene": 0, "eid": export_id})
        try:
            response = await self._client.post(
                f"{FEED_INFO_API}?_rid={random.randrange(16**8):08x}&_pageUrl={urllib.parse.quote(FEED_PAGE, safe='')}",
                json={"baseReq": {"generalToken": token}, "exportId": export_id},
                headers={"Origin": "https://channels.weixin.qq.com", "Referer": referer})
            payload = response.json()
        except httpx.HTTPError:
            raise ResolveError("upstream", "无法连接视频号，请稍后重试", retryable=True) from None
        except ValueError:
            raise ResolveError("upstream", "视频号返回了无法解析的内容", retryable=True) from None
        if payload.get("errCode") not in (0, None):
            raise ResolveError("upstream", f"视频号接口返回错误（{payload.get('errCode')}）：{payload.get('errMsg', '')}", retryable=True)
        return payload.get("data") or {}

    async def resolve(self, url: str, part: int | None = None) -> ResolvedVideo:
        short = short_uri(url)
        if not short:
            raise ResolveError("unsupported_link", "不是可识别的视频号分享链接")
        canonical = f"https://weixin.qq.com/sph/{short}"
        token, export_id = await self._token(canonical)
        data = await self._feed(token, export_id)
        feed, author = data.get("feedInfo") or {}, data.get("authorInfo") or {}
        if not feed:
            raise ResolveError("not_found", "视频号内容不存在、已删除或仅作者可见")
        video_url = (feed.get("videoUrl") or (feed.get("h264VideoInfo") or {}).get("videoUrl")
                     or (feed.get("h265VideoInfo") or {}).get("videoUrl"))
        if not video_url:
            if feed.get("mediaType") == MEDIA_ALBUM or feed.get("picInfo"):
                raise ResolveError("unsupported_content", "这是视频号的图文/图集，不是视频")
            raise ResolveError("no_stream", "视频号没有返回视频地址，可能是元宝凭证权限不足", retryable=True)
        duration = float(feed.get("videoDuration") or feed.get("duration") or 0)
        if duration <= 0:
            duration = await self.probe(video_url, self.headers)
        if duration <= 0:
            raise ResolveError("upstream", "无法读取视频号视频的时长", retryable=True)
        stream = Stream(video_url, self.headers, "wechat-mp4")
        description = feed.get("description") or ""
        title = feed.get("title") or description.split("#")[0].strip()[:60] or f"视频号 {short}"
        return ResolvedVideo(
            platform=self.platform, video_id=short, canonical_url=canonical, title=title, duration=duration,
            streams=[stream], cover=feed.get("coverUrl") or "", author=author.get("nickname") or "",
            description=description,
            # A single MP4 carries the sound too; ffmpeg reads just its audio track.
            audio_streams=[stream],
            extra={"export_id": export_id},
        )
