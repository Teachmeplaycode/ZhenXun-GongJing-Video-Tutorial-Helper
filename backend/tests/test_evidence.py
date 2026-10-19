"""Typed citations in answers, and the check every one of them passes before an answer is final."""
import asyncio

from modules.agent import evidence
from modules.frames import FrameJob
from modules.screentext.merge import Caption
from modules.screentext.task import ScreenText
from modules.transcript.asr import Segment
from modules.transcript.task import Transcript
from modules.video_source import ResolvedVideo, Stream


def job(tmp_path):
    video = ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "Excel 教程", 155.0, [Stream("u", {}, "s")])
    j = FrameJob("j", video, None, tmp_path / "j", count=8)
    for s in j.slots:
        s.status = "ok"
    j.transcript = Transcript("done", "", [Segment(73.0, 76.0, "我们先点击报表布局")])
    j.screentext = ScreenText()
    j.screentext.segments = [Caption(85.0, 87.0, "以表格形式显示", "middle")]
    return j


ANSWER = ("先点「报表布局」[原声 01:13-01:24] [画面 01:26]，再选「以表格形式显示」[画面文字 01:26]。"
          "官方说明见 [资料 https://support.microsoft.com/pivot]。这样做是为了方便筛选 [推断]。"
          "结尾在 [09:59] 还有一句 [原声 02:10]，另见 [资料 https://invented.example/x] 和 [画面 ]。")


def test_every_kind_of_citation_is_read():
    items = evidence.parse(ANSWER)
    assert [(i["kind"], i["start"], i["end"]) for i in items[:3]] == [("speech", 73, 84), ("frame", 86, 86), ("screentext", 86, 86)]
    assert items[3]["url"] == "https://support.microsoft.com/pivot" and items[4]["kind"] == "inference"
    assert items[5]["kind"] == "moment" and items[5]["start"] == 599
    assert evidence.parse("没有引用的回答") == [] and evidence.parse("比分 [3:2]") == []  # a score, not a time


def test_citations_are_checked_against_the_video_and_the_run(tmp_path):
    j = job(tmp_path)
    looked = []
    items = evidence.check(j, evidence.parse(ANSWER), looked, {"https://support.microsoft.com/pivot"})
    verdict = {i["marker"]: (i["ok"], i["reason"]) for i in items}
    assert verdict["[原声 01:13-01:24]"] == (True, "")
    assert verdict["[画面 01:26]"][0] and verdict["[画面文字 01:26]"][0] and verdict["[推断]"][0]
    assert verdict["[资料 https://support.microsoft.com/pivot]"][0]
    assert verdict["[09:59]"] == (False, "超出视频时长（02:35）")
    assert verdict["[原声 02:10]"] == (False, "这个时间没有识别到说话内容")
    assert verdict["[资料 https://invented.example/x]"] == (False, "这个链接不是本次检索或打开过的资料")
    assert verdict["[画面 ]"] == (False, "没有写明时间点")
    assert evidence.summary(items) == {"counts": {"speech": 2, "frame": 2, "screentext": 1, "source": 2, "inference": 1, "moment": 1},
                                       "failed": 4, "total": 9}


def test_a_picture_citation_needs_a_frame_near_it_or_a_second_look(tmp_path):
    j = job(tmp_path)
    for s in j.slots:
        s.status = "missing" if 100 < s.time < 140 else "ok"
    cited = evidence.parse("[画面 01:58]")
    assert not evidence.check(j, cited, [], set())[0]["ok"]
    assert evidence.check(j, cited, [(117.0, 119.0)], set())[0]["ok"]  # view_frames / replay looked there


def test_the_stream_gets_its_check_just_before_it_completes(tmp_path):
    j = job(tmp_path)

    async def answer():
        yield {"type": "tool_call.started", "call_id": "tool1", "tool_name": "web.search"}
        yield {"type": "tool_call.output", "call_id": "tool1", "stdout": "1. 透视表\n   https://support.microsoft.com/pivot\n"}
        yield {"type": "tool_call.started", "call_id": "tool2", "tool_name": "frames.replay"}
        yield {"type": "tool_call.input", "call_id": "tool2", "input": {"params": {"start": "02:00", "end": "02:05"}}}
        yield {"type": "assistant.message.delta", "delta": "见 [资料 https://support.microsoft.com/pivot]"}
        yield {"type": "assistant.message.delta", "delta": " 和 [画面 02:02]，用户给的 [资料 https://user.example/a]"}
        yield {"type": "run.completed"}

    async def run():
        return [e async for e in evidence.with_evidence(answer(), j, "参考 https://user.example/a")]
    events = asyncio.run(run())
    assert [e["type"] for e in events][-2:] == ["evidence.checked", "run.completed"]
    assert all(i["ok"] for i in events[-2]["items"]) and events[-2]["summary"]["total"] == 3


def test_an_answer_without_citations_adds_no_event(tmp_path):
    async def answer():
        yield {"type": "assistant.message.delta", "delta": "视频里没有讲这个。"}
        yield {"type": "run.completed"}

    async def run():
        return [e["type"] async for e in evidence.with_evidence(answer(), job(tmp_path))]
    assert asyncio.run(run()) == ["assistant.message.delta", "run.completed"]
