"""Pick the resolver for a link. Add a platform by registering another Resolver subclass."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .base import ResolveError, ResolvedVideo, Resolver

# Share text often wraps the link: "【标题】 https://b23.tv/xxxx 复制此链接…"
URL_RE = re.compile(r"https?://[^\s<>\"'，。！？、】）)]+", re.I)
BV_RE = re.compile(r"\b(BV[0-9A-Za-z]{10})\b")
AV_RE = re.compile(r"(?<![0-9A-Za-z])av(\d+)\b", re.I)


def extract_url(text: str) -> str:
    """Find a link in pasted text; bare BV/av ids are expanded to their Bilibili page."""
    text = (text or "").strip()
    found = URL_RE.search(text)
    if found:
        return found.group(0).rstrip(".,;")
    bv = BV_RE.search(text)
    if bv:
        return f"https://www.bilibili.com/video/{bv.group(1)}"
    av = AV_RE.search(text)
    if av:
        return f"https://www.bilibili.com/video/av{av.group(1)}"
    raise ResolveError("no_link", "没有识别到视频链接，请粘贴完整的分享链接")


class Registry:
    def __init__(self, resolvers: list[Resolver] | None = None) -> None:
        self.resolvers: list[Resolver] = list(resolvers or [])

    def register(self, resolver: Resolver) -> None:
        self.resolvers.append(resolver)

    def find(self, url: str) -> Resolver:
        for resolver in self.resolvers:
            if resolver.matches(url):
                return resolver
        host = urlsplit(url).hostname or url
        raise ResolveError("unsupported_platform", f"暂不支持该平台的链接：{host}")

    async def resolve(self, text: str, part: int | None = None) -> tuple[Resolver, ResolvedVideo]:
        url = extract_url(text)
        resolver = self.find(url)
        return resolver, await resolver.resolve(url, part)

    async def aclose(self) -> None:
        for resolver in self.resolvers:
            await resolver.aclose()


def default_registry() -> Registry:
    from .bilibili import BilibiliResolver
    from .douyin import DouyinResolver
    from .local import LocalResolver
    from .wechat import WeChatChannelsResolver
    from .youtube import YouTubeResolver

    # LocalResolver never matches a URL; it is listed so restored upload sessions find their resolver.
    return Registry([BilibiliResolver(), WeChatChannelsResolver(), YouTubeResolver(), DouyinResolver(), LocalResolver()])
