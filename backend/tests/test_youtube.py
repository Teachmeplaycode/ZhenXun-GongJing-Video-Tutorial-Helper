import asyncio
import json

import httpx
import pytest

from modules.video_source import ResolveError
from modules.video_source.youtube import YouTubeResolver, parse_target


def run(coro):
    return asyncio.run(coro)


def player_response(*, status="OK", reason="", video_id="dQw4w9WgXcQ", title="测试视频", length=120,
                    formats=None, adaptive=None, signed=False):
    fmts = formats if formats is not None else [
        {"itag": 18, "url": "https://cdn/muxed.mp4", "mimeType": "video/mp4", "qualityLabel": "360p", "height": 360},
    ]
    if signed:
        fmts = [{"itag": 18, "signatureCipher": "s=AAA&url=https://cdn/muxed.mp4",
                 "mimeType": "video/mp4", "qualityLabel": "360p", "height": 360}]
    return {
        "playabilityStatus": {"status": status, **({"reason": reason} if reason else {})},
        "videoDetails": {"videoId": video_id, "title": title, "lengthSeconds": str(length),
                         "author": "UP", "shortDescription": "简介",
                         "thumbnail": {"thumbnails": [{"url": "https://t/cover.jpg"}]}},
        "streamingData": {"formats": fmts, "adaptiveFormats": adaptive or []},
    }


def watch_html(payload):
    return f"<html><script>var ytInitialPlayerResponse = {json.dumps(payload)};</script></html>"


def resolver(handler):
    return YouTubeResolver(transport=httpx.MockTransport(handler))


def test_parse_target_variants():
    assert parse_target("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_target("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_target("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_target("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    with pytest.raises(ResolveError) as e:
        parse_target("https://www.youtube.com/watch?v=short")
    assert e.value.code == "unsupported_link"


def test_matches_youtube_hosts():
    r = YouTubeResolver()
    assert all(r.matches(u) for u in (
        "https://www.youtube.com/watch?v=x", "https://youtu.be/x", "https://m.youtube.com/watch?v=x"))
    assert not r.matches("https://www.bilibili.com/video/BV1xx411c7mD")
    assert not r.matches("https://v.douyin.com/abc/")


def test_resolve_ok():
    payload = player_response()

    def handler(request):
        assert request.url.params.get("v") == "dQw4w9WgXcQ"
        return httpx.Response(200, text=watch_html(payload))

    v = run(resolver(handler).resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert v.platform == "youtube" and v.video_id == "dQw4w9WgXcQ"
    assert v.title == "测试视频" and v.duration == 120 and v.author == "UP"
    assert v.streams[0].url == "https://cdn/muxed.mp4"
    assert v.canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert "streams" not in json.dumps(v.public())


def test_resolve_with_audio_adaptive():
    payload = player_response(formats=[], adaptive=[
        {"itag": 137, "url": "https://cdn/v.mp4", "mimeType": "video/mp4; codecs=avc1", "height": 1080},
        {"itag": 251, "url": "https://cdn/a.weba", "mimeType": "audio/webm; codecs=opus"},
    ])
    v = run(resolver(lambda r: httpx.Response(200, text=watch_html(payload))).resolve("https://youtu.be/dQw4w9WgXcQ"))
    assert v.streams[0].url == "https://cdn/v.mp4"
    assert v.audio_streams[0].url == "https://cdn/a.weba"


@pytest.mark.parametrize("status,code", [
    ("UNPLAYABLE", "unavailable"), ("LOGIN_REQUIRED", "login_required"),
    ("PRIVATE", "forbidden"), ("AGE_CHECK_REQUIRED", "login_required"),
])
def test_playability_errors(status, code):
    payload = player_response(status=status, reason="x")
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, text=watch_html(payload))).resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert e.value.code == code


def test_missing_player_response():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(200, text="<html>no player</html>")).resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert e.value.code == "upstream"


def test_signed_formats_produce_note():
    payload = player_response(signed=True)
    v = run(resolver(lambda r: httpx.Response(200, text=watch_html(payload))).resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert v.streams[0].url == "https://cdn/muxed.mp4"
    assert v.notes and "yt-dlp" in v.notes[0]


def test_not_found_and_server_error():
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(404)).resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert e.value.code == "not_found"
    with pytest.raises(ResolveError) as e:
        run(resolver(lambda r: httpx.Response(500)).resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert e.value.code == "upstream"
