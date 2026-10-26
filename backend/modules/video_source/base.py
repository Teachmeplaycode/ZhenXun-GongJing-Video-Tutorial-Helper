"""Platform-neutral contract every link resolver fulfils.

A resolver turns a share link into a ResolvedVideo: identity, metadata and a ranked list of
readable stream addresses. It never downloads the video; frame sampling reads the streams.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit


class ResolveError(Exception):
    """User-facing resolution failure. `code` is stable for the frontend, `message` is Chinese."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass
class Stream:
    """One readable video address. Headers must accompany every request to it."""

    url: str
    headers: dict[str, str]
    label: str
    height: int = 0
    expires_at: float | None = None

    def expired(self, margin: float = 60) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at - margin


@dataclass
class Part:
    index: int
    title: str
    duration: float


@dataclass
class ResolvedVideo:
    platform: str
    video_id: str
    canonical_url: str
    title: str
    duration: float
    streams: list[Stream]
    part: int = 1
    parts: list[Part] = field(default_factory=list)
    cover: str = ""
    author: str = ""
    description: str = ""
    # Set when only a prefix is readable (e.g. trial playback); later frames are reported missing.
    playable_duration: float | None = None
    notes: list[str] = field(default_factory=list)
    # Audio-only addresses (lowest bitrate first) for transcription; empty when the platform has none.
    audio_streams: list[Stream] = field(default_factory=list)
    # Resolver-private identifiers needed to refresh addresses (never sent to the client).
    extra: dict = field(default_factory=dict)

    def public(self) -> dict:
        """Client-safe view: no stream addresses or headers."""
        sampling = self.extra.get("sampling")
        mode = sampling.get("ocr_mode") if isinstance(sampling, dict) else None
        return {
            "platform": self.platform,
            "video_id": self.video_id,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "duration": self.duration,
            "part": self.part,
            "parts": [{"index": p.index, "title": p.title, "duration": p.duration} for p in self.parts],
            "cover": self.cover,
            "author": self.author,
            "description": self.description,
            "playable_duration": self.playable_duration,
            "notes": self.notes,
            "stream_count": len(self.streams),
            "has_audio": bool(self.audio_streams),
            "ocr_mode": mode if mode in ("hybrid", "local", "server") else "server",
            "stats": self.extra.get("stats") or {},
            "tags": self.extra.get("tags") or [],
            "kind": self.extra.get("kind") or "video",  # "images": an image post or uploaded pictures
            "image_count": len(self.extra.get("images") or []),
        }


@dataclass
class Comment:
    author: str
    text: str
    likes: int = 0
    reply_count: int = 0
    time: float = 0  # unix seconds
    pinned: bool = False
    replies: list[Comment] = field(default_factory=list)  # the few sub-replies the platform sends along


@dataclass
class CommentPage:
    comments: list[Comment]
    total: int | None = None
    cursor: str | None = None  # pass back for the next page; None: no more
    note: str = ""             # e.g. why only a few were returned


@dataclass
class Danmaku:
    """A bullet comment: viewers' remarks pinned to a moment of the video."""
    time: float
    text: str


class Resolver:
    """Base class for platform resolvers. Subclasses set `platform` and implement the hooks."""

    platform = ""
    audience: tuple[str, ...] = ()  # what viewers left that this platform can read: "comments", "danmaku"

    def matches(self, url: str) -> bool:
        raise NotImplementedError

    def audience_for(self, video: ResolvedVideo | None) -> tuple[str, ...]:
        """What viewers left on this particular video that can be read (alcedo: only some sources)."""
        return self.audience

    def serves(self, platform: str) -> bool:
        """Whether a saved session of this platform is refreshed by this resolver."""
        return platform == self.platform

    async def resolve(self, url: str, part: int | None = None) -> ResolvedVideo:
        raise NotImplementedError

    async def refresh(self, video: ResolvedVideo) -> ResolvedVideo:
        """Re-acquire addresses for the same target after they expired or were refused."""
        fresh = await self.resolve(video.canonical_url, video.part)
        if fresh.video_id != video.video_id:
            raise ResolveError("identity_mismatch", "重新获取到的视频与原目标不一致")
        return fresh

    async def fallback_streams(self, video: ResolvedVideo) -> list[Stream]:
        """Lower-quality but more permissive addresses, tried after the primary ones fail."""
        return []

    async def hd_streams(self, video: ResolvedVideo) -> list[Stream]:
        """Sharper picture tracks than the ones keyframes are read from, for small print; [] when there are none."""
        return []

    async def related(self, video: ResolvedVideo) -> list[dict]:
        """Videos the platform recommends next to this one: [{url, title, author, duration, views, cover}]."""
        return []

    async def comments(self, video: ResolvedVideo, sort: str = "hot", cursor: str | None = None) -> CommentPage:
        """One page of the video's comments; sort is "hot" or "time"."""
        raise ResolveError("unsupported", "这个平台读不到评论")

    async def danmaku(self, video: ResolvedVideo) -> list[Danmaku]:
        """Bullet comments, in time order."""
        raise ResolveError("unsupported", "这个平台没有弹幕")

    async def aclose(self) -> None:
        return None


def expiry_from_url(url: str, key: str = "deadline") -> float | None:
    """Many CDNs sign addresses with a unix deadline in the query string."""
    value = parse_qs(urlsplit(url).query).get(key, [None])[0]
    try:
        return float(value) if value else None
    except ValueError:
        return None
