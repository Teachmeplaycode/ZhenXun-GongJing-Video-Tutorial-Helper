"""Step cards: one model call over the timed speech and screen text, parsed, each step on its frame."""
import asyncio

from fastapi.testclient import TestClient

from modules import steps
from modules.screentext import ScreenText
from modules.screentext.merge import Caption
from modules.transcript import Transcript
from tests.test_replay import job_for


class Seg:
    def __init__(self, start, text):
        self.start, self.end, self.text = start, start + 2, text


ANSWER = """1. 12|点「数据」选项卡里的「数据验证」|
40.5|把「允许」改成「序列」|来源选 A1:D1
不是步骤的一行
999|超出视频的时间|
"""


def tutorial(tmp_path):
    job = job_for(tmp_path)
    job.transcript = Transcript("done", "", [Seg(10, "先点数据选项卡"), Seg(40, "允许这里选序列")])
    job.screentext = ScreenText("done", "", [Caption(12, 14, "数据验证", "top")])
    for slot, t in zip(job.slots, (0, 45)):
        slot.time, slot.status = t, "ok"
    return job


def test_lines_are_timed_and_a_long_text_is_thinned():
    lines = steps.timed_lines([Seg(65, "说一句")], [Caption(3, 4, "屏上字", "top"), Caption(5, 6, "240", "top")])
    assert lines == ["[00:03 · 3s] 屏：屏上字", "[01:05 · 65s] 说：说一句"]
    many = steps.timed_lines([Seg(i, "字" * 100) for i in range(1000)], [])
    assert sum(len(x) + 1 for x in many) <= steps.MAX_CHARS + 200 and many[0].startswith("[00:00")


def test_parse_keeps_steps_inside_the_video():
    got = steps.parse(ANSWER, 300)
    assert got == [{"time": 12.0, "action": "点「数据」选项卡里的「数据验证」", "detail": ""},
                   {"time": 40.5, "action": "把「允许」改成「序列」", "detail": "来源选 A1:D1"}]
    assert steps.parse("无", 300) == []
    assert [s["time"] for s in steps.parse("04:22|双击精确匹配|\n1:02:03|太晚了|", 400)] == [262.0]  # mm:ss too
    assert steps.parse("1|点单元格|\n2|输入公式|\n3|按回车|", 400) == []  # numbers, not times
    assert [s["time"] for s in steps.parse("18:00|双击安装包|\n136:00|输入命令|", 193)] == [18.0, 136.0]  # seconds written as mm:00


def test_build_numbers_steps_puts_each_on_its_nearest_frame_and_caches(tmp_path):
    job = tutorial(tmp_path)
    seen = []

    async def complete(messages):
        seen.append(messages)
        return ANSWER

    record = asyncio.run(steps.build(job, complete))
    assert record["status"] == "done" and [(s["n"], s["frame"]) for s in record["steps"]] == [(1, 0), (2, 1)]
    assert "[00:12 · 12s] 屏：数据验证" in seen[0][1]["content"]
    assert steps.load(job.root) == record
    none = asyncio.run(steps.build(job, lambda m: asyncio.sleep(0, "无")))
    assert none["status"] == "empty" and "不是教程" in none["message"]


def test_endpoints_build_on_post_and_serve_the_cache(tmp_path, monkeypatch):
    import app

    job = tutorial(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)

    class Model:
        async def stream(self, messages, usage, **kwargs):
            yield ANSWER

    monkeypatch.setattr(app, "get_llm", lambda: Model())
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/steps").json()["status"] == "none"
    built = client.post("/api/link-jobs/job1/steps").json()
    assert built["status"] == "done" and len(built["steps"]) == 2
    assert client.get("/api/link-jobs/job1/steps").json() == built
