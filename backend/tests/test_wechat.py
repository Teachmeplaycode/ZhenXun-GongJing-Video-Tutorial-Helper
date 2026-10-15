import asyncio
import json

import httpx
import pytest

from modules.video_source import ResolveError
from modules.video_source import wechat
from modules.video_source.wechat import WeChatChannelsResolver, short_uri

PLAYABLE = "https://channels.weixin.qq.com/finder-preview/pages/feed?token=TKN&eid=export%2FABC"


def resolver(handler, monkeypatch, cookie="hy_user=u; hy_token=t", duration=33.0):
    monkeypatch.setattr(wechat, "settings", lambda: {"YUANBAO_COOKIE": cookie} if cookie else {})

    async def probe(url, headers):
        return duration
    return WeChatChannelsResolver(transport=httpx.MockTransport(handler), probe=probe)


def feed_response(feed, err=0):
    return {"data": {"authorInfo": {"nickname": "科学探秘编辑部"}, "feedInfo": feed}, "errCode": err, "errMsg": ""}


def run(r, url="https://weixin.qq.com/sph/AaWZ4mB4x5"):
    return asyncio.run(r.resolve(url))


def test_short_uri_and_matches():
    assert short_uri("https://weixin.qq.com/sph/AaWZ4mB4x5") == "AaWZ4mB4x5"
    assert short_uri("https://channels.weixin.qq.com/finder-preview/pages/sph?id=AaWZ4mB4x5") == "AaWZ4mB4x5"
    r = WeChatChannelsResolver()
    assert r.matches("https://weixin.qq.com/sph/AaWZ4mB4x5")
    assert not r.matches("https://weixin.qq.com/") and not r.matches("https://www.bilibili.com/video/BV1")


def test_resolves_through_yuanbao_token(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "yuanbao.tencent.com":
            assert request.headers["cookie"] == "hy_user=u; hy_token=t"
            assert json.loads(request.content)["url"] == "https://weixin.qq.com/sph/AaWZ4mB4x5"
            return httpx.Response(200, json={"data": {"playable_url": PLAYABLE}})
        body = json.loads(request.content)
        assert body == {"baseReq": {"generalToken": "TKN"}, "exportId": "export/ABC"}
        return httpx.Response(200, json=feed_response({
            "mediaType": 4, "description": "吃柚子一定要当心！#科普知识", "coverUrl": "https://c",
            "h264VideoInfo": {"videoUrl": "https://finder.video.qq.com/v.mp4"}}))

    v = run(resolver(handler, monkeypatch))
    assert v.platform == "wechat_channels" and v.video_id == "AaWZ4mB4x5" and v.duration == 33.0
    assert v.title == "吃柚子一定要当心！" and v.author == "科学探秘编辑部"
    assert v.streams[0].url == v.audio_streams[0].url == "https://finder.video.qq.com/v.mp4"
    assert len(seen) == 2


def test_missing_cookie_and_expired_login(monkeypatch):
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(500), monkeypatch, cookie=""))
    assert e.value.code == "login_required" and "YUANBAO_COOKIE" in e.value.message

    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, json={"code": 401, "msg": "未登录"}), monkeypatch))
    assert e.value.code == "login_expired"


def test_album_and_deleted(monkeypatch):
    def album(request):
        if request.url.host == "yuanbao.tencent.com":
            return httpx.Response(200, json={"data": {"playable_url": PLAYABLE}})
        return httpx.Response(200, json=feed_response({"mediaType": 2, "picInfo": [{"url": "https://p"}]}))
    with pytest.raises(ResolveError) as e:
        run(resolver(album, monkeypatch))
    assert e.value.code == "unsupported_content"

    def deleted(request):
        if request.url.host == "yuanbao.tencent.com":
            return httpx.Response(200, json={"data": {"playable_url": PLAYABLE}})
        return httpx.Response(200, json=feed_response({}))
    with pytest.raises(ResolveError) as e:
        run(resolver(deleted, monkeypatch))
    assert e.value.code == "not_found"
