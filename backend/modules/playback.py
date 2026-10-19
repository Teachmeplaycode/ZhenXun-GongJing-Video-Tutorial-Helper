"""Playing the original video, so a cited moment can be watched rather than only seen as a still.

A job's evidence can be in one of three states, shown to the user as such and never blurred:

  original  the source can be played: an upload kept on disk, or a platform's own MP4 (with sound)
            that this backend relays, since its CDN wants headers or refuses other sites
  cache     only the sampled frames (and transcript) are left: the upload was deleted, the link
            expired, or the platform offers no playable file
  none      nothing to look at: no frames either

Platform addresses expire; a relayed request that is refused re-acquires them once.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .frames import FrameJob
from .video_source.base import ResolveError, Stream

LOCAL = "local"
PLAY_TTL = 600            # seconds a found playable address is reused before asking the platform again
RESUMES = 3              # times a relayed body the CDN cut off is carried on from where it stopped
PASS_HEADERS = ("content-type", "content-length", "content-range", "accept-ranges", "last-modified", "etag")


@dataclass
class Playable:
    kind: str                      # "file" | "stream"
    path: Path | None = None
    stream: Stream | None = None
    label: str = ""
    found: float = 0.0


_cache: dict[str, Playable] = {}
_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    """The relay's connection pool, kept for the server's life (seeking sends many Range requests)."""
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(30, read=60), follow_redirects=True,
                                  limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=60))
    return _http


def _combined(job: FrameJob) -> Stream | None:
    """A stream that carries both picture and sound (the same address is also an audio stream)."""
    sound = {a.url for a in job.video.audio_streams}
    return next((s for s in job.video.streams if s.url in sound and not s.expired()), None)


async def find(job: FrameJob, fresh: bool = False) -> Playable | None:
    """How the original can be played right now, or None."""
    if (job.video.extra or {}).get("kind") == "images":
        return None
    if job.video.platform == LOCAL:
        path = Path(job.video.streams[0].url) if job.video.streams else None
        return Playable("file", path=path, label="本地原文件") if path and path.is_file() else None
    hit = _cache.get(job.id)
    if hit and not fresh and time.time() - hit.found < PLAY_TTL and not (hit.stream and hit.stream.expired()):
        return hit
    resolver = job.resolver
    if resolver is None:
        return None
    stream = None
    if job.video.platform == "bilibili":
        # The DASH tracks it reads frames from are picture-only; its html5 player's MP4 has sound.
        try:
            pick = getattr(resolver, "play_streams", None) or resolver.fallback_streams
            found = await pick(job.video)
        except ResolveError:
            found = []
        stream = found[0] if found else None
    else:
        stream = None if fresh else _combined(job)
        if stream is None:
            try:
                job.video = await resolver.refresh(job.video)
            except (ResolveError, NotImplementedError):
                return None
            stream = _combined(job)
    if stream is None:
        _cache.pop(job.id, None)
        return None
    _cache[job.id] = Playable("stream", stream=stream, label=f"{job.video.platform} 原视频", found=time.time())
    return _cache[job.id]


def forget(job_id: str) -> None:
    _cache.pop(job_id, None)


async def state(job: FrameJob) -> dict:
    """{state, label, message} for the client: which kind of looking back this job offers."""
    playable = await find(job)
    if playable is not None:
        return {"state": "original", "label": playable.label, "message": "点击时间点会在原片里播放"}
    has_frames = any(s.status == "ok" for s in job.slots)
    if has_frames:
        reason = ("上传的原视频已删除" if job.video.platform == LOCAL
                  else "平台没有提供可播放的原视频（或链接已失效）")
        return {"state": "cache", "label": "缓存证据", "message": f"{reason}，时间点只能查看抽取的画面和文字"}
    return {"state": "none", "label": "无可回看证据", "message": "原视频和抽取的画面都不可用，时间点不能回看"}


def span(content_range: str | None, content_length: str | None) -> tuple[int, int | None]:
    """(first byte, last byte) of a response body: from Content-Range, else 0..length-1 (None: unknown)."""
    m = re.match(r"bytes (\d+)-(\d+)/", content_range or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    try:
        return 0, int(content_length) - 1 if content_length else None
    except ValueError:
        return 0, None


async def relay(client: httpx.AsyncClient, stream: Stream, range_header: str | None):
    """Open the platform address with its headers and the viewer's Range: (status, headers, response)."""
    headers = dict(stream.headers)
    if range_header:
        headers["Range"] = range_header
    request = client.build_request("GET", stream.url, headers=headers)
    response = await client.send(request, stream=True)
    passed = {k: v for k, v in response.headers.items() if k.lower() in PASS_HEADERS}
    passed.setdefault("accept-ranges", "bytes")
    if passed.get("content-type", "").startswith(("application/octet-stream", "binary/")):
        passed["content-type"] = "video/mp4"
    return response.status_code, passed, response
