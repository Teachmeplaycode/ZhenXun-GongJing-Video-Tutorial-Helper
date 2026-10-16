"""What viewers left: Bilibili comments and danmaku, and the read_comments / read_danmaku tools."""
import asyncio

import httpx

from modules.agent.tools import AgentTools, definitions
from modules.frames import FrameJob
from modules.video_source import ResolvedVideo, Stream
from modules.video_source.base import Comment, CommentPage, Danmaku
from modules.video_source.bilibili import ANONYMOUS_NOTE, BilibiliResolver, parse_danmaku

DM_XML = """<?xml version="1.0" encoding="UTF-8"?><i><chatid>11</chatid>
<d p="30.5,1,25,16777215,1790000000,0,a,1,9">前方高能</d>
<d p="2.0,1,25,16777215,1790000000,0,a,2,9">开头</d>
<d p="31.0,1,25,16777215,1790000000,0,a,3,9">前方高能</d>
<d p="bad,1">坏的</d><d p="40,1">   </d></i>"""


def reply(rpid, name, text, like=0, sub=()):
    return {"rpid": rpid, "member": {"uname": name}, "content": {"message": text}, "like": like, "rcount": len(sub),
            "ctime": 1790000000, "replies": [reply(rpid * 10 + i, n, t) for i, (n, t) in enumerate(sub)]}


def bili(monkeypatch, cookie=""):
    calls = []
    monkeypatch.setenv("BILIBILI_COOKIE", cookie)

    def handler(request: httpx.Request):
        path = request.url.path
        calls.append((path, dict(request.url.params), request.headers.get("cookie", "")))
        if path.endswith("/finger/spi"):
            return httpx.Response(200, json={"code": 0, "data": {"b_3": "b3", "b_4": "b4"}})
        if path.endswith("/nav"):
            return httpx.Response(200, json={"code": -101, "data": {"wbi_img": {
                "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
                "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"}}})
        if path.endswith("/wbi/view"):
            return httpx.Response(200, json={"code": 0, "data": {"aid": 2, "bvid": "BV1xx411c7mD"}})
        if path == "/x/v2/reply/main":
            return httpx.Response(200, json={"code": 0, "data": {
                "cursor": {"is_end": False, "all_count": 900},
                "top_replies": [reply(1, "UP", "置顶说明")],
                "replies": [reply(1, "UP", "置顶说明"), reply(2, "甲", "第一", 50, [("乙", "同意")])]}})
        if path == "/x/v2/reply/wbi/main":
            offset = request.url.params["pagination_str"]
            last = "p2" in offset
            return httpx.Response(200, json={"code": 0, "data": {
                "cursor": {"is_end": last, "all_count": 900, "pagination_reply": {"next_offset": "" if last else "p2"}},
                "replies": [reply(3 if last else 2, "丙" if last else "甲", "第二页" if last else "第一")]}})
        if request.url.host == "comment.bilibili.com":
            return httpx.Response(200, text=DM_XML)
        return httpx.Response(404)

    return BilibiliResolver(transport=httpx.MockTransport(handler)), calls


def old_video():
    # Saved before aid was kept: only bvid and cid.
    return ResolvedVideo("bilibili", "BV1xx411c7mD", "https://www.bilibili.com/video/BV1xx411c7mD", "t", 60.0,
                         [], extra={"bvid": "BV1xx411c7mD", "cid": 11})


def test_parse_danmaku_sorts_and_skips_broken():
    assert parse_danmaku(DM_XML) == [Danmaku(2.0, "开头"), Danmaku(30.5, "前方高能"), Danmaku(31.0, "前方高能")]


def test_anonymous_comments_are_the_first_page_with_a_note(monkeypatch):
    resolver, calls = bili(monkeypatch)
    video = old_video()
    page = asyncio.run(resolver.comments(video, "hot"))
    assert video.extra["aid"] == 2  # looked up once for an old session
    assert [c.author for c in page.comments] == ["UP", "甲"] and page.comments[0].pinned
    assert page.comments[1].replies[0].text == "同意"
    assert page.total == 900 and page.cursor is None and page.note == ANONYMOUS_NOTE
    assert calls[-1][1]["mode"] == "3" and calls[-1][1]["oid"] == "2"


def test_logged_in_comments_page_with_the_cookie(monkeypatch):
    resolver, calls = bili(monkeypatch, cookie="SESSDATA=secret")
    video = old_video()
    first = asyncio.run(resolver.comments(video, "time"))
    second = asyncio.run(resolver.comments(video, "time", first.cursor))
    assert first.cursor == "p2" and second.cursor is None and not first.note
    assert [c.text for c in second.comments] == ["第二页"]
    reply_calls = [c for c in calls if c[0] == "/x/v2/reply/wbi/main"]
    assert all("SESSDATA=secret" in cookie and "buvid3=b3" in cookie for _, _, cookie in reply_calls)
    assert reply_calls[0][1]["mode"] == "2" and "w_rid" in reply_calls[0][1]


class Viewers:
    audience = ("comments", "danmaku")

    def __init__(self, danmaku=(), pages=()):
        self.items, self.pages, self.calls = list(danmaku), list(pages), []

    async def danmaku(self, video):
        self.calls.append("danmaku")
        return self.items

    async def comments(self, video, sort="hot", cursor=None):
        self.calls.append(("comments", sort, cursor))
        return self.pages[int(cursor or 0)]


def job_with(tmp_path, resolver, duration=100.0, stats=None):
    v = ResolvedVideo("bilibili", "BV1", "u", "t", duration, [Stream("https://v", {}, "s")], extra={"stats": stats or {}})
    return FrameJob("j", v, resolver, tmp_path / "j", count=2)


def test_viewer_tools_follow_the_platform():
    names = lambda d: {x["function"]["name"] for x in d}  # noqa: E731
    assert {"read_comments", "read_danmaku"} <= names(definitions(web=False, audience=("comments", "danmaku")))
    assert "read_comments" not in names(definitions())


def test_read_danmaku_merges_repeats_finds_peaks_and_filters(tmp_path):
    items = [Danmaku(5, "开头")] + [Danmaku(50 + i * 0.1, "前方高能") for i in range(6)] + [Danmaku(80, "结束了")]
    resolver = Viewers(items)
    tools = AgentTools(job_with(tmp_path, resolver, stats={"danmaku": 500}))
    r = asyncio.run(tools.run("read_danmaku", {}))
    assert "共 8 条弹幕" in r.text and "视频共有 500 条" in r.text
    assert "[00:50] 前方高能 ×6" in r.text and r.data["peaks"][0]["count"] == 1 and max(p["count"] for p in r.data["peaks"]) == 6
    assert sum(r.data["bins"]) == 8 and len(r.data["bins"]) == 48
    r = asyncio.run(tools.run("read_danmaku", {"start": "01:00", "end": "01:40", "query": "结束"}))
    assert r.count == 1 and r.data["hits"] == [{"t": 80, "text": "结束了", "n": 1}]
    assert resolver.calls == ["danmaku"]  # fetched once per job


def test_read_comments_pages_and_marks_viewers(tmp_path):
    pages = [CommentPage([Comment("甲", "好看", likes=3, reply_count=1, replies=[Comment("乙", "同意")])], 2, "1"),
             CommentPage([Comment("丙", "第二页")], 2, None)]
    resolver = Viewers(pages=pages)
    tools = AgentTools(job_with(tmp_path, resolver))
    r = asyncio.run(tools.run("read_comments", {"page": 2}))
    assert "丙" in r.text and "观众" in r.text.splitlines()[0]
    assert resolver.calls == [("comments", "hot", None), ("comments", "hot", "1")]
    r = asyncio.run(tools.run("read_comments", {}))
    assert "↳ 乙" in r.text and "page=2" in r.text and len(resolver.calls) == 2
    r = asyncio.run(tools.run("read_comments", {"page": 3}))
    assert r.error and "只有 2 页" in r.text


def test_platform_without_viewers_gets_no_tool(tmp_path):
    class Plain:
        audience = ()

    tools = AgentTools(job_with(tmp_path, Plain()))
    assert asyncio.run(tools.run("read_comments", {})).error
