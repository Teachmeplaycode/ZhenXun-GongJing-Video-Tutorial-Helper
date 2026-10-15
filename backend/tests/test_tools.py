import asyncio
import json

import httpx

from modules.agent.run import run_agent
from modules.agent.tools import AgentTools, parse_time
from modules.frames import FrameJob, GrabResult
from modules.llm import ChatClient, LLMConfig
from modules.transcript import Segment, Transcript
from modules.video_source import ResolveError, ResolvedVideo, Stream


def video(streams=("https://v",)):
    return ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "标题", 600.0,
                         [Stream(u, {}, f"s{i}") for i, u in enumerate(streams)])


class Resolver:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    async def refresh(self, v):
        self.calls += 1
        if self.fail:
            raise ResolveError("local_file", "已删除")
        return video(("https://fresh",))


def make_job(tmp_path, v=None, resolver=None, statuses=("ok",) * 4):
    job = FrameJob("j", v or video(), resolver or Resolver(), tmp_path / "j", count=len(statuses))
    for slot, status in zip(job.slots, statuses):
        slot.status = status
        if status == "ok":
            job.frame_path(slot.index).write_bytes(b"jpg")
    job.transcript = Transcript("done", "", [Segment(10, 14, "今天聊体重"), Segment(250, 255, "体重保持在120斤以下"),
                                             Segment(400, 404, "我们来化眼妆")])
    return job


def grabber(ok_urls):
    calls = []

    async def grab(stream, t, out):
        calls.append((stream.url, t))
        if stream.url in ok_urls:
            out.write_bytes(b"jpg")
            return GrabResult(True)
        return GrabResult(False, "forbidden")
    grab.calls = calls
    return grab


def test_parse_time():
    assert parse_time(75) == 75 and parse_time("01:15") == 75 and parse_time("1:00:00") == 3600 and parse_time("x") is None


def test_search_and_read_transcript(tmp_path):
    tools = AgentTools(make_job(tmp_path))
    hits = asyncio.run(tools.run("search_transcript", {"query": "体重"}))
    assert hits.text.splitlines() == ["[00:10] 今天聊体重", "[04:10] 体重保持在120斤以下"] and hits.count == 2
    assert "没有找到" in asyncio.run(tools.run("search_transcript", {"query": "直播"})).text
    read = asyncio.run(tools.run("read_transcript", {"start": "04:00", "end": "07:00"}))
    assert read.count == 2 and read.text.startswith("[04:10]")
    assert asyncio.run(tools.run("nope", {})).error


def test_view_frames_grabs_then_refreshes_expired_addresses(tmp_path):
    job = make_job(tmp_path)
    grab = grabber({"https://fresh"})
    result = asyncio.run(AgentTools(job, grab=grab).run("view_frames", {"start": "02:00", "end": "03:00", "count": 3}))
    assert result.count == 3 and [label for label, _ in result.images] == ["画面 · 02:10", "画面 · 02:30", "画面 · 02:50"]
    assert job.resolver.calls == 1 and all(p.is_file() for _, p in result.images)


def test_view_frames_falls_back_to_sampled_frames(tmp_path):
    # An upload whose source was deleted: refresh fails, so the frames already sampled in range are used.
    job = make_job(tmp_path, video(streams=()), Resolver(fail=True))
    result = asyncio.run(AgentTools(job, grab=grabber(set())).run("view_frames", {"start": 0, "end": 200}))
    assert "已有的关键帧" in result.text and [label for label, _ in result.images] == ["画面 · 01:15"]


def sse(*chunks):
    return "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def test_loop_runs_tool_and_answers(tmp_path):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:  # first round: ask for a transcript search, arguments split across chunks
            return httpx.Response(200, text=sse(
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "search_transcript", "arguments": "{\"query\""}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ": \"体重\"}"}}]}, "finish_reason": "tool_calls"}]},
                {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}))
        return httpx.Response(200, text=sse(
            {"choices": [{"delta": {"content": "在 [04:10] 她说体重保持在120斤以下。"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 150, "completion_tokens": 20}}))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))

    async def go():
        return [e async for e in run_agent(make_job(tmp_path), client, "她什么时候提到体重？")]
    events = asyncio.run(go())

    assert "tools" in requests[0] and requests[0]["tools"][0]["function"]["name"] == "search_transcript"
    second = requests[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["function"]["name"] == "search_transcript"
    assert second[-1] == {"role": "tool", "tool_call_id": "c1", "name": "search_transcript",
                          "content": "[00:10] 今天聊体重\n[04:10] 体重保持在120斤以下"}
    names = [e["tool_name"] for e in events if e["type"] == "tool_call.started"]
    assert names == ["frames.select", "transcript.read", "vision.deepseek-flash", "transcript.search", "vision.deepseek-flash"]
    assert "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta") == "在 [04:10] 她说体重保持在120斤以下。"
    assert events[-1]["type"] == "run.completed" and "调用工具 1 次" in events[-1]["summary"] and "输入 250" in events[-1]["summary"]


def test_last_round_has_no_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOOL_ROUNDS", "1")
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, text=sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {
                "name": "view_frames", "arguments": "{\"start\": \"02:00\", \"end\": \"03:00\", \"count\": 2}"}}]}}]}))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "好的"}, "finish_reason": "stop"}]}))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))
    job = make_job(tmp_path)
    import modules.agent.tools as tools_module
    monkeypatch.setattr(tools_module, "grab_frame", grabber({"https://v"}))

    async def go():
        return [e async for e in run_agent(job, client, "q")]
    events = asyncio.run(go())
    assert len(requests) == 2 and "tools" not in requests[1]
    images = [p for p in requests[1]["messages"][-1]["content"] if p["type"] == "image_url"]
    assert len(images) == 2 and events[-1]["type"] == "run.completed"


def test_asked_ranges():
    from modules.agent.run import asked_ranges
    assert asked_ranges("06:10 到 06:40 她在画什么") == [("06:10", "06:40")]
    assert asked_ranges("1:02:03-1:02:30 和 05:30 时") == [("1:02:03", "1:02:30"), ("320.0", "340.0")]
    assert asked_ranges("她提到了 MBTI 吗") == []
