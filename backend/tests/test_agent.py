import asyncio
import json

import httpx
import pytest

from modules.agent.run import pick_frames, run_agent, spread
from modules.frames import FrameJob
from modules.llm import ChatClient, LLMConfig, LLMError
from modules.llm.client import read_env_file, read_key_file
from modules.video_source import ResolvedVideo, Stream


def make_job(tmp_path, statuses):
    v = ResolvedVideo("test", "v1", "https://x/v1", "标题", 100.0, [Stream("https://a", {}, "s")], description="简介")
    job = FrameJob("j", v, None, tmp_path, count=len(statuses))
    tmp_path.mkdir(exist_ok=True)
    for slot, status in zip(job.slots, statuses):
        slot.status = status
        if status == "ok":
            job.frame_path(slot.index).write_bytes(b"\xff\xd8jpg")
    return job


def sse_body(*chunks):
    lines = [f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks]
    return "".join(lines) + "data: [DONE]\n\n"


def client_for(handler):
    return ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "sk-test"), transport=httpx.MockTransport(handler))


def collect(gen):
    async def go():
        return [e async for e in gen]
    return asyncio.run(go())


def test_spread_keeps_ends_and_order():
    assert spread(list(range(10)), 4) == [0, 3, 6, 9]
    assert spread([1, 2], 5) == [1, 2]


def test_pick_frames_skips_missing_and_caps(tmp_path):
    job = make_job(tmp_path, ["ok", "missing", "ok", "pending", "ok", "ok"])
    chosen, notes = pick_frames(job, None, 3)
    assert [s.index for s in chosen] == [0, 4, 5] and "均匀选取 3 帧" in notes[0]
    chosen, notes = pick_frames(job, [1, 2], 16)
    assert [s.index for s in chosen] == [2] and "1 帧尚未获取" in notes[0]


def test_run_streams_answer_with_images(tmp_path):
    job = make_job(tmp_path, ["ok", "ok", "missing", "ok"])
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "画面"}}]},
            {"choices": [{"delta": {"content": "[00:12] 出现标题"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 900, "completion_tokens": 12}},
        ))

    history = [{"role": "user", "content": "上一个问题"}, {"role": "assistant", "content": "上一个回答"}]
    events = collect(run_agent(job, client_for(handler), "讲了什么", history=history))
    types = [e["type"] for e in events]
    assert types[0] == "progress.update" and types[-1] == "run.completed"
    assert "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta") == "画面[00:12] 出现标题"
    assert "900" in events[-1]["summary"]

    body = seen["body"]
    assert seen["auth"] == "Bearer sk-test" and body["stream"] and body["thinking"] == {"type": "disabled"}
    # system, the video's material (the same for every question: cached), its acknowledgement, the
    # conversation so far, then this question
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user", "assistant", "user"]
    material, asked = body["messages"][1]["content"], body["messages"][-1]["content"]
    images = [c for c in material if c["type"] == "image_url"]
    assert len(images) == 3 and images[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "没有取到画面的时段" in material[0]["text"] and asked[-1]["text"] == "问题：讲了什么"


@pytest.mark.parametrize("status,code", [(401, "unauthorized"), (402, "insufficient_balance"), (503, "upstream")])
def test_http_errors_end_with_run_error(tmp_path, status, code):
    job = make_job(tmp_path, ["ok"])
    events = collect(run_agent(job, client_for(lambda r: httpx.Response(status)), "q"))
    assert events[-1]["type"] == "run.error" and events[-1]["code"] == code
    assert any(e["type"] == "tool_call.output" and e.get("exit_code") == 1 for e in events)


def test_truncated_answer_is_marked(tmp_path):
    job = make_job(tmp_path, ["ok"])
    handler = lambda r: httpx.Response(200, text=sse_body({"choices": [{"delta": {"content": "x"}, "finish_reason": "length"}]}))
    events = collect(run_agent(job, client_for(handler), "q"))
    assert "截断" in events[-2]["delta"] and events[-1]["type"] == "run.completed"


def test_a_cut_off_answer_carries_on_where_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_TOOLS", "off")
    job = make_job(tmp_path, ["ok"])
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(200, text=sse_body({"choices": [{"delta": {"content": "第一页……第二"}, "finish_reason": "length"}]}))
        return httpx.Response(200, text=sse_body({"choices": [{"delta": {"content": "页……完"}, "finish_reason": "stop"}]}))

    events = collect(run_agent(job, client_for(handler), "逐页整理"))
    text = "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta")
    assert text == "第一页……第二页……完" and "截断" not in text
    assert bodies[0]["max_tokens"] == 8192
    assert bodies[1]["messages"][-2] == {"role": "assistant", "content": "第一页……第二"} and "接着写完" in bodies[1]["messages"][-1]["content"]


def test_config_from_env_and_key_file(tmp_path):
    with pytest.raises(LLMError):
        LLMConfig.from_env({})
    key = tmp_path / "key.txt"
    key.write_text("DEEPSEEK_API_KEY='sk-abc'\n")
    assert read_key_file(key) == "sk-abc"
    config = LLMConfig.from_env({"LLM_KEY_FILE": str(key), "LLM_MODEL": "m"})
    assert config.api_key == "sk-abc" and config.model == "m" and "sk-abc" not in repr(config)


def test_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nDEEPSEEK_API_KEY=sk-1\nexport LLM_BASE_URL='https://x/v1?a=b'\n\n")
    assert read_env_file(env) == {"DEEPSEEK_API_KEY": "sk-1", "LLM_BASE_URL": "https://x/v1?a=b"}
    assert read_env_file(tmp_path / "missing") == {}
    key = tmp_path / "bare.txt"
    key.write_text("sk-bare\n")
    assert read_key_file(key) == "sk-bare"


def busy_client(handler):
    return ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "sk-test"),
                      transport=httpx.MockTransport(handler), first_token_timeout=0.3, answer_timeout=0.3)


def test_busy_server_without_response_times_out(tmp_path):
    async def hang(request):
        await asyncio.sleep(5)
        return httpx.Response(200)

    events = collect(run_agent(make_job(tmp_path, ["ok"]), busy_client(hang), "q"))
    assert events[-1]["type"] == "run.error" and events[-1]["code"] == "busy"


def test_keepalive_only_stream_times_out(tmp_path):
    async def keepalive():
        for _ in range(50):
            yield b": keep-alive\n\n"
            await asyncio.sleep(0.05)

    events = collect(run_agent(make_job(tmp_path, ["ok"]), busy_client(lambda r: httpx.Response(200, content=keepalive())), "q"))
    assert events[-1]["type"] == "run.error" and events[-1]["code"] == "busy"


def test_stream_closed_without_content_is_an_error(tmp_path):
    handler = lambda r: httpx.Response(200, text=": keep-alive\n\n")
    events = collect(run_agent(make_job(tmp_path, ["ok"]), client_for(handler), "q"))
    assert events[-1]["type"] == "run.error" and events[-1]["code"] == "empty"


def test_the_video_material_is_the_same_for_every_question_so_it_can_be_cached(tmp_path):
    from modules.agent.run import build_messages
    job = make_job(tmp_path, ["ok", "ok", "ok"])
    first = build_messages(job, job.slots, "第一个问题", [], scope_all=True)
    second = build_messages(job, job.slots, "第二个问题", [{"role": "user", "content": "第一个问题"},
                                                     {"role": "assistant", "content": "回答"}], scope_all=True)
    assert first[:3] == second[:3]  # system, material, acknowledgement: an identical prefix
    assert first[-1]["content"][-1]["text"] == "问题：第一个问题" and second[-1]["content"][-1]["text"] == "问题：第二个问题"
    assert second[3:5] == [{"role": "user", "content": "第一个问题"}, {"role": "assistant", "content": "回答"}]
