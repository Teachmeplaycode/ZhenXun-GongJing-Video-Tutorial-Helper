"""Bilibili resolver: anonymous, address-only (never downloads media).

Flow: expand short link → parse BV/av + part → buvid cookies (finger/spi) → WBI-signed `view`
(identity, parts, duration) → WBI-signed `playurl` (DASH video addresses + backups).
Risk-control responses reset the session once and retry. A permissive html5 MP4 address is kept
as a fallback for when every DASH address is refused.

Viewers' side: danmaku come from comment.bilibili.com/{cid}.xml (anonymous, the most recent ones up
to the video's pool size, each with its moment in the video). Comments come from /x/v2/reply/main;
logged out, Bilibili sends only the top 3 (tested 2026-10-16, and the WBI `reply/wbi/main` answers
-403). With BILIBILI_COOKIE (the browser's `SESSDATA=…`) the signed endpoint pages through all of them.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from modules.settings import settings

from .base import Comment, CommentPage, Danmaku, Part, ResolveError, ResolvedVideo, Resolver, Stream, expiry_from_url

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"
API = "https://api.bilibili.com"
HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}
SHORT_HOSTS = {"b23.tv", "www.b23.tv", "bili2233.cn", "www.bili2233.cn"}
BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
AV_RE = re.compile(r"/av(\d+)", re.I)
# Frames don't need more than this; smaller streams seek faster.
MAX_HEIGHT = 720
HD_HEIGHT = 1080  # hd_streams: reading small print, with the person's login
AVC = 7
# Peer/edge caches that are often slow or refuse range reads; tried last.
PCDN_MARKERS = ("mcdn.bilivideo", "szbdyd.com", ":8082", ":4483")
MIXIN_TABLE = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39,
    12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63,
    57, 62, 11, 36, 20, 34, 44, 52,
]
RISK_CODES = {-352, -412, -351}
VIEW_ERRORS = {
    -404: ("not_found", "视频不存在或已被删除"),
    62002: ("not_found", "视频不可见（可能已删除或设为私密）"),
    62012: ("not_found", "视频仅 UP 主自己可见"),
    62004: ("unavailable", "视频正在审核中，暂时无法读取"),
    -403: ("forbidden", "该视频需要权限才能观看（可能是付费、充电专属或需登录）"),
    87008: ("forbidden", "该视频为充电专属，暂不支持"),
}


def mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_TABLE)[:32]


def sign_wbi(params: dict, key: str, now: float | None = None) -> dict:
    """Add `wts` and `w_rid` the way the web player does."""
    signed = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in params.items()}
    signed["wts"] = str(int(now if now is not None else time.time()))
    query = urllib.parse.urlencode(sorted(signed.items()))
    signed["w_rid"] = hashlib.md5((query + key).encode()).hexdigest()
    return signed


def parse_target(url: str) -> tuple[str, str, int | None]:
    """Return (id_kind, id, part) from a full Bilibili page URL."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if host not in HOSTS:
        # space./live./search. and other subdomains are Bilibili, just not a video page.
        raise ResolveError("not_video_page", "这不是 B 站视频页面（如用户主页、直播间），请粘贴视频链接")
    if "/bangumi/" in parts.path or "/cheese/" in parts.path:
        raise ResolveError("unsupported_content", "暂不支持番剧、影视和课程，请使用普通视频链接")
    query = urllib.parse.parse_qs(parts.query)
    part = None
    if query.get("p"):
        try:
            part = max(1, int(query["p"][0]))
        except ValueError:
            part = None
    bv = BV_RE.search(parts.path) or BV_RE.search(query.get("bvid", [""])[0])
    if bv:
        return "bvid", bv.group(1), part
    av = AV_RE.search(parts.path)
    if av:
        return "aid", av.group(1), part
    raise ResolveError("unsupported_link", "链接里没有找到视频编号（BV 号或 av 号）")


def rank_urls(urls: list[str]) -> list[str]:
    """Deduplicate and push peer caches to the end, keeping the original order otherwise."""
    seen, ordered = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    return sorted(ordered, key=lambda u: any(m in u for m in PCDN_MARKERS))


COMMENT_SORT = {"hot": 3, "time": 2}  # reply `mode`
ANONYMOUS_NOTE = "B 站未登录只返回前 3 条热门评论；点右上角「账号」扫码登录 B 站后可以读更多"


def parse_comment(r: dict, pinned: bool = False) -> Comment:
    return Comment(
        author=(r.get("member") or {}).get("uname", ""),
        text=((r.get("content") or {}).get("message") or "").strip(),
        likes=int(r.get("like") or 0), reply_count=int(r.get("rcount") or 0), time=float(r.get("ctime") or 0),
        pinned=pinned, replies=[parse_comment(x) for x in (r.get("replies") or [])[:3]])


def parse_danmaku(xml: str) -> list[Danmaku]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        raise ResolveError("upstream", "B 站返回的弹幕无法解析", retryable=True) from None
    items = []
    for d in root.iter("d"):
        try:
            t = float((d.get("p") or "").split(",")[0])
        except ValueError:
            continue
        if (d.text or "").strip():
            items.append(Danmaku(t, d.text.strip()))
    return sorted(items, key=lambda x: x.time)


class BilibiliResolver(Resolver):
    platform = "bilibili"
    audience = ("comments", "danmaku")

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 12) -> None:
        self._transport = transport
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._has_buvid = False
        self._wbi: tuple[date, str] | None = None

    def matches(self, url: str) -> bool:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        return host in SHORT_HOSTS or host == "bilibili.com" or host.endswith(".bilibili.com")

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Referer": REFERER}

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers, timeout=self._timeout, follow_redirects=True, transport=self._transport
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _reset_session(self) -> None:
        self._has_buvid = False
        self._wbi = None
        if self._client is not None:
            self._client.cookies.clear()

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        try:
            return await self._http().get(url, **kwargs)
        except httpx.TimeoutException:
            raise ResolveError("timeout", "连接 B 站超时，请检查网络后重试", retryable=True) from None
        except httpx.HTTPError:
            raise ResolveError("network", "无法连接 B 站，请检查网络后重试", retryable=True) from None

    async def _expand(self, url: str) -> str:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if host not in SHORT_HOSTS:
            return url
        response = await self._get(url)
        final = str(response.url)
        if (urllib.parse.urlsplit(final).hostname or "").lower() not in HOSTS:
            raise ResolveError("unsupported_link", "短链接没有指向 B 站视频页面")
        return final

    async def _ensure_buvid(self) -> None:
        if self._has_buvid:
            return
        response = await self._get(f"{API}/x/frontend/finger/spi")
        data = (response.json() or {}).get("data") or {}
        client = self._http()
        if data.get("b_3"):
            client.cookies.set("buvid3", data["b_3"], domain=".bilibili.com")
        if data.get("b_4"):
            client.cookies.set("buvid4", data["b_4"], domain=".bilibili.com")
        client.cookies.set("b_nut", str(int(time.time())), domain=".bilibili.com")
        self._has_buvid = True

    async def _mixin_key(self) -> str:
        today = date.today()
        if self._wbi and self._wbi[0] == today:
            return self._wbi[1]
        response = await self._get(f"{API}/x/web-interface/nav")
        # `nav` answers -101 (not logged in) but still carries the WBI keys.
        img = ((response.json() or {}).get("data") or {}).get("wbi_img") or {}
        name = lambda u: u.rsplit("/", 1)[-1].split(".")[0]  # noqa: E731
        if not img.get("img_url") or not img.get("sub_url"):
            raise ResolveError("upstream", "B 站签名参数获取失败，请稍后重试", retryable=True)
        key = mixin_key(name(img["img_url"]), name(img["sub_url"]))
        self._wbi = (today, key)
        return key

    async def _api(self, path: str, params: dict, *, signed: bool = True, login: str = "") -> dict:
        """GET, WBI-signed unless `signed=False`; a risk-control answer resets cookies and keys once.

        `login`: the user's cookie string, sent along with the session's buvid cookies.
        """
        for attempt in range(2):
            await self._ensure_buvid()
            query = sign_wbi(params, await self._mixin_key()) if signed else params
            headers = {}
            if login:
                jar = "; ".join(f"{k}={v}" for k, v in self._http().cookies.items())
                headers["Cookie"] = f"{jar}; {login}" if jar else login
            response = await self._get(f"{API}{path}", params=query, headers=headers)
            if response.status_code == 412:
                code = -412
                payload = {}
            else:
                try:
                    payload = response.json()
                except ValueError:
                    raise ResolveError("upstream", f"B 站返回了无法解析的内容（HTTP {response.status_code}）", retryable=True) from None
                code = payload.get("code", -1)
            if code in RISK_CODES and attempt == 0:
                self._reset_session()
                continue
            if code in RISK_CODES:
                raise ResolveError("risk_control", "B 站暂时限制了访问，请稍后再试", retryable=True)
            return payload
        raise AssertionError("unreachable")

    async def _view(self, kind: str, ident: str) -> dict:
        payload = await self._api("/x/web-interface/wbi/view", {kind: ident})
        code = payload.get("code", -1)
        if code != 0:
            err = VIEW_ERRORS.get(code)
            if err:
                raise ResolveError(*err)
            raise ResolveError("upstream", f"B 站返回错误（{code}）：{payload.get('message', '')}", retryable=True)
        return payload["data"]

    async def _playurl(self, bvid: str, cid: int, **extra) -> dict:
        params = {"bvid": bvid, "cid": cid, "fnval": 16, "fnver": 0, "fourk": 0, "qn": 64, **extra}
        payload = await self._api("/x/player/wbi/playurl", params)
        code = payload.get("code", -1)
        if code != 0:
            err = VIEW_ERRORS.get(code)
            if err:
                raise ResolveError(*err)
            raise ResolveError("no_stream", f"没有拿到播放地址（{code}）：{payload.get('message', '')}", retryable=True)
        return payload["data"] or {}

    def _dash_streams(self, play: dict, cap: int = MAX_HEIGHT) -> list[Stream]:
        videos = [v for v in ((play.get("dash") or {}).get("video") or []) if v.get("baseUrl") or v.get("base_url")]
        if not videos:
            return []
        bounded = [v for v in videos if (v.get("height") or 0) <= cap] or videos
        # Prefer AVC (fastest to decode), highest height within the cap; other codecs follow.
        ordered = sorted(bounded, key=lambda v: (v.get("codecid") != AVC, -(v.get("height") or 0), v.get("codecid") or 0))
        streams: list[Stream] = []
        seen_codecs = set()
        for v in ordered:
            codec = v.get("codecid")
            if codec in seen_codecs:
                continue
            seen_codecs.add(codec)
            urls = rank_urls([v.get("baseUrl") or v.get("base_url")] + list(v.get("backupUrl") or v.get("backup_url") or []))
            for i, u in enumerate(urls):
                streams.append(Stream(u, self.headers, f"dash-{codec}-{v.get('height')}p-{i}", v.get("height") or 0, expiry_from_url(u)))
        return streams

    def _dash_audio(self, play: dict) -> list[Stream]:
        """Audio tracks, lowest bitrate first: plenty for speech and the quickest to read."""
        audios = [a for a in ((play.get("dash") or {}).get("audio") or []) if a.get("baseUrl") or a.get("base_url")]
        streams: list[Stream] = []
        for a in sorted(audios, key=lambda a: a.get("bandwidth") or 0):
            urls = rank_urls([a.get("baseUrl") or a.get("base_url")] + list(a.get("backupUrl") or a.get("backup_url") or []))
            streams += [Stream(u, self.headers, f"audio-{a.get('id')}-{i}", 0, expiry_from_url(u)) for i, u in enumerate(urls)]
        return streams

    def _durl_streams(self, play: dict, label: str) -> list[Stream]:
        segments = play.get("durl") or []
        # Multi-segment FLV is legacy; a single segment covers the whole part.
        if len(segments) != 1:
            return []
        seg = segments[0]
        urls = rank_urls([seg.get("url")] + list(seg.get("backup_url") or []))
        return [Stream(u, self.headers, f"{label}-{i}", 0, expiry_from_url(u)) for i, u in enumerate(urls)]

    async def resolve(self, url: str, part: int | None = None) -> ResolvedVideo:
        url = await self._expand(url)
        kind, ident, url_part = parse_target(url)
        part = part or url_part or 1
        view = await self._view(kind, ident)
        bvid = view["bvid"]
        pages = view.get("pages") or [{"page": 1, "cid": view.get("cid"), "part": view.get("title"), "duration": view.get("duration")}]
        page = next((p for p in pages if p.get("page") == part), None)
        if page is None:
            raise ResolveError("part_not_found", f"该视频只有 {len(pages)} P，没有第 {part} P")
        duration = float(page.get("duration") or view.get("duration") or 0)
        if duration <= 0:
            raise ResolveError("upstream", "无法确定视频时长", retryable=True)
        play = await self._playurl(bvid, page["cid"])
        streams = self._dash_streams(play) or self._durl_streams(play, "durl")
        if not streams:
            raise ResolveError("no_stream", "没有拿到可读取的播放地址", retryable=True)
        notes, playable = [], None
        timelength = float(play.get("timelength") or 0) / 1000
        if play.get("is_preview") or (timelength and timelength < duration - 2):
            playable = timelength or None
            notes.append(f"该视频只能试看前 {int(timelength)} 秒，之后的画面无法读取")
        canonical = f"https://www.bilibili.com/video/{bvid}" + (f"?p={part}" if part > 1 else "")
        return ResolvedVideo(
            platform=self.platform,
            video_id=bvid,
            canonical_url=canonical,
            title=view.get("title", ""),
            duration=duration,
            streams=streams,
            part=part,
            parts=[Part(p.get("page"), p.get("part", ""), float(p.get("duration") or 0)) for p in pages],
            cover=view.get("pic", ""),
            author=(view.get("owner") or {}).get("name", ""),
            description=view.get("desc", ""),
            playable_duration=playable,
            notes=notes,
            audio_streams=self._dash_audio(play),
            extra={"bvid": bvid, "cid": page["cid"], "aid": view.get("aid"), "stats": {
                k: (view.get("stat") or {}).get(src) for k, src in
                (("views", "view"), ("likes", "like"), ("comments", "reply"), ("danmaku", "danmaku"), ("favorites", "favorite"))}},
        )

    async def _ids(self, video: ResolvedVideo) -> tuple[int, int]:
        """(aid, cid); sessions saved before aid was kept look it up again."""
        if not video.extra.get("aid"):
            video.extra["aid"] = (await self._view("bvid", video.extra.get("bvid") or video.video_id)).get("aid")
        return int(video.extra["aid"]), int(video.extra["cid"])

    async def related(self, video: ResolvedVideo) -> list[dict]:
        """B 站's 相关推荐 beside the player (no login needed)."""
        response = await self._get(f"{API}/x/web-interface/archive/related", params={"bvid": video.video_id})
        out = []
        for v in (response.json() or {}).get("data") or []:
            if not v.get("bvid"):
                continue
            out.append({"url": f"https://www.bilibili.com/video/{v['bvid']}/", "title": v.get("title") or "",
                        "author": (v.get("owner") or {}).get("name") or "", "duration": v.get("duration") or 0,
                        "views": (v.get("stat") or {}).get("view") or 0, "cover": (v.get("pic") or "").replace("http://", "https://")})
        return out

    async def comments(self, video: ResolvedVideo, sort: str = "hot", cursor: str | None = None) -> CommentPage:
        aid, _ = await self._ids(video)
        mode = COMMENT_SORT.get(sort, 3)
        login = settings().get("BILIBILI_COOKIE", "").strip()
        if login:
            payload = await self._api("/x/v2/reply/wbi/main", {
                "oid": aid, "type": 1, "mode": mode, "plat": 1, "web_location": 1315875,
                "pagination_str": json.dumps({"offset": cursor or ""}, separators=(",", ":"))}, login=login)
        else:
            payload = await self._api("/x/v2/reply/main", {"oid": aid, "type": 1, "mode": mode, "next": cursor or 0}, signed=False)
        code = payload.get("code", -1)
        if code == 12002:
            raise ResolveError("comments_closed", "这个视频的评论区已关闭")
        if code == -403 and login:
            raise ResolveError("login_expired", "B 站登录已失效：点右上角「账号」重新扫码登录")
        if code != 0:
            raise ResolveError("upstream", f"B 站评论接口返回错误（{code}）：{payload.get('message', '')}", retryable=True)
        data = payload.get("data") or {}
        top = [r for r in ((data.get("top_replies") or []) + [(data.get("upper") or {}).get("top")]) if r] if not cursor else []
        pinned_ids = {r.get("rpid") for r in top}
        items = [parse_comment(r, pinned=True) for r in top]
        items += [parse_comment(r) for r in (data.get("replies") or []) if r.get("rpid") not in pinned_ids]
        page_info = data.get("cursor") or {}
        if login:
            nxt = ((page_info.get("pagination_reply") or {}).get("next_offset")) or None
        else:
            nxt = None  # logged out there is nothing past the first page
        if page_info.get("is_end"):
            nxt = None
        total = page_info.get("all_count") or (video.extra.get("stats") or {}).get("comments")
        return CommentPage(items, total, nxt, "" if login else ANONYMOUS_NOTE)

    async def danmaku(self, video: ResolvedVideo) -> list[Danmaku]:
        _, cid = await self._ids(video)
        response = await self._get(f"https://comment.bilibili.com/{cid}.xml")
        if response.status_code != 200:
            raise ResolveError("upstream", f"读取弹幕失败（HTTP {response.status_code}）", retryable=True)
        return parse_danmaku(response.content.decode("utf-8", errors="replace"))

    async def hd_streams(self, video: ResolvedVideo) -> list[Stream]:
        """Picture tracks up to HD_HEIGHT with the person's own login (accounts: BILIBILI_COOKIE, the web
        demo's per-person overlay), for reading small print off the screen (抄作业, a note's figures).
        Logged out, Bilibili gives 480p at most; the keyframes stay at MAX_HEIGHT either way. [] when
        there is no login or it is refused."""
        login = settings().get("BILIBILI_COOKIE", "").strip()
        if not login:
            return []
        params = {"bvid": video.extra["bvid"], "cid": video.extra["cid"], "fnval": 16, "fnver": 0, "fourk": 0, "qn": 80}
        try:
            payload = await self._api("/x/player/wbi/playurl", params, login=login)
        except ResolveError:
            return []
        if payload.get("code") != 0:
            return []
        return self._dash_streams(payload.get("data") or {}, cap=HD_HEIGHT)

    async def play_streams(self, video: ResolvedVideo) -> list[Stream]:
        """An MP4 with picture and sound for watching the original (modules/playback): the html5 player's
        file at up to 1080p (asked for qn=80, tested 2026-10-19), else the low-resolution fallback.
        The DASH tracks frames are read from carry no sound, so they can't be played as they are."""
        try:
            play = await self._playurl(video.extra["bvid"], video.extra["cid"], fnval=1, qn=80, platform="html5", high_quality=1)
            found = self._durl_streams(play, "html5-mp4-hd")
        except ResolveError:
            found = []
        return found or await self.fallback_streams(video)

    async def fallback_streams(self, video: ResolvedVideo) -> list[Stream]:
        """The html5 player's single MP4: low resolution, but its CDN doesn't require a Referer."""
        try:
            play = await self._playurl(video.extra["bvid"], video.extra["cid"], fnval=1, qn=32, platform="html5", high_quality=1)
        except ResolveError:
            return []
        return self._durl_streams(play, "html5-mp4")
