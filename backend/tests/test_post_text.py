import asyncio
import json

from modules.video_source import alcedo, post_text
from modules.video_source.base import ResolvedVideo


def page(note: dict) -> str:
    state = {"note": {"noteDetailMap": {"abc": {"note": note}}}}
    return f"<script>window.__INITIAL_STATE__={json.dumps(state, ensure_ascii=False).replace('null', 'undefined')}</script>"


NOTE = {"noteId": "abc", "desc": "第一段[笑哭R]\n#催眠麦克风[话题]# 第二段", "ipLocation": "上海", "extra": None,
        "tagList": [{"name": "催眠麦克风"}, {"name": "踯躅森卢笙"}],
        "interactInfo": {"likedCount": "174", "collectedCount": "1.2万", "commentCount": "12", "shareCount": ""}}


def test_the_body_topics_and_counts_are_read_off_the_note_page():
    note = post_text.parse_note(page(NOTE))
    assert note["desc"] == "第一段\n#催眠麦克风 第二段"
    assert note["tags"] == ["催眠麦克风", "踯躅森卢笙"]
    assert note["stats"] == {"likes": 174, "favorites": 12000, "comments": 12}
    assert note["ip"] == "上海"


def test_a_page_without_a_note_gives_nothing():
    assert post_text.parse_note("<html>登录后查看</html>") is None
    assert post_text.parse_note(page({"desc": "no id"})) is None


def test_only_xiaohongshu_pages_are_fetched():
    assert asyncio.run(post_text.fetch("https://www.douyin.com/note/1")) is None
    assert post_text.is_xiaohongshu("https://www.xiaohongshu.com/explore/1")
    assert post_text.is_xiaohongshu("http://xhslink.com/a/b")


def test_an_image_post_gets_its_body(monkeypatch):
    async def fake(url):
        return post_text.parse_note(page(NOTE))
    monkeypatch.setattr(post_text, "fetch", fake)
    v = ResolvedVideo(platform="redbook", video_id="r", canonical_url="https://www.xiaohongshu.com/explore/abc",
                      title="t", duration=1, streams=[], extra={"kind": "images", "images": [{"url": "u"}]})
    asyncio.run(alcedo.add_post_text(v))
    assert v.description.startswith("第一段")
    assert v.public()["tags"] == ["催眠麦克风", "踯躅森卢笙"]
    assert v.public()["stats"]["likes"] == 174
