import asyncio
import json

import httpx
import pytest

from modules.video_source import ResolveError
from modules.video_source.douyin import DouyinResolver, parse_target


def run(coro):
    return asyncio.run(coro)


def share_html(blob):
    return f"<html><script>window._ROUTER_DATA = {json.dumps(blob)};</script></html>"


def aweme(video_id="7123456789", desc="测试抖音视频 #科普", duration_ms=33000):
    return {"loaderData": {"video_(id)/page": {"videoInfoRes": {"item_list": [
        {"aweme_id": video_id, "desc": desc, "author": {"nickname": "测试作者"},
         "statistics": {"digg_count": 1234},
         "video": {"duration": duration_ms,
                   "play_addr": {"url_list": ["https://aweme.snssdk.com/ugc/playwm?v=1"]},
                   "cover": {"url_list": ["https://p/cover.jpg"]}}}]}}}}


def resolver(handler):
    return DouyinResolver(transport=httpx.MockTransport(handler))


def test_parse_target_variants():
    assert parse_target("https://www.douyin.com/video/7123456789") == ("video", "7123456789")
    assert parse_target("https://www.douyin.com/note/7123456789") == ("note", "7123456789")
    assert parse_target("https://v.douyin.com/AbCdEf/") == ("short", "AbCdEf")
    with pytest.raises(ResolveError) as e:
        parse_target("https://www.douyin.com/")
    assert e.value.code == "unsupported_link"


def test_matches_douyin_hosts():
    r = DouyinResolver()
    assert all(r.matches(u) for u in (
        "https://www.douyin.com/video/1", "https://v.douyin.com/abc/", "https://iesdouyin.com/share/1"))
    assert not r.matches("https://www.youtube.com/watch?v=x")
    assert not r.matches("https://www.bilibili.com/video/BV1xx411c7mD")


def test_resolve_ok():
    def handler(request):
        if request.url.host == "v.douyin.com":
            return httpx.Response(302, headers={"Location": "https://www.douyin.com/video/7123456789"})
        return httpx.Response(200, text=share_html(aweme()))

    v = run(resolver(handler).resolve("https://v.douyin.com/AbCdEf/"))
    assert v.platform == "douyin" and v.video_id == "7123456789"
    assert v.duration == 33.0 and v.title == "测试抖音视频"
    assert v.author == "测试作者"
    assert "playwm" not in v.streams[0].url
    assert v.canonical_url == "https://www.douyin.com/video/7123456789"


def test_resolve_direct_video_url():
    v = run(resolver(lambda r: httpx.Response(200, text=share_html(aweme()))).resolve("https://www.douyin.com/video/7123456789"))
    assert v.video_id == "7123456789" and v.duration == 33.0


def test_note_is_unsupported():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, text=share_html(aweme()))).resolve("https://www.douyin.com/note/7123456789"))
    assert e.value.code == "unsupported_content"


def test_missing_share_data():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, text="<html>nothing</html>")).resolve("https://www.douyin.com/video/7123456789"))
    assert e.value.code == "upstream"


def test_aweme_not_found():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, text=share_html({"loaderData": {}}))).resolve("https://www.douyin.com/video/7123456789"))
    assert e.value.code == "not_found"


def test_short_link_not_video_page():
    def handler(request):
        if request.url.host == "v.douyin.com":
            return httpx.Response(302, headers={"Location": "https://www.douyin.com/user/abc"})
        return httpx.Response(200, text="<html></html>")

    with pytest.raises(ResolveError) as e:
        run(resolver(handler).resolve("https://v.douyin.com/AbCdEf/"))
    assert e.value.code == "unsupported_link"


def test_not_found_status():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(404)).resolve("https://www.douyin.com/video/7123456789"))
    assert e.value.code == "not_found"
