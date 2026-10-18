import asyncio
import json
from urllib.parse import quote

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


def test_unknown_decoded_page_is_retryable_instead_of_deleted():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, text=share_html({"loaderData": {}}))).resolve("https://www.douyin.com/video/7123456789"))
    assert e.value.code == "upstream"
    assert e.value.retryable is True


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


@pytest.mark.parametrize("tag", [
    '<script id="RENDER_DATA" type="application/json">{body}</script>',
    "<script type='application/json' id = 'RENDER_DATA'>\n{body}\n</script>",
    '<SCRIPT TYPE="application/json" ID="RENDER_DATA">{body}</SCRIPT>',
])
def test_url_encoded_render_script_body_is_parsed(tag):
    blob = aweme(desc="中文 A+B 和花括号 } #科普")
    html = '<html><script data-id="RENDER_DATA">invalid distractor</script>' + tag.format(body=quote(json.dumps(blob))) + '</html>'
    v = run(resolver(lambda r: httpx.Response(200, text=html)).resolve("https://www.douyin.com/video/7123456789"))
    assert v.video_id == "7123456789" and v.duration == 33
    assert v.title == "中文 A+B 和花括号 }"
    assert v.author == "测试作者"
    assert [s.url for s in v.streams] == ["https://aweme.snssdk.com/ugc/play?v=1"]
    assert v.audio_streams == v.streams


@pytest.mark.parametrize("html", ['<script id="RENDER_DATA" type="application/json">%7Binvalid</script>',
                                 '<script data-id="RENDER_DATA">{}</script>'])
def test_invalid_or_unrelated_render_script_is_retryable(html):
    with pytest.raises(ResolveError) as error:
        run(resolver(lambda r: httpx.Response(200, text=html)).resolve("https://www.douyin.com/video/7123456789"))
    assert error.value.code == "upstream" and error.value.retryable


@pytest.mark.parametrize("status,code,retryable", [(401, "login_required", False),
                                                (403, "forbidden", False),
                                                (429, "rate_limited", True)])
@pytest.mark.parametrize("stage", ["direct", "shortlink", "redirected"])
def test_http_restrictions_are_mapped_before_body_parsing(status, code, retryable, stage):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if stage == "redirected" and request.url.host == "v.douyin.com":
            return httpx.Response(302, headers={"Location": "https://www.douyin.com/video/7123456789"})
        return httpx.Response(status, text="<html>not a video payload</html>")

    url = "https://www.douyin.com/video/7123456789" if stage == "direct" else "https://v.douyin.com/AbCdEf/"
    with pytest.raises(ResolveError) as error:
        run(resolver(handler).resolve(url))
    assert error.value.code == code and error.value.retryable is retryable
    assert len(requests) == (2 if stage == "redirected" else 1)


@pytest.mark.parametrize("status,code,retryable", [
    ({"status_code": 2100}, "not_found", False),
    ({"status_code": "2100"}, "not_found", False),
    ({"status_msg": "该视频已删除"}, "not_found", False),
    ({"status_info": "视频已下架"}, "not_found", False),
    ({"status_code": 8}, "login_required", False),
    ({"status_msg": "请登录后查看，登录限制导致无法查看"}, "login_required", False),
    ({"status_msg": "Login required"}, "login_required", False),
    ({"status_code": 2095}, "forbidden", False),
    ({"status_msg": "该内容在当前地区不可用"}, "forbidden", False),
    ({"filter_list": [{"reason": "region"}]}, "forbidden", False),
    ({"status_code": 0, "status_msg": "success", "item_list": []}, "upstream", True),
    ({"status_msg": "无法查看"}, "upstream", True),
    ({"status_code": "unknown", "status_info": {"message": "changed schema"}}, "upstream", True),
])
def test_decoded_missing_aweme_uses_explicit_status(status, code, retryable):
    # A valid outer envelope often has status_code=0; its nested error must still be examined.
    blob = {"status_code": 0, "loaderData": {"video_(id)/page": {"videoInfoRes": status}}}
    with pytest.raises(ResolveError) as error:
        run(resolver(lambda r: httpx.Response(200, text=share_html(blob))).resolve("https://www.douyin.com/video/7123456789"))
    assert error.value.code == code
    assert error.value.retryable is retryable


def test_short_link_to_note_matches_direct_note_error_without_video_request():
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.host == "v.douyin.com":
            return httpx.Response(302, headers={"Location": "https://www.douyin.com/note/7123456789"})
        assert request.url.path == "/note/7123456789"
        return httpx.Response(200, text="<html>图文</html>")

    r = resolver(handler)
    with pytest.raises(ResolveError) as short_error:
        run(r.resolve("https://v.douyin.com/AbCdEf/"))
    with pytest.raises(ResolveError) as direct_error:
        run(r.resolve("https://www.douyin.com/note/7123456789"))
    assert short_error.value.code == direct_error.value.code == "unsupported_content"
    assert short_error.value.retryable is direct_error.value.retryable is False
    assert len(requests) == 2
