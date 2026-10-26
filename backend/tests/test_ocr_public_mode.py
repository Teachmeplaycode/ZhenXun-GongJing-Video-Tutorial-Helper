"""The browser receives only a safe OCR placement choice, never private resolver settings."""
import pytest

from modules.video_source import ResolvedVideo


@pytest.mark.parametrize('mode', ['hybrid', 'local', 'server'])
def test_public_video_exposes_the_selected_ocr_mode_without_private_settings(mode):
    video = ResolvedVideo('bilibili', 'video', 'https://example.test/video', '课件', 120, [],
        extra={'sampling': {'ocr_mode': mode}, 'private_token': 'private', 'cookie': 'private'})
    public = video.public()
    assert public['ocr_mode'] == mode
    assert 'extra' not in public and 'private_token' not in public and 'cookie' not in public


@pytest.mark.parametrize('sampling', [None, {}, {'ocr_mode': 'invalid'}, {'ocr_mode': None}, 'invalid'])
def test_legacy_or_invalid_public_mode_stays_on_the_server(sampling):
    video = ResolvedVideo('local', 'video', 'local://video', '课件', 120, [], extra={'sampling': sampling})
    assert video.public()['ocr_mode'] == 'server'
