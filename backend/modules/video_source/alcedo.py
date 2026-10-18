"""Links our own resolvers don't know, through alcedo (github.com/hiyufan/alcedo, MIT).

alcedo is a Rust video-link parser for 35 platforms: 抖音, 快手, 小红书, YouTube, TikTok, 微博,
西瓜 … It returns the same things our resolvers do: title, author, duration, and per quality a
combined address or separate video/audio tracks, with the request headers the CDN checks. Bilibili
and WeChat Channels keep their own resolvers (comments, danmaku, the Yuanbao login); alcedo is tried
after them, for any other link, and once more when the Bilibili resolver fails.

Two ways to reach it, from settings:
  ALCEDO_URL   a running `alcedo serve` (e.g. http://127.0.0.1:7878): pooled connections, guest
               identities and a result cache kept between imports
  ALCEDO_BIN   the binary, run once per link (`alcedo --json`); found on PATH or in
               ../tools/alcedo-*/ when not set (scripts/install-alcedo.sh puts it there)
Neither available: this resolver matches nothing and the app behaves as before.

Logins the app already holds are passed on (BILIBILI_COOKIE → ALCEDO_BILI_COOKIE, and DOUYIN_COOKIE,
XHS_COOKIE, YOUTUBE_COOKIE when set). ALCEDO_SSRF_DNS (alcedo's private-address check on DNS answers)
is turned off automatically when the machine resolves public hosts into 198.18.0.0/15 — the fake-IP
range of proxy tools, which alcedo would otherwise refuse as private.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..settings import settings
from .base import ResolveError, ResolvedVideo, Resolver, Stream

PLATFORM = "alcedo"
TIMEOUT = 60.0  # seconds for one parse (alcedo's own total timeout is 45 s)
TOOLS = Path(__file__).resolve().parents[4] / "tools"  # next to the repository
MAX_STREAMS = 4
COOKIES = {"BILIBILI_COOKIE": "ALCEDO_BILI_COOKIE", "DOUYIN_COOKIE": "ALCEDO_DOUYIN_COOKIE",
           "XHS_COOKIE": "ALCEDO_XHS_COOKIE", "YOUTUBE_COOKIE": "ALCEDO_YOUTUBE_COOKIE"}
# alcedo's reasons → our codes; the message shown is ours plus alcedo's own explanation.
REASONS = {
    "login": ("login_required", "这个平台要求登录才能读取"),
    "blocked": ("rate_limited", "平台暂时限制了访问，过几分钟再试"),
    "restricted": ("restricted", "平台限制访问这条内容（账号、地区或权限）"),
    "deleted": ("not_found", "内容已删除、设为私密，或链接已过期"),
    "unsupported": ("unsupported_platform", "暂不支持这个链接"),
    "network": ("network", "连不上对方平台，稍后再试"),
    "timeout": ("timeout", "解析超时，稍后再试"),
    "empty": ("no_stream", "没有取到可播放的视频"),
    "parse": ("upstream", "平台返回的数据和预期不一致，可能改版了"),
}
RETRYABLE = {"rate_limited", "network", "timeout"}
CODEC_RANK = {"": 0, "h.264": 0, "avc": 0, "h.265": 1, "hevc": 1, "vp9": 2, "av1": 3}  # cheapest to decode first


def find_binary() -> str | None:
    configured = settings().get("ALCEDO_BIN", "").strip()
    if configured:
        return configured if Path(configured).is_file() else None
    on_path = shutil.which("alcedo")
    if on_path:
        return on_path
    found = sorted(TOOLS.glob("alcedo-*/alcedo-cli-*/bin/alcedo"))
    return str(found[-1]) if found else None


@functools.lru_cache(maxsize=1)
def fake_ip_dns() -> bool:
    """True when public names resolve into the proxy fake-IP range (alcedo's DNS check would refuse)."""
    fake = ipaddress.ip_network("198.18.0.0/15")
    try:
        return ipaddress.ip_address(socket.gethostbyname("www.bilibili.com")) in fake
    except (OSError, ValueError):
        return False


def child_env() -> dict[str, str]:
    conf = settings()
    env = {k: v for k, v in os.environ.items() if not k.startswith("ALCEDO_")}
    env.update({k: v for k, v in conf.items() if k.startswith("ALCEDO_") and k not in ("ALCEDO_BIN", "ALCEDO_URL")})
    for ours, theirs in COOKIES.items():
        if conf.get(ours, "").strip() and theirs not in env:
            env[theirs] = conf[ours].strip()
    if "ALCEDO_SSRF_DNS" not in env and fake_ip_dns():
        env["ALCEDO_SSRF_DNS"] = "0"
    return env


def failure(reason: str, detail: str) -> ResolveError:
    code, text = REASONS.get(reason, ("upstream", "解析失败"))
    detail = re.sub(r"https?://\S+", "", detail or "").strip("（）() ")[:160]
    return ResolveError(code, f"{text}（{detail}）" if detail else text, retryable=code in RETRYABLE)


def _rank(f: dict) -> tuple:
    codec = (f.get("codec") or "").lower()
    return (CODEC_RANK.get(codec, 4), abs((f.get("height") or 720) - 720))


def to_video(data: dict, url: str) -> ResolvedVideo:
    """alcedo's JSON → our ResolvedVideo. Video streams: H.264 first, nearest 720p first."""
    headers = {k: str(v) for k, v in (data.get("video_headers") or {}).items()}
    expires = data.get("expires_at")
    formats = sorted([f for f in data.get("formats") or [] if f.get("url") or f.get("video_url")], key=_rank)

    def stream(address: str, label: str, height: int = 0) -> Stream:
        return Stream(address, headers, label, height or 0, float(expires) if expires else None)

    streams, audio, seen = [], [], set()
    sound_only = []  # "仅音频": no picture height and no separate video track
    for f in formats:
        address = f.get("video_url") or f.get("url")
        if address in seen:
            continue
        seen.add(address)
        if not f.get("video_url") and not f.get("height"):
            sound_only.append(stream(address, f"alcedo {f.get('label', '')} audio"))
            continue
        streams.append(stream(address, f"alcedo {f.get('label', '')}".strip(), f.get("height") or 0))
        if f.get("audio_url") and f["audio_url"] not in {a.url for a in audio}:
            audio.append(stream(f["audio_url"], f"alcedo {f.get('label', '')} audio"))
        elif f.get("url") and not f.get("video_url"):
            audio.append(stream(f["url"], f"alcedo {f.get('label', '')}"))  # a combined file carries its sound
    audio += [a for a in sound_only if a.url not in {x.url for x in audio}]
    if not streams and sound_only and not data.get("video_url"):
        streams = sound_only  # nothing else to read: at least the sound is analysed
    if not streams and data.get("video_url"):
        streams.append(stream(data["video_url"], "alcedo"))
        audio.append(stream(data["video_url"], "alcedo"))
    page = data.get("page_url") or url
    source = data.get("source") or "web"
    author = data.get("author") or {}
    if not streams and data.get("images"):  # an image post (图集): pictures instead of a video
        pictures = [{"url": i["url"], "headers": headers} for i in data["images"] if i.get("url")][:60]
        return ResolvedVideo(
            platform=source, video_id=f"{source}-{hashlib.sha1(page.encode()).hexdigest()[:12]}", canonical_url=page,
            title=(data.get("title") or "").strip() or page, duration=float(len(pictures)), streams=[],
            cover=data.get("cover_url") or "", author=author.get("name") or "",
            notes=[f"经 alcedo 解析（{source}），图集 {len(pictures)} 张"],
            extra={"resolver": PLATFORM, "kind": "images", "images": pictures})
    if not streams:
        raise ResolveError("no_stream", "没有取到可播放的视频")
    return ResolvedVideo(
        platform=source,
        video_id=f"{source}-{hashlib.sha1(page.encode()).hexdigest()[:12]}",
        canonical_url=page,
        title=(data.get("title") or "").strip() or page,
        duration=float(data.get("duration") or 0),
        streams=streams[:MAX_STREAMS],
        cover=data.get("cover_url") or "",
        author=author.get("name") or "",
        audio_streams=audio[:MAX_STREAMS],
        notes=[f"经 alcedo 解析（{source}）"],
        extra={"resolver": PLATFORM},
    )


async def probe_duration(stream: Stream) -> float:
    """The duration ffprobe reads from the stream's header (0 if it can't)."""
    args = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1"]
    if stream.headers:
        args += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in stream.headers.items())]
    try:
        proc = await asyncio.create_subprocess_exec(*args, stream.url, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), 30)
        return round(float(out.decode().strip() or 0), 3)
    except (OSError, ValueError, asyncio.TimeoutError):
        return 0.0


class AlcedoResolver(Resolver):
    platform = PLATFORM

    def available(self) -> bool:
        return bool(settings().get("ALCEDO_URL", "").strip() or find_binary())

    def matches(self, url: str) -> bool:
        return urlsplit(url).scheme in ("http", "https") and self.available()

    def serves(self, platform: str) -> bool:
        """Sessions it resolved carry the source platform (douyin, youtube …) as their platform."""
        return platform not in ("bilibili", "wechat_channels", "local")

    async def resolve(self, url: str, part: int | None = None) -> ResolvedVideo:
        data = await (self._serve(url) if settings().get("ALCEDO_URL", "").strip() else self._run(url))
        video = to_video(data, url)
        if not video.duration and video.streams:  # some platforms (微博, 梨视频, Vimeo) give an address but no duration
            video.duration = await probe_duration(video.streams[0])
            if not video.duration:
                raise ResolveError("no_stream", "读不到这个视频的时长，无法抽帧")
        return video

    async def _run(self, url: str) -> dict:
        binary = find_binary()
        if not binary:
            raise ResolveError("unsupported_platform", "暂不支持这个链接（没有安装 alcedo）")
        proc = await asyncio.create_subprocess_exec(binary, "--json", url, env=child_env(),
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ResolveError("timeout", "解析超时，稍后再试", retryable=True) from None
        if proc.returncode == 0:
            try:
                return json.loads(out)
            except ValueError:
                raise ResolveError("upstream", "解析结果无法读取") from None
        text = (err or out).decode(errors="replace")
        m = re.search(r"\[(\w+)\]\s*(.*)", text, re.S)
        raise failure(m.group(1), m.group(2).strip()) if m else ResolveError("upstream", "解析失败")

    async def _serve(self, url: str) -> dict:
        base = settings()["ALCEDO_URL"].strip().rstrip("/")
        token = settings().get("ALCEDO_SERVE_TOKEN", "").strip()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.get(f"{base}/parse", params={"url": url},
                                     headers={"Authorization": f"Bearer {token}"} if token else {})
        except httpx.HTTPError:
            raise ResolveError("network", "连不上解析服务（ALCEDO_URL），请确认 alcedo serve 在运行", retryable=True) from None
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200:
            return body
        raise failure(body.get("reason", ""), body.get("message") or body.get("detail") or f"HTTP {r.status_code}")
