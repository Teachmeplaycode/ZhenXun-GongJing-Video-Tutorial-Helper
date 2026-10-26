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
    # a 100 s tutorial's seconds written twice (EX01, 2026-10-26): all were dropped as past the end
    assert [s["time"] for s in steps.parse("09:10|点「插入数据透视表」|\n21:21|点「现有工作表」|\n34:34|点「确定」|", 100)] == [9.0, 21.0, 34.0]
    assert [s["time"] for s in steps.parse("00:09|点「插入」|\n01:21|点「确定」|", 100)] == [9.0, 81.0]  # real mm:ss stay


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
    assert none["status"] == "empty" and "读不出" in none["message"]


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


def test_parse_reads_the_shapes_models_wrap_lines_in():
    out = "\n".join(["**00:56|调整网格分段|按需要**", "- 第2步：01:12｜使用点实例节点｜", "[01:36] | 新建矢量运算节点 | 使用位置",
                     "【1:55】输出线性衰减属性", "02:05 - 复制点大小节点", "步骤6：02:13|调整点乘的轴|"])
    got = steps.parse(out, 600)
    assert [(s["time"], s["action"]) for s in got] == [
        (56.0, "调整网格分段"), (72.0, "使用点实例节点"), (96.0, "新建矢量运算节点"),
        (115.0, "输出线性衰减属性"), (125.0, "复制点大小节点"), (133.0, "调整点乘的轴")]


def test_steps_have_no_cap_and_a_long_action_stays_whole():
    assert "最多" not in steps.messages("t", ["[00:01 · 1s] 说：x"], 693)[0]["content"]
    many = "\n".join(f"{i}|第{i}步|" for i in range(10, 700, 7))
    assert len(steps.parse(many, 693)) == 98  # every one inside the video, none cut
    long = "点「Download for Windows」下载 Docker Desktop 安装程序"
    assert steps.parse(f"00:05|{long}|", 60)[0]["action"] == long  # once cut at 30: 「Download for Wind」


def test_each_step_gets_its_own_sharper_picture_when_one_can_be_read(tmp_path):
    import asyncio
    cards = [{"n": 1, "time": 5.0}, {"n": 2, "time": 9.0}]
    asked = []

    async def sharp(t, out, width):
        asked.append((t, width))
        if t > 8:
            return False  # this one can't be read: the keyframe stays
        out.write_bytes(b"jpg")
        return True

    asyncio.run(steps.take_shots(tmp_path, cards, sharp))
    assert [c["shot"] for c in cards] == [True, False] and sorted(asked) == [(5.0, 1600), (9.0, 1600)]
    assert steps.shot_path(tmp_path, 1).read_bytes() == b"jpg"


def test_steps_that_stop_half_way_are_followed_to_the_end(tmp_path):
    # a 3 min Blender tutorial (2026-10-26): all 30 steps spent by 01:30, the second half had none
    job = tutorial(tmp_path)
    job.video.duration = 180
    job.transcript = Transcript("done", "", [Seg(t, f"第{t}秒的操作") for t in range(5, 180, 5)])
    seen = []

    async def complete(messages):
        seen.append(messages)
        return "\n".join(f"{t}|前半段 {t}|" for t in range(3, 91, 3)) if len(seen) == 1 else "01:20|太早了|\n02:00|后半段|\n02:50|收尾|"

    record = asyncio.run(steps.build(job, complete))
    assert "视频全长 03:00" in seen[0][0]["content"] and len(seen) == 2
    assert "[01:30" not in seen[1][1]["content"] and "[01:35 · 95s]" in seen[1][1]["content"]
    assert "前面已整理到 01:30" in seen[1][0]["content"]
    assert [s["time"] for s in record["steps"][-2:]] == [120.0, 170.0] and record["steps"][-1]["n"] == 32

    seen.clear()
    asyncio.run(steps.build(job, lambda m: seen.append(m) or asyncio.sleep(0, "30|开头|\n160|快结束|")))
    assert len(seen) == 1  # reaching the end needs no second call


def test_any_video_gets_steps_and_says_which_kind():
    assert steps.kind_of("类型|内容\n00:05|介绍两款耳机|") == "content"
    assert steps.kind_of("**类型：操作**\n00:05|点开设置|") == "operation"
    assert steps.kind_of("00:05|点开设置|") == "operation"  # an old-style reply is a tutorial's
    assert [s["action"] for s in steps.parse("类型|内容\n00:05|介绍两款耳机|\n01:10|对比降噪|", 120)] == ["介绍两款耳机", "对比降噪"]
    assert "已定为「内容」" in steps.messages("t", ["[00:01 · 1s] 说：x"], 120, 60, "content")[0]["content"]


def test_a_talk_is_kept_as_content_steps(tmp_path):
    job = tutorial(tmp_path)
    record = asyncio.run(steps.build(job, lambda m: asyncio.sleep(0, "类型|内容\n00:12|讲数据验证的用处|\n00:40|讲序列来源|")))
    assert record["status"] == "done" and record["kind"] == "content" and len(record["steps"]) == 2
