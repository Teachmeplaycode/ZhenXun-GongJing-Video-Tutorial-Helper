"""Where viewers got stuck: comments and danmaku labelled against the step cards."""
import asyncio

from fastapi.testclient import TestClient

from modules import steps, stuck
from modules.video_source.base import Comment, CommentPage, Danmaku
from tests.test_replay import job_for

STEPS = [{"n": 1, "time": 10.0, "action": "输入=VLOOKUP(", "detail": "", "frame": 0},
         {"n": 2, "time": 40.0, "action": "按F4绝对引用", "detail": "", "frame": 1}]
PAGES = [CommentPage([Comment("甲", "F4 按了变成调亮度怎么办", likes=30, replies=[Comment("乙", "笔记本要按 Fn+F4", likes=12)]),
                      Comment("丙", "讲得真好")])]
DANMAKU = [Danmaku(41.0, "为什么我的F4不起作用"), Danmaku(5.0, "哈哈哈"), Danmaku(42.0, "为什么我的F4不起作用")]


def test_items_are_numbered_and_only_questions_and_answers_among_danmaku_are_read():
    said = stuck.numbered(stuck.flatten(PAGES) + stuck.pick_danmaku(DANMAKU))
    assert [(x["id"], x["source"]) for x in said] == [("1", "comment"), ("2", "reply"), ("3", "comment"), ("4", "danmaku")]
    assert said[1]["reply_to"] == "1" and said[3]["time"] == 41.0  # the repeat and 哈哈哈 are left out
    assert "#4（弹幕，视频 00:41）：为什么我的F4不起作用" in stuck.messages("t", STEPS, said)[1]["content"]


def test_labels_must_copy_the_start_of_the_item_they_name():
    said = {x["id"]: x for x in stuck.numbered(stuck.flatten(PAGES) + stuck.pick_danmaku(DANMAKU))}
    out = "\n".join(["#1|2|卡住|F4 按了变|F4 变成调亮度",
                     "#2|2|办法|笔记本要按|按 Fn+F4",
                     "#3|2|卡住|为什么我的|编号错位：原话对不上",  # renumbered by the model: dropped
                     "#4|9|卡住|为什么我的|没有第 9 步",
                     "#1|1|办法|F4 按了变|同一条只算一次"])
    got = stuck.parse(out, said, 2)
    assert [(x["id"], x["step"], x["kind"]) for x in got] == [("1", 2, "stuck"), ("2", 2, "fix")]
    groups = stuck.group(got, STEPS)
    assert groups == [{"step": 2, "stuck": 1, "fixes": 1, "items": got}]
    assert stuck.context({"status": "done", "groups": groups})[1].startswith("第 2 步 · 办法：按 Fn+F4（原话：笔记本要按 Fn+F4）")


def test_endpoint_needs_steps_first_then_builds_and_caches(tmp_path, monkeypatch):
    import app

    job = job_for(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)

    class Resolver:
        audience = ("comments", "danmaku")

        async def comments(self, video, sort="hot", cursor=None):
            return PAGES[0]

        async def danmaku(self, video):
            return DANMAKU

    class Model:
        async def stream(self, messages, usage, **kwargs):
            yield "#1|2|卡住|F4 按了变|F4 变成调亮度\n#2|2|办法|笔记本要按|按 Fn+F4"

    job.resolver = Resolver()
    monkeypatch.setattr(app, "get_llm", lambda: Model())
    client = TestClient(app.app)
    assert client.post("/api/link-jobs/job1/step-comments").status_code == 409  # no steps yet
    steps.save(job.root, {"status": "done", "steps": STEPS, "message": ""})
    built = client.post("/api/link-jobs/job1/step-comments").json()
    assert built["status"] == "done" and built["read"] == {"comments": 3, "danmaku": 1}
    assert built["groups"][0]["step"] == 2 and "1 条说卡住了" in built["message"]
    assert client.get("/api/link-jobs/job1/step-comments").json() == built
