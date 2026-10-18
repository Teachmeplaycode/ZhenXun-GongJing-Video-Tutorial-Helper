"""Links through alcedo: its JSON as our ResolvedVideo, its errors as ours, and where it is tried."""
import asyncio
import json
import stat

import httpx
import pytest

from modules.video_source import alcedo
from modules.video_source.alcedo import AlcedoResolver, to_video
from modules.video_source.base import ResolveError, ResolvedVideo, Resolver, Stream
from modules.video_source.registry import Registry

YOUTUBE = {
    "source": "youtube", "title": "Rick Astley - Never Gonna Give You Up", "duration": 213.0,
    "page_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "cover_url": "https://i.ytimg.com/x.jpg",
    "author": {"name": "Rick Astley"}, "expires_at": 1792362699,
    "formats": [
        {"label": "2160p AV1", "height": 2160, "codec": "AV1", "video_url": "https://v/2160av1", "audio_url": "https://a/140"},
        {"label": "1080p", "height": 1080, "codec": "", "video_url": "https://v/1080", "audio_url": "https://a/140"},
        {"label": "720p", "height": 720, "codec": "", "video_url": "https://v/720", "audio_url": "https://a/140"},
        {"label": "480p", "height": 480, "codec": "", "video_url": "https://v/480", "audio_url": "https://a/139"},
        {"label": "仅音频", "url": "https://a/251", "ext": "m4a"},  # no height: sound only, never a picture stream
    ],
}
DOUYIN = {"source": "douyin", "title": "跳舞", "duration": 15.0, "page_url": "https://www.douyin.com/video/1",
          "video_url": "https://v/douyin.mp4", "video_headers": {"Referer": "https://www.douyin.com/"},
          "formats": [{"label": "1080p", "height": 1080, "url": "https://v/douyin-1080.mp4", "codec": "H.265"}]}


def test_tracks_become_streams_h264_near_720p_first():
    v = to_video(YOUTUBE, "https://youtu.be/dQw4w9WgXcQ")
    assert v.platform == "youtube" and v.video_id.startswith("youtube-") and v.duration == 213
    assert [s.url for s in v.streams] == ["https://v/720", "https://v/480", "https://v/1080", "https://v/2160av1"]
    assert [s.url for s in v.audio_streams] == ["https://a/140", "https://a/139", "https://a/251"]
    assert v.streams[0].expires_at == 1792362699 and v.author == "Rick Astley" and v.extra["resolver"] == "alcedo"
    assert to_video(YOUTUBE, "x").video_id == v.video_id  # stable: a refresh finds the same video


def test_a_combined_file_carries_its_sound_and_the_headers():
    v = to_video(DOUYIN, "https://v.douyin.com/abc/")
    assert [s.url for s in v.streams] == ["https://v/douyin-1080.mp4"] and v.audio_streams[0].url == "https://v/douyin-1080.mp4"
    assert v.streams[0].headers == {"Referer": "https://www.douyin.com/"}


def test_an_image_post_is_explained():
    with pytest.raises(ResolveError) as e:
        to_video({"source": "redbook", "images": [{"url": "a"}, {"url": "b"}]}, "u")
    assert e.value.code == "images_only" and "2 张图" in e.value.message


def fake_binary(tmp_path, stdout="", stderr="", code=0):
    """A stand-in alcedo: prints what it's told and records its environment."""
    script = tmp_path / "alcedo"
    script.write_text("#!/bin/sh\n"
                      f"env > {tmp_path}/env.txt\n"
                      f"cat <<'EOF_OUT'\n{stdout}\nEOF_OUT\n"
                      f"cat >&2 <<'EOF_ERR'\n{stderr}\nEOF_ERR\n"
                      f"exit {code}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture
def conf(monkeypatch):
    values = {}
    monkeypatch.setattr(alcedo, "settings", lambda: values)
    monkeypatch.setattr(alcedo, "fake_ip_dns", lambda: True)
    return values


def test_the_binary_gets_our_logins_and_the_fake_ip_setting(tmp_path, conf):
    conf.update(ALCEDO_BIN=str(fake_binary(tmp_path, stdout=json.dumps(YOUTUBE))), BILIBILI_COOKIE="SESSDATA=secret")
    v = asyncio.run(AlcedoResolver().resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    env = (tmp_path / "env.txt").read_text()
    assert v.title.startswith("Rick") and "ALCEDO_BILI_COOKIE=SESSDATA=secret" in env and "ALCEDO_SSRF_DNS=0" in env


def test_alcedo_failures_become_ours(tmp_path, conf):
    conf.update(ALCEDO_BIN=str(fake_binary(tmp_path, stderr="解析失败 [login] 平台要求登录（需要 cookie https://x）", code=1)))
    with pytest.raises(ResolveError) as e:
        asyncio.run(AlcedoResolver().resolve("https://www.xiaohongshu.com/explore/1"))
    assert e.value.code == "login_required" and e.value.message.startswith("平台要求登录") and "https://" not in e.value.message
    conf.update(ALCEDO_BIN=str(fake_binary(tmp_path, stderr="解析失败 [blocked] 412", code=1)))
    with pytest.raises(ResolveError) as e:
        asyncio.run(AlcedoResolver().resolve("https://www.douyin.com/video/1"))
    assert e.value.code == "rate_limited" and e.value.retryable


def test_without_alcedo_nothing_changes(conf, monkeypatch):
    monkeypatch.setattr(alcedo, "find_binary", lambda: None)
    assert not AlcedoResolver().matches("https://www.douyin.com/video/1")


def test_the_service_is_used_when_configured(conf, monkeypatch):
    conf.update(ALCEDO_URL="http://127.0.0.1:7878/", ALCEDO_SERVE_TOKEN="t")
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), auth=request.headers.get("authorization"))
        if "deleted" in str(request.url):
            return httpx.Response(404, json={"reason": "deleted", "message": "内容没了"})
        return httpx.Response(200, json=DOUYIN)

    real = httpx.AsyncClient
    monkeypatch.setattr(alcedo.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    v = asyncio.run(AlcedoResolver().resolve("https://v.douyin.com/abc/"))
    assert v.platform == "douyin" and seen["url"].startswith("http://127.0.0.1:7878/parse?url=") and seen["auth"] == "Bearer t"
    with pytest.raises(ResolveError) as e:
        asyncio.run(AlcedoResolver().resolve("https://v.douyin.com/deleted/"))
    assert e.value.code == "not_found"


class Flaky(Resolver):
    platform = "bilibili"

    def __init__(self, code):
        self.code = code

    def matches(self, url):
        return "bilibili" in url

    async def resolve(self, url, part=None):
        raise ResolveError(self.code, "B 站风控")


class Backup(Resolver):
    platform = "alcedo"

    def __init__(self, ok=True):
        self.ok = ok

    def matches(self, url):
        return True

    async def resolve(self, url, part=None):
        if not self.ok:
            raise ResolveError("upstream", "alcedo 也失败了")
        return ResolvedVideo("bilibili", "BV1", url, "t", 10, [Stream("https://v", {}, "s")])


def test_a_bilibili_failure_gets_a_second_try_through_alcedo():
    url = "https://www.bilibili.com/video/BV1atp96AE8j/"
    r, v = asyncio.run(Registry([Flaky("risk_control"), Backup()]).resolve(url))
    assert isinstance(r, Backup) and v.title == "t"
    with pytest.raises(ResolveError) as e:  # both fail: the first reason is shown
        asyncio.run(Registry([Flaky("risk_control"), Backup(ok=False)]).resolve(url))
    assert e.value.message == "B 站风控"
    with pytest.raises(ResolveError):  # not a pushback: no second try
        asyncio.run(Registry([Flaky("part_not_found"), Backup()]).resolve(url))


@pytest.mark.parametrize("url,part", [
    ("https://www.bilibili.com/video/BV1GY4y1V7P8/?p=13", None),
    ("https://m.bilibili.com/video/BV1GY4y1V7P8/?%70=13", None),
    ("https://www.bilibili.com/video/BV1GY4y1V7P8/", 13),
    ("https://www.bilibili.com/video/BV1GY4y1V7P8/", 1),
    ("https://b23.tv/example", None),
    ("https://bili2233.cn/example", None),
])
def test_bilibili_fallback_never_changes_a_part_or_guesses_a_short_link(url, part):
    class Native(Flaky):
        def matches(self, url):
            return True

    class MustNotRun(Backup):
        async def resolve(self, url, part=None):
            pytest.fail("a first-P-only fallback must not receive this target")

    with pytest.raises(ResolveError) as exc:
        asyncio.run(Registry([Native("risk_control"), MustNotRun()]).resolve(url, part))
    assert exc.value.code == "risk_control" and exc.value.message == "B 站风控"


def test_bilibili_fallback_accepts_an_explicit_first_p_in_the_url():
    url = "https://www.bilibili.com/video/BV1GY4y1V7P8/?p=1"
    resolver, _ = asyncio.run(Registry([Flaky("risk_control"), Backup()]).resolve(url))
    assert isinstance(resolver, Backup)


def test_saved_sessions_find_their_resolver():
    assert AlcedoResolver().serves("douyin") and AlcedoResolver().serves("youtube")
    assert not AlcedoResolver().serves("bilibili") and not AlcedoResolver().serves("local")


def test_a_missing_duration_is_read_from_the_stream(tmp_path, conf, monkeypatch):
    weibo = {"source": "weibo", "title": "微博视频", "page_url": "https://weibo.com/tv/show/1", "video_url": "https://v/w.mp4"}
    conf.update(ALCEDO_BIN=str(fake_binary(tmp_path, stdout=json.dumps(weibo))))

    async def probe(stream):
        return 61.5 if stream.url == "https://v/w.mp4" else 0.0

    monkeypatch.setattr(alcedo, "probe_duration", probe)
    assert asyncio.run(AlcedoResolver().resolve("https://weibo.com/tv/show/1")).duration == 61.5
