"""Questions worth asking about this very video, offered before the first question."""
import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from modules import suggest
from modules.frames import FrameJob
from modules.llm import ChatClient, LLMConfig
from modules.screentext.merge import Caption
from modules.screentext.task import ScreenText
from modules.transcript.asr import Segment
from modules.transcript.task import Transcript
from modules.video_source import ResolvedVideo, Stream


def job(tmp_path, speech="done"):
    video = ResolvedVideo("bilibili", "BV1", "u", "【Excel技巧】数据透视表转换成表格形式", 155.0, [Stream("u", {}, "s")])
    j = FrameJob("job1", video, None, tmp_path / "jobs" / "job1", count=4)
    j.transcript = Transcript(speech, "", [Segment(73.0, 76.0, "我们先点击报表布局")])
    j.screentext = ScreenText()
    j.screentext.status = "done"
    j.screentext.segments = [Caption(85.0, 87.0, "以表格形式显示", "middle"), Caption(88.0, 89.0, "以表格形式显示", "middle")]
    return j


def test_the_model_sees_title_speech_and_on_screen_text_once_each(tmp_path):
    text = suggest.context(job(tmp_path))
    assert "标题：【Excel技巧】数据透视表转换成表格形式" in text and "[01:13] 我们先点击报表布局" in text
    assert text.count("以表格形式显示") == 1  # the same caption on consecutive frames is listed once


def test_sampling_keeps_the_whole_video_in_view():
    lines = [f"[{i:02d}:00] 第{i}句" + "字" * 40 for i in range(200)]
    picked = suggest._sample(lines, 1000)
    last = int(picked[-1][1:].split(":")[0])
    assert picked[0] == lines[0] and last > 150 and sum(len(x) for x in picked) <= 1100


def test_questions_are_cleaned():
    raw = 'ok {"questions": [{"question": "数据透视表是在哪一步改成表格形式的？", "kind": "tutorial", "hint": "找到关键操作"},' \
          ' {"question": "数据透视表是在哪一步改成表格形式的？", "kind": "tutorial"},' \
          ' {"question": "' + "很长" * 30 + '", "kind": "content"},' \
          ' {"question": "去掉分类汇总后为什么要再去掉总计？", "kind": "odd"},' \
          ' {"question": "这个视频适合哪个 Excel 版本？", "kind": "content"}, {"question": "第四个", "kind": "content"}]}'
    got = suggest.parse(raw)
    assert [q["question"] for q in got] == ["数据透视表是在哪一步改成表格形式的？", "去掉分类汇总后为什么要再去掉总计？", "这个视频适合哪个 Excel 版本？"]
    assert got[0]["label"] == "教程操作" and got[1]["kind"] == "content"  # an unknown kind becomes content
    assert suggest.parse("not json") == [] and suggest.parse('{"questions": "x"}') == []


def test_the_endpoint_waits_for_the_text_then_writes_once(tmp_path, monkeypatch):
    import app
    j = job(tmp_path, speech="running")
    monkeypatch.setitem(app.jobs, "job1", j)
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        body = '{"questions": [{"question": "数据透视表是在哪一步改成表格形式的？", "kind": "tutorial", "hint": "关键操作"}]}'
        return httpx.Response(200, text=f"data: {json.dumps({'choices': [{'delta': {'content': body}, 'finish_reason': 'stop'}]})}\n\ndata: [DONE]\n\n")
    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))
    monkeypatch.setattr(app.suggest_service, "get_client", lambda: client)
    api = TestClient(app.app)
    assert api.get("/api/link-jobs/job1/suggestions").json() == {"status": "waiting", "questions": []}
    j.transcript.status = "done"
    asyncio.run(app.suggest_service.build(j))  # what the spawned task does
    record = api.get("/api/link-jobs/job1/suggestions").json()
    assert record["status"] == "done" and record["questions"][0]["question"] == "数据透视表是在哪一步改成表格形式的？"
    assert len(calls) == 1 and api.get("/api/link-jobs/job1/suggestions").json() == record  # cached, not asked again
