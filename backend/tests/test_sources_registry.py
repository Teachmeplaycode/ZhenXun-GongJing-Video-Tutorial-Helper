import pytest

from modules.video_source import ResolveError, default_registry, extract_url
from modules.video_source.douyin import DouyinResolver
from modules.video_source.youtube import YouTubeResolver


def test_registry_resolves_new_platforms():
    reg = default_registry()
    assert isinstance(reg.find("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), YouTubeResolver)
    assert isinstance(reg.find("https://youtu.be/dQw4w9WgXcQ"), YouTubeResolver)
    assert isinstance(reg.find("https://www.douyin.com/video/7123456789"), DouyinResolver)
    assert isinstance(reg.find("https://v.douyin.com/AbCdEf/"), DouyinResolver)


def test_extract_url_keeps_new_platform_links():
    assert extract_url("【分享】 https://youtu.be/dQw4w9WgXcQ 复制") == "https://youtu.be/dQw4w9WgXcQ"
    assert extract_url("打开抖音看看 https://v.douyin.com/AbCdEf/ 复制此链接") == "https://v.douyin.com/AbCdEf/"


def test_registry_reports_unknown_platform():
    with pytest.raises(ResolveError) as e:
        default_registry().find("https://example.com/v/1")
    assert e.value.code == "unsupported_platform"
    assert "example.com" in e.value.message