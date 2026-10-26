"""Tutorials side by side: rows of the same operation, each cell a real step of that video."""
from fastapi.testclient import TestClient

from modules import compare, steps
from tests.test_replay import job_for

A = [{"n": 1, "time": 0.0, "action": "输入=VLOOKUP(", "frame": 0}, {"n": 2, "time": 122.0, "action": "按F4", "frame": 1}]
B = [{"n": 1, "time": 11.0, "action": "输入公式", "frame": 0}, {"n": 2, "time": 69.0, "action": "跨表框选", "frame": 1}]
VIDEOS = [{"title": "甲", "steps": A}, {"title": "乙", "steps": B}]
ANSWER = """行|操作|甲的步骤号|乙的步骤号|差别
1|输入函数|1|1|甲先点单元格
2|绝对引用|2|-|乙没讲
3|再用一次|2|9|甲第 2 步已用过、乙没有第 9 步
4|跨表|-|2|
总结|先看甲再看乙
甲|基础
乙|进阶"""


def test_the_prompt_has_one_column_per_video():
    system = compare.messages(VIDEOS)[0]["content"]
    assert "行|操作|甲的步骤号|乙的步骤号|差别" in system and "丙" not in system


def test_rows_keep_only_real_unused_steps_and_skip_the_echoed_format_line():
    got = compare.parse(ANSWER, VIDEOS)
    assert [(r["op"], [c and c["n"] for c in r["cells"]]) for r in got["rows"]] == [
        ("输入函数", [1, 1]), ("绝对引用", [2, None]), ("跨表", [None, 2])]
    assert got["rows"][1]["note"] == "乙没讲" and got["rows"][0]["cells"][1]["time"] == 11.0
    assert got["summary"] == "先看甲再看乙" and got["traits"] == ["基础", "进阶"]


def test_endpoint_builds_missing_steps_then_compares_and_caches(tmp_path, monkeypatch):
    import app

    a, b = job_for(tmp_path / "a"), job_for(tmp_path / "b")
    a.id, b.id = "aaaaaaaaaaaa", "bbbbbbbbbbbb"
    from modules.transcript import Transcript
    from tests.test_steps import Seg
    b.transcript = Transcript("done", "", [Seg(75, "先输入公式")])  # something to build b's steps from
    monkeypatch.setitem(app.jobs, a.id, a)
    monkeypatch.setitem(app.jobs, b.id, b)
    monkeypatch.setattr(app, "DATA_ROOT", tmp_path)
    steps.save(a.root, {"status": "done", "steps": A, "message": ""})
    asked = []

    class Model:
        async def stream(self, messages, usage, **kwargs):
            asked.append(messages[0]["content"][:6])
            yield "75|输入公式|\n69|跨表框选|" if messages[0]["content"].startswith("你把视频整理") else ANSWER

    monkeypatch.setattr(app, "get_llm", lambda: Model())
    client = TestClient(app.app)
    assert client.post("/api/compare", json={"ids": [a.id]}).status_code == 422
    built = client.post("/api/compare", json={"ids": [a.id, b.id]}).json()
    assert len(asked) == 2  # b's steps first, then the comparison
    assert built["status"] == "done" and [v["label"] for v in built["videos"]] == ["甲", "乙"]
    assert client.get("/api/compare", params={"ids": f"{b.id},{a.id}"}).json() == built  # either order


def test_a_video_without_steps_is_left_out_while_two_remain(tmp_path, monkeypatch):
    import app

    a, b, c = job_for(tmp_path / "a"), job_for(tmp_path / "b"), job_for(tmp_path / "c")
    a.id, b.id, c.id = "aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"
    for j in (a, b, c):
        monkeypatch.setitem(app.jobs, j.id, j)
    monkeypatch.setattr(app, "DATA_ROOT", tmp_path)
    steps.save(a.root, {"status": "done", "steps": A, "message": ""})
    steps.save(b.root, {"status": "done", "steps": B, "message": ""})
    steps.save(c.root, {"status": "empty", "steps": [], "message": "不是教程"})

    class Model:
        async def stream(self, messages, usage, **kwargs):
            yield ANSWER

    monkeypatch.setattr(app, "get_llm", lambda: Model())
    client = TestClient(app.app)
    built = client.post("/api/compare", json={"ids": [a.id, c.id, b.id]}).json()
    assert [v["id"] for v in built["videos"]] == [a.id, b.id] and built["skipped"] == [c.video.title]
    assert client.get("/api/compare", params={"ids": f"{a.id},{c.id},{b.id}"}).json() == built  # found by what was asked
    steps.save(b.root, {"status": "empty", "steps": [], "message": ""})
    assert client.post("/api/compare", json={"ids": [a.id, b.id, c.id]}).status_code == 422  # one left: nothing to compare


def test_five_videos_get_five_columns():
    five = [{"title": x, "steps": A} for x in "12345"]
    assert "戊的步骤号" in compare.messages(five)[0]["content"]
