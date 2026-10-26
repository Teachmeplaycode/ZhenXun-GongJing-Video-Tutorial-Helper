"""The actual answer path chooses a bounded summary without weakening detail requests."""
import asyncio
import copy
from types import SimpleNamespace

import pytest

from modules.agent import intent, run
from modules.chapters import Chapter, save
from modules.llm import ToolCall
from modules.screentext import ScreenText
from modules.transcript import Segment, Transcript
from tests.test_agent import make_job


@pytest.fixture
def ready_job(tmp_path, monkeypatch):
    monkeypatch.setenv("INTENT_LLM_FALLBACK", "off")
    monkeypatch.setattr(run.experience, "kinds", lambda: [])
    job = make_job(tmp_path, ["ok"] * 64)
    job.video.duration = 3600
    for i, slot in enumerate(job.slots):
        slot.time = (i + .5) * 3600 / 64
    job.transcript = Transcript("done", segments=[Segment(i * 45, (i + 1) * 45,
        ("开头证据" if i == 0 else "末尾证据" if i == 79 else f"第{i}段") + "课堂内容" * 250) for i in range(80)])
    job.screentext = ScreenText("done")
    return job


class Client:
    config = SimpleNamespace(model="fake")
    def __init__(self):
        self.calls = []
        self.read_ahead = False
    async def stream(self, messages, usage, **kwargs):
        self.calls.append({"messages": copy.deepcopy(messages), **kwargs})
        usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, "stop"
        yield "这"
        self.read_ahead = True
        yield "是课程要点。"


def collect(job, client, question, **kwargs):
    async def go():
        return [event async for event in run.run_agent(job, client, question, **kwargs)]
    return asyncio.run(go())


def material(client):
    return client.calls[0]["messages"][1]["content"]


def images(client):
    return [part for part in material(client) if part["type"] == "image_url"]


def test_summary_skips_model_routing_and_covers_both_ends(ready_job, monkeypatch):
    routes = []
    async def classify(question, decider, **kwargs):
        routes.append(question)
        return intent.Intent("content", None, {}, "test")
    monkeypatch.setattr(intent, "classify", classify)
    client = Client()
    collect(ready_job, client, "总结这个视频的主要内容，分3–5点。")
    assert routes == []
    assert len(images(client)) == 12
    body = "\n".join(part.get("text", "") for part in material(client))
    assert "开头证据" in body and "末尾证据" in body
    assert "F001" in body and "F064" in body
    assert len(body) < 18000
    assert client.calls[0]["max_tokens"] <= 3000


@pytest.mark.parametrize("speech", ["none", "partial"])
def test_visual_summary_uses_sixteen_frames_when_text_is_missing_or_partial(ready_job, speech):
    ready_job.transcript.segments = [] if speech == "none" else [Segment(0, 1200, "仅前面三分之一的语音")]
    client = Client()
    collect(ready_job, client, "概括课程核心要点")
    assert len(images(client)) == 16


@pytest.mark.parametrize("question", ["总结每一页的参数和操作步骤", "联网核实后总结这个视频", "逐帧总结视频内容", "总结完整公式推导", "网上查一下再总结", "查查并总结这个视频", "搜集相关内容再概括", "总结这句话能信吗", "总结第3页"])
def test_detailed_or_research_requests_keep_the_full_path(ready_job, monkeypatch, question):
    routes = []
    async def classify(question, decider, **kwargs):
        routes.append(question)
        return intent.Intent("content", None, {}, "test")
    monkeypatch.setattr(intent, "classify", classify)
    client = Client()
    collect(ready_job, client, question)
    assert routes == [question]
    assert len(images(client)) == 64


def test_explicit_frame_selection_keeps_every_selected_frame(ready_job, monkeypatch):
    routes = []
    async def classify(question, decider, **kwargs):
        routes.append(question)
        return intent.Intent("content", None, {}, "test")
    monkeypatch.setattr(intent, "classify", classify)
    client = Client()
    collect(ready_job, client, "总结这些画面", frames=list(range(64)))
    assert len(images(client)) == 64 and routes


def test_summary_streams_the_first_word_before_reading_the_next(ready_job):
    client = Client()
    async def go():
        gen = run.run_agent(ready_job, client, "总结视频")
        async for event in gen:
            if event["type"] == "assistant.message.delta":
                assert event["delta"] == "这"
                assert client.read_ahead is False
                await gen.aclose()
                return
        pytest.fail("no answer delta")
    asyncio.run(go())


def test_summary_still_can_fetch_more_video_evidence(ready_job):
    class ToolsClient(Client):
        async def stream(self, messages, usage, **kwargs):
            self.calls.append({"messages": copy.deepcopy(messages), **kwargs})
            usage.prompt_tokens, usage.completion_tokens = 100, 10
            if len(self.calls) == 1:
                usage.tool_calls = [ToolCall("find", "search_transcript", {"query": "末尾证据"})]
                usage.finish_reason = "tool_calls"
                return
            usage.finish_reason = "stop"
            yield "末尾介绍了课程总结。"
    client = ToolsClient()
    events = collect(ready_job, client, "总结视频要点")
    assert len(client.calls) == 2
    assert any(event.get("tool_name") == "transcript.search" for event in events)
    assert "末尾证据" in client.calls[1]["messages"][-1]["content"]


def test_cached_chapters_are_only_derived_navigation(ready_job):
    save(ready_job.root, "done", [Chapter(0, 3600, "缓存课程结构", "派生知识摘要")])
    client = Client()
    collect(ready_job, client, "总结课程要点")
    body = str(client.calls[0]["messages"])
    assert "缓存课程结构" in body
    assert "派生" in body and "原始证据" in body


def test_split_tool_markup_is_never_streamed_to_a_summary(ready_job, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOOL_ROUNDS", "0")
    class MarkupClient(Client):
        async def stream(self, messages, usage, **kwargs):
            self.calls.append({"messages": copy.deepcopy(messages), **kwargs})
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, "stop"
            if len(self.calls) == 1:
                for part in ["<", "｜", "｜DS", "ML｜｜ calls>", "secret tool payload"]:
                    yield part
            else:
                yield "课程主要介绍存储器。"
    client = MarkupClient()
    events = collect(ready_job, client, "总结视频")
    answer = "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta")
    assert "DSML" not in answer and "secret" not in answer and "<" not in answer
    assert "课程主要介绍存储器" in answer


def test_explicit_clock_range_still_runs_the_close_look(ready_job, monkeypatch):
    from modules.agent.tools import ToolResult
    requested = []
    async def tool_run(self, name, args):
        requested.append((name, args))
        return ToolResult("区间画面已读取", "1 帧", 1)
    monkeypatch.setattr(run.AgentTools, "run", tool_run)
    client = Client()
    collect(ready_job, client, "01:54 到 02:10 的画面发生了什么？")
    assert requested == [("view_frames", {"start": "01:54", "end": "02:10", "count": 6})]
    assert client.calls


def test_incremental_ocr_is_marked_partial_and_sampled(ready_job):
    from modules.screentext import Caption
    ready_job.screentext.status = "running"
    ready_job.screentext.segments = [Caption(0, 12, "首批画面文字", "middle")]
    client = Client()
    events = collect(ready_job, client, "概括课程内容")
    body = str(client.calls[0]["messages"])
    assert "首批画面文字" in body and "资料仍在补充" in body
    assert "未采样" in body and "每秒识别" not in body
    assert not any(e.get("tool_name") == "data.wait" for e in events)


def test_summary_keeps_the_end_of_a_long_ocr_timeline(ready_job):
    from modules.screentext import Caption
    ready_job.transcript.segments = []
    ready_job.screentext.segments = [Caption(i * 45, (i + 1) * 45,
        ("OCR首段" if i == 0 else "OCR末段" if i == 79 else f"文字{i}") + "画面内容" * 200, "middle") for i in range(80)]
    client = Client()
    collect(ready_job, client, "概括课程内容")
    body = str(material(client))
    assert "OCR首段" in body and "OCR末段" in body
    assert len(body) < 10000
