"""Mainland platforms go through CN_PROXY; everything else, B 站 included, stays direct."""
from modules import settings
from modules.frames.grabber import input_args
from modules.video_source import Stream


def test_only_mainland_hosts_use_the_proxy(monkeypatch):
    monkeypatch.setenv("CN_PROXY", "http://sh:43128")
    monkeypatch.delenv("CN_PROXY_HOSTS", raising=False)
    assert settings.mainland_proxy("https://v9-web.douyinvod.com/x.mp4") == "http://sh:43128"
    assert settings.mainland_proxy("https://sns-video-bd.xhscdn.com/a") == "http://sh:43128"
    assert settings.mainland_proxy("https://upos-sz-mirror.bilivideo.com/a.mp4") is None
    assert settings.mainland_proxy("https://evil-douyin.com/a") is None  # a look-alike host
    assert settings.mainland_proxy("/data/source.mp4") is None
    args = input_args(Stream("https://v9-web.douyinvod.com/x.mp4", {"Referer": "https://www.douyin.com/"}, "mp4"))
    assert args[args.index("-http_proxy") + 1] == "http://sh:43128" and args[-1].endswith("x.mp4")
    monkeypatch.delenv("CN_PROXY")
    assert "-http_proxy" not in input_args(Stream("https://v9-web.douyinvod.com/x.mp4", {}, "mp4"))


def test_the_list_can_be_replaced(monkeypatch):
    monkeypatch.setenv("CN_PROXY", "http://sh:43128")
    monkeypatch.setenv("CN_PROXY_HOSTS", "bilivideo.com")
    assert settings.mainland_proxy("https://upos-sz-mirror.bilivideo.com/a.mp4") == "http://sh:43128"
    assert settings.mainland_proxy("https://v9-web.douyinvod.com/x.mp4") is None
