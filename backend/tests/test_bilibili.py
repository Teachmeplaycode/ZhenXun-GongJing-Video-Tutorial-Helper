import asyncio
import json

import httpx
import pytest

from modules.video_source import ResolveError, extract_url
from modules.video_source.bilibili import BilibiliResolver, mixin_key, parse_target, rank_urls, sign_wbi

IMG = "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
SUB = "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"


def run(coro):
    return asyncio.run(coro)


def make_api(view=None, play=None, *, risk_first=False, view_code=0):
    """Fake api.bilibili.com; records calls."""
    calls = []
    state = {"risk": risk_first}
    view = view or {
        "bvid": "BV1xx411c7mD", "aid": 2, "title": "测试视频", "duration": 120, "cid": 11, "pic": "cover.jpg",
        "owner": {"name": "UP"}, "desc": "简介",
        "pages": [{"page": 1, "cid": 11, "part": "P1", "duration": 120}, {"page": 2, "cid": 22, "part": "P2", "duration": 60}],
    }
    play = play or {
        "timelength": 120000,
        "dash": {"video": [
            {"height": 1080, "codecid": 7, "baseUrl": "https://cdn/1080.m4s?deadline=4102444800", "backupUrl": []},
            {"height": 720, "codecid": 12, "baseUrl": "https://cdn/720-hevc.m4s", "backupUrl": []},
            {"height": 720, "codecid": 7, "baseUrl": "https://x.mcdn.bilivideo.cn:4483/720.m4s",
             "backupUrl": ["https://upos-sz-mirrorcos.bilivideo.com/720.m4s"]},
        ]},
    }

    def handler(request: httpx.Request):
        path = request.url.path
        calls.append((path, dict(request.url.params)))
        if path.endswith("/finger/spi"):
            return httpx.Response(200, json={"code": 0, "data": {"b_3": "b3", "b_4": "b4"}})
        if path.endswith("/nav"):
            return httpx.Response(200, json={"code": -101, "data": {"wbi_img": {"img_url": IMG, "sub_url": SUB}}})
        if state["risk"]:
            state["risk"] = False
            return httpx.Response(412, text="blocked")
        if path.endswith("/wbi/view"):
            assert "w_rid" in request.url.params and "wts" in request.url.params
            if view_code:
                return httpx.Response(200, json={"code": view_code, "message": "x"})
            return httpx.Response(200, json={"code": 0, "data": view})
        if path.endswith("/wbi/playurl"):
            if request.url.params.get("platform") == "html5":
                return httpx.Response(200, json={"code": 0, "data": {"durl": [{"url": "https://cdn/h5.mp4", "backup_url": None}]}})
            return httpx.Response(200, json={"code": 0, "data": play})
        if request.url.host == "b23.tv":
            return httpx.Response(302, headers={"Location": "https://www.bilibili.com/video/BV1xx411c7mD?p=2&share_source=copy"})
        return httpx.Response(404)

    return httpx.MockTransport(handler), calls


def test_extract_url_from_share_text():
    assert extract_url("【测试】 https://b23.tv/AbCdEf 复制链接") == "https://b23.tv/AbCdEf"
    assert extract_url("看看 BV1xx411c7mD") == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert extract_url("av2") == "https://www.bilibili.com/video/av2"
    with pytest.raises(ResolveError) as e:
        extract_url("没有链接")
    assert e.value.code == "no_link"


def test_parse_target_variants():
    assert parse_target("https://www.bilibili.com/video/BV1xx411c7mD/?p=3") == ("bvid", "BV1xx411c7mD", 3)
    assert parse_target("https://m.bilibili.com/video/av2") == ("aid", "2", None)
    assert parse_target("https://www.bilibili.com/festival/x?bvid=BV1xx411c7mD") == ("bvid", "BV1xx411c7mD", None)
    with pytest.raises(ResolveError) as e:
        parse_target("https://www.bilibili.com/bangumi/play/ep1")
    assert e.value.code == "unsupported_content"
    with pytest.raises(ResolveError) as e:
        parse_target("https://space.bilibili.com/2")
    assert e.value.code == "not_video_page"


def test_matches_every_bilibili_host():
    r = BilibiliResolver()
    assert all(r.matches(u) for u in ("https://b23.tv/x", "https://live.bilibili.com/1", "https://m.bilibili.com/video/av2"))
    assert not r.matches("https://www.youtube.com/watch?v=x")
    assert not r.matches("https://notbilibili.com/video/BV1xx411c7mD")


def test_wbi_signature_is_deterministic():
    key = mixin_key("7cd084941338484aae1ad9425b84077c", "4932caff0ff746eab6f01bf08b70ac45")
    assert len(key) == 32
    signed = sign_wbi({"foo": "one!", "bar": "五"}, key, now=1702204169)
    assert signed["foo"] == "one" and signed["wts"] == "1702204169" and len(signed["w_rid"]) == 32
    assert signed == sign_wbi({"bar": "五", "foo": "one!"}, key, now=1702204169)


def test_rank_urls_moves_peer_cache_last():
    assert rank_urls(["https://a.mcdn.bilivideo.cn/x", "https://upos/x", "https://upos/x"]) == ["https://upos/x", "https://a.mcdn.bilivideo.cn/x"]


def test_resolve_picks_avc_within_720p_and_keeps_backups():
    transport, calls = make_api()
    video = run(BilibiliResolver(transport).resolve("https://www.bilibili.com/video/BV1xx411c7mD"))
    assert video.video_id == "BV1xx411c7mD" and video.duration == 120 and video.part == 1
    labels = [s.label for s in video.streams]
    # AVC 720p first, peer cache after the mirror, then the HEVC alternative; 1080p excluded.
    assert labels[0].startswith("dash-7-720p")
    assert "mirrorcos" in video.streams[0].url and "mcdn" in video.streams[1].url
    assert labels[2].startswith("dash-12-720p")
    assert all(s.headers["Referer"] == "https://www.bilibili.com/" for s in video.streams)
    assert [p.index for p in video.parts] == [1, 2]
    assert "streams" not in json.dumps(video.public())


def test_short_link_and_part():
    transport, calls = make_api()
    video = run(BilibiliResolver(transport).resolve("https://b23.tv/AbCdEf"))
    assert video.part == 2 and video.duration == 60
    assert video.canonical_url.endswith("?p=2")
    assert any(params.get("cid") == "22" for path, params in calls if path.endswith("playurl"))


def test_missing_part():
    transport, _ = make_api()
    with pytest.raises(ResolveError) as e:
        run(BilibiliResolver(transport).resolve("https://www.bilibili.com/video/BV1xx411c7mD?p=9"))
    assert e.value.code == "part_not_found"


def test_risk_control_resets_session_and_retries_once():
    transport, calls = make_api(risk_first=True)
    video = run(BilibiliResolver(transport).resolve("https://www.bilibili.com/video/BV1xx411c7mD"))
    assert video.title == "测试视频"
    assert sum(1 for p, _ in calls if p.endswith("/finger/spi")) == 2


@pytest.mark.parametrize("code,expected", [(-404, "not_found"), (62004, "unavailable"), (-403, "forbidden")])
def test_view_errors_are_mapped(code, expected):
    transport, _ = make_api(view_code=code)
    with pytest.raises(ResolveError) as e:
        run(BilibiliResolver(transport).resolve("https://www.bilibili.com/video/BV1xx411c7mD"))
    assert e.value.code == expected


def test_trial_is_reported_not_fatal():
    play = {"timelength": 30000, "is_preview": 1,
            "dash": {"video": [{"height": 480, "codecid": 7, "baseUrl": "https://cdn/480.m4s"}]}}
    transport, _ = make_api(play=play)
    video = run(BilibiliResolver(transport).resolve("https://www.bilibili.com/video/BV1xx411c7mD"))
    assert video.playable_duration == 30 and video.notes


def test_fallback_streams_use_html5_mp4():
    transport, _ = make_api()
    resolver = BilibiliResolver(transport)
    video = run(resolver.resolve("https://www.bilibili.com/video/BV1xx411c7mD"))
    extra = run(resolver.fallback_streams(video))
    assert [s.url for s in extra] == ["https://cdn/h5.mp4"]


def test_classify_ignores_hex_addresses():
    from modules.frames.grabber import classify
    assert classify("[vost#0:0/mjpeg @ 0xc50c44000] Terminating thread with return code -22 (Invalid argument)") == "error"
    assert classify("Server returned 403 Forbidden (access denied)") == "forbidden"
    assert classify("HTTP error 404 Not Found") == "forbidden"


def test_hd_streams_use_the_persons_login_and_go_up_to_1080p(monkeypatch):
    from modules import settings as config

    transport, calls = make_api()
    resolver = BilibiliResolver(transport)
    video = run(resolver.resolve("https://www.bilibili.com/video/BV1xx411c7mD"))
    monkeypatch.setattr(config, "overlay", config.overlay)
    token = config.overlay.set({"BILIBILI_COOKIE": ""})
    assert run(resolver.hd_streams(video)) == []  # logged out: nothing sharper to ask for
    config.overlay.reset(token)
    token = config.overlay.set({"BILIBILI_COOKIE": "SESSDATA=s; bili_jct=j"})
    seen = []
    original = transport.handle_async_request

    async def spy(request):
        if request.url.path.endswith("/wbi/playurl"):
            seen.append((dict(request.url.params).get("qn"), request.headers.get("cookie", "")))
        return await original(request)

    transport.handle_async_request = spy
    streams = run(resolver.hd_streams(video))
    config.overlay.reset(token)
    assert streams[0].label.startswith("dash-7-1080p")  # past MAX_HEIGHT, for small print
    assert seen and seen[-1][0] == "80" and "SESSDATA=s" in seen[-1][1]
