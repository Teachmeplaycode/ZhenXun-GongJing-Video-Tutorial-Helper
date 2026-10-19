import asyncio

import pytest

from modules.video_source import xhs_comments
from modules.video_source.alcedo import AlcedoResolver
from modules.video_source.base import ResolveError, ResolvedVideo

RAW = [
    {"has_more": True, "comments": [
        {"content": "下转评论区的第二部分在这", "like_count": "1.2万", "sub_comment_count": "2", "create_time": 1760000000000,
         "user_info": {"nickname": "诸葛苍"}, "show_tags": ["is_author"],
         "sub_comments": [{"content": "写得好", "like_count": "3", "user_info": {"nickname": "路人"}}]},
        {"content": "哭了[皱眉R]", "like_count": "", "user_info": {"nickname": "甲"}}]},
    {"has_more": True, "comments": [{"content": "第二页", "user_info": {"nickname": "乙"}}]},
]


def video(platform="redbook"):
    return ResolvedVideo(platform=platform, video_id="v", canonical_url="https://www.xiaohongshu.com/explore/1?xsec_token=t",
                         title="t", duration=1, streams=[])


def test_captured_pages_become_comment_pages():
    pages = xhs_comments.to_pages(RAW, 12)
    first = pages[0].comments[0]
    assert (first.author, first.likes, first.reply_count, first.pinned) == ("诸葛苍", 12000, 2, True)
    assert first.replies[0].text == "写得好" and first.time == 1760000000
    assert pages[0].cursor == "1" and pages[0].total == 12
    assert pages[1].cursor is None and "前 2 页" in pages[1].note  # more exist than one visit reads


def test_cookie_string_becomes_browser_cookies():
    assert xhs_comments.cookies_of("a1=x; web_session=y;") == [
        {"name": "a1", "value": "x", "domain": ".xiaohongshu.com", "path": "/"},
        {"name": "web_session", "value": "y", "domain": ".xiaohongshu.com", "path": "/"}]


def test_only_xiaohongshu_sessions_offer_comments():
    r = AlcedoResolver()
    assert r.audience_for(video()) == ("comments",)
    assert r.audience_for(video("douyin")) == ()
    with pytest.raises(ResolveError):
        asyncio.run(r.comments(video("douyin")))


def test_without_a_login_the_agent_is_told_how_to_add_one(monkeypatch):
    monkeypatch.setattr(xhs_comments, "settings", lambda: {})
    with pytest.raises(ResolveError, match="账号"):
        asyncio.run(xhs_comments.comments("https://www.xiaohongshu.com/explore/1"))


def test_one_visit_serves_every_page(monkeypatch):
    visits = []

    async def visit(url, cookie):
        visits.append(url)
        return xhs_comments.to_pages(RAW, None)
    monkeypatch.setattr(xhs_comments, "settings", lambda: {"XHS_COOKIE": "a1=x; web_session=y"})
    monkeypatch.setattr(xhs_comments, "_visit", visit)
    monkeypatch.setattr(xhs_comments, "_cache", {})
    first = asyncio.run(xhs_comments.comments("u"))
    second = asyncio.run(xhs_comments.comments("u", first.cursor))
    assert second.comments[0].text == "第二页" and visits == ["u"]


def test_sticker_codes_are_taken_out_of_comments():
    assert xhs_comments.to_pages(RAW, None)[0].comments[1].text == "哭了"
