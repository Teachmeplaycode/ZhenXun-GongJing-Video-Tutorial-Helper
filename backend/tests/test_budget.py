"""modules/agent/budget.py and its run.py / app.py integration (issue #30): budget gates,
per-call cost and wait metering. Unknown usage or price must never become ¥0."""
import asyncio
import importlib
import json
import time
import types

import httpx
import pytest
from fastapi.testclient import TestClient

from modules.agent import intent as intent_mod
from modules.agent.budget import AnswerBudget, limits, prices, side_tokens
from modules.agent.run import run_agent
from modules.agent.web import SearchResult
from modules.frames import FrameJob
from modules.llm import ChatClient, LLMConfig
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


def sse_tool_call(name, arguments="{}"):
    return {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": f"call_{name}", "function": {"name": name, "arguments": arguments}}]}}]}


def client_for(handler):
    return ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "sk-test"),
                      transport=httpx.MockTransport(handler))


def collect(gen):
    async def go():
        return [e async for e in gen]
    return asyncio.run(go())


NO_LIMITS = {"external": None, "tool_calls": None, "frames": None, "seconds": None, "tokens": None}


# ---- the budget module on its own ------------------------------------------------------------
def test_limits_default_unlimited_and_env_override(monkeypatch):
    for var in ("LLM_BUDGET_MAX_EXTERNAL", "LLM_BUDGET_MAX_TOOL_CALLS", "LLM_BUDGET_MAX_FRAMES",
                "LLM_BUDGET_MAX_SECONDS", "LLM_BUDGET_MAX_TOKENS"):
        monkeypatch.delenv(var, raising=False)
    assert limits() == NO_LIMITS
    monkeypatch.setenv("LLM_BUDGET_MAX_EXTERNAL", "3")
    monkeypatch.setenv("LLM_BUDGET_MAX_SECONDS", "0.5")
    monkeypatch.setenv("LLM_BUDGET_MAX_FRAMES", "abc")       # unparsable → unlimited
    monkeypatch.setenv("LLM_BUDGET_MAX_TOOL_CALLS", "-2")    # negative → unlimited
    assert limits() == {"external": 3.0, "tool_calls": None, "frames": None, "seconds": 0.5, "tokens": None}


def test_prices_unset_means_no_estimate(monkeypatch):
    monkeypatch.delenv("LLM_PRICE_IN_M", raising=False)
    monkeypatch.delenv("LLM_PRICE_OUT_M", raising=False)
    assert prices() == (None, None)
    monkeypatch.setenv("LLM_PRICE_IN_M", "2")
    monkeypatch.setenv("LLM_PRICE_OUT_M", "8")
    assert prices() == (2.0, 8.0)


def test_check_tool_refuses_at_each_cap():
    b = AnswerBudget(caps={**NO_LIMITS, "external": 1})
    assert b.check_tool("web_search") is None
    b.tool_done("web_search")
    assert b.check_tool("web_search") == "external" and b.check_tool("fetch_page") == "external"
    assert b.check_tool("search_papers") == "external" and b.check_tool("browse") == "external"
    assert b.check_tool("view_frames") is None and b.limit_hits == ["external"]
    assert "外部访问次数已达到上限" in b.deny_text("external")


def test_frames_and_call_caps_are_soft():
    b = AnswerBudget(caps={**NO_LIMITS, "tool_calls": 3, "frames": 4})
    b.tool_done("view_frames", 3)
    assert b.frames_read == 3 and b.tool_calls == 1
    assert b.check_tool("view_frames") is None            # 3 < 4: still room
    b.tool_done("replay", 2)                              # started under the cap, ended at 5
    assert b.frames_read == 5 and b.check_tool("view_frames") == "frames"
    b.tool_done("search_transcript", 1)                   # third call, cap was 3... reached now
    assert b.check_tool("search_transcript") == "tool_calls"
    assert b.limit_hits == ["frames", "tool_calls"]


def test_gate_round_on_seconds_and_tokens():
    by_seconds = AnswerBudget(caps={**NO_LIMITS, "seconds": 0.0})
    assert by_seconds.gate_round() == "seconds"
    by_tokens = AnswerBudget(caps={**NO_LIMITS, "tokens": 100})
    by_tokens.llm_finished(80, 30)
    assert by_tokens.gate_round() == "tokens"
    unknown = AnswerBudget(caps={**NO_LIMITS, "tokens": 100})
    unknown.llm_finished(None, None)                      # usage unknown: the gate cannot know
    assert unknown.gate_round() is None


def test_costs_need_price_and_known_usage(monkeypatch):
    monkeypatch.delenv("LLM_PRICE_IN_M", raising=False)
    monkeypatch.delenv("LLM_PRICE_OUT_M", raising=False)
    b = AnswerBudget()
    b.llm_finished(1000, 100)
    cost = b.cost()
    assert cost["cny"] is None and not cost["computable"] and "单价" in cost["reason"]
    monkeypatch.setenv("LLM_PRICE_IN_M", "2")
    monkeypatch.setenv("LLM_PRICE_OUT_M", "8")
    assert b.cost() == {"cny": 0.0028, "computable": True, "reason": None}
    assert b.cost_text() == "约￥0.0028"
    broken = AnswerBudget()
    broken.llm_finished(None, None)                       # a stream that reported no usage
    assert broken.cost()["cny"] is None and "未知" in broken.cost()["reason"]


def test_llm_metering_wait_failures_and_tokens():
    b = AnswerBudget()
    b.llm_started()
    time.sleep(0.005)
    b.llm_first_word()
    b.llm_finished(10, 2)
    b.llm_started()                                       # no word at all: whole call is the wait
    time.sleep(0.005)
    b.llm_finished(20, 3)
    assert b.llm_calls == 2 and b.prompt_tokens == 30 and b.completion_tokens == 5
    assert b.max_wait_ms is not None and b.max_wait_ms >= 5
    b.llm_started()
    b.llm_failed()                                        # a broken stream: usage unknowable
    assert b.llm_failures == 1 and not b.tokens_known and b.cost()["cny"] is None


def test_side_tokens_shapes():
    assert side_tokens(None) == (None, None) and side_tokens("junk") == (None, None)
    assert side_tokens({"prompt": 5, "completion": 1}) == (5, 1)
    assert side_tokens({"prompt_tokens": 7, "completion_tokens": 2}) == (7, 2)
    assert side_tokens(types.SimpleNamespace(prompt_tokens=9, completion_tokens=4)) == (9, 4)
    assert side_tokens({"prompt": 5}) == (5, None)         # half known → the cost is unknowable


def test_add_side_counts_intent_fallback_and_tolerates_absence():
    b = AnswerBudget()
    b.add_side(types.SimpleNamespace(prompt_tokens=50, completion_tokens=5), 123)
    assert b.prompt_tokens == 50 and b.completion_tokens == 5 and b.max_wait_ms == 123
    b.add_side(None, None)                                # today's intent.py: no metadata, no crash
    assert b.prompt_tokens == 50 and b.completion_tokens == 5
    b.add_side({"prompt": 10}, 50)                        # half a usage: marked unknown, not added
    assert b.prompt_tokens == 50 and not b.tokens_known


# ---- run_agent integration --------------------------------------------------------------------
def no_prices(monkeypatch):
    monkeypatch.delenv("LLM_PRICE_IN_M", raising=False)
    monkeypatch.delenv("LLM_PRICE_OUT_M", raising=False)


def test_run_completed_carries_budget_and_unknown_cost(tmp_path, monkeypatch):
    no_prices(monkeypatch)
    job = make_job(tmp_path, ["ok", "ok"])
    handler = lambda r: httpx.Response(200, text=sse_body(
        {"choices": [{"delta": {"content": "答"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 500, "completion_tokens": 20}}))
    events = collect(run_agent(job, client_for(handler), "讲了什么"))
    done = events[-1]
    assert done["type"] == "run.completed"
    assert done["budget"]["llm_calls"] == 1 and done["budget"]["prompt_tokens"] == 500
    assert done["budget"]["completion_tokens"] == 20 and done["budget"]["tokens_known"]
    assert done["budget"]["max_wait_ms"] is not None and done["budget"]["external_calls"] == 0
    assert done["cost"] == done["budget"]["cost"] and done["cost"]["cny"] is None
    assert not done["cost"]["computable"] and "单价" in done["cost"]["reason"]


def test_cost_computed_when_priced(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PRICE_IN_M", "2")
    monkeypatch.setenv("LLM_PRICE_OUT_M", "8")
    job = make_job(tmp_path, ["ok"])
    handler = lambda r: httpx.Response(200, text=sse_body(
        {"choices": [{"delta": {"content": "答"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 100}}))
    done = collect(run_agent(job, client_for(handler), "讲了什么"))[-1]
    assert done["cost"]["computable"] and done["cost"]["cny"] == pytest.approx(0.0028)


def test_external_budget_refuses_and_the_model_still_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_MAX_EXTERNAL", "1")

    async def fake_search(query, limit=6, freshness="", *, client=None):
        return [SearchResult("官方说明", "https://x.example/a", "摘要", 3, "example", "2026-01-01")]

    monkeypatch.setattr("modules.agent.web.search", fake_search)
    job = make_job(tmp_path, ["ok", "ok"])
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(200, text=sse_body(
                sse_tool_call("web_search", '{"query": "柚子 药物"}'),
                {"choices": [], "usage": {"prompt_tokens": 400, "completion_tokens": 10}}))
        if len(bodies) == 2:  # asks to search again: over the cap, refused, told why
            return httpx.Response(200, text=sse_body(
                sse_tool_call("web_search", '{"query": "再查一次"}'),
                {"choices": [], "usage": {"prompt_tokens": 500, "completion_tokens": 10}}))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "根据已有资料回答。"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 600, "completion_tokens": 30}}))

    events = collect(run_agent(job, client_for(handler), "查一下柚子和药物", web=True))
    denied = [e for e in events if e["type"] == "tool_call.output" and e.get("exit_code") == 3]
    assert len(denied) == 1 and "外部访问次数已达到上限" in denied[0]["stdout"]
    assert denied[0]["data"]["budget"] == "external"
    done = events[-1]
    assert done["type"] == "run.completed"
    assert "根据已有资料回答。" in "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta")
    assert done["budget"]["external_calls"] == 1 and done["budget"]["tool_calls"] == 1
    assert done["budget"]["blocked_calls"] == 1 and done["budget"]["limit_hits"] == ["external"]


def test_frames_budget_refuses_view_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_MAX_FRAMES", "0")
    job = make_job(tmp_path, ["ok", "ok"])
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(200, text=sse_body(
                sse_tool_call("view_frames", '{"start": "0", "end": "20", "count": 4}'),
                {"choices": [], "usage": {"prompt_tokens": 300, "completion_tokens": 8}}))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "用已有的关键帧回答。"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 400, "completion_tokens": 12}}))

    events = collect(run_agent(job, client_for(handler), "画面里的细节是什么"))
    denied = [e for e in events if e["type"] == "tool_call.output" and e.get("exit_code") == 3]
    assert len(denied) == 1 and denied[0]["data"]["budget"] == "frames"
    done = events[-1]
    assert done["budget"]["frames_read"] == 0 and done["budget"]["limit_hits"] == ["frames"]


def test_two_tool_calls_in_one_round_both_count(tmp_path, monkeypatch):
    job = make_job(tmp_path, ["ok", "ok", "ok", "ok"])

    async def fail_grab(stream, t, out):
        return types.SimpleNamespace(ok=False, kind="error")

    monkeypatch.setattr("modules.agent.tools.grab_frame", fail_grab)  # falls back to keyframes
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx.Response(200, text=sse_body(
                {"choices": [{"delta": {"tool_calls": [
                    {"index": 0, "id": "c1", "function": {"name": "view_frames", "arguments": '{"start": "0", "end": "20"}'}},
                    {"index": 1, "id": "c2", "function": {"name": "view_frames", "arguments": '{"start": "30", "end": "50"}'}}]}}]},
                {"choices": [], "usage": {"prompt_tokens": 700, "completion_tokens": 10}}))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "两段都看了。"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 900, "completion_tokens": 15}}))

    events = collect(run_agent(job, client_for(handler), "画面里有什么"))
    done = events[-1]
    assert done["budget"]["tool_calls"] == 2            # both calls of the round, concurrent or not
    assert done["budget"]["frames_read"] == 2           # one nearby keyframe per view_frames fallback


def test_token_budget_forces_a_toolless_round(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_MAX_TOKENS", "500")
    job = make_job(tmp_path, ["ok"])
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:  # asks for a tool with the budget already spent
            return httpx.Response(200, text=sse_body(
                sse_tool_call("web_search", '{"query": "x"}'),
                {"choices": [], "usage": {"prompt_tokens": 600, "completion_tokens": 10}}))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "直接回答。"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 700, "completion_tokens": 20}}))

    events = collect(run_agent(job, client_for(handler), "查一下 x"))
    assert any(e["type"] == "progress.update" and "预算已用完" in e["step"] for e in events)
    assert "tools" not in bodies[1]                     # the gated round asks for no tools
    denied = [e for e in events if e["type"] == "tool_call.output" and e.get("exit_code") == 3]
    assert denied and denied[0]["data"]["budget"] == "tokens"
    done = events[-1]
    assert done["budget"]["limit_hits"] == ["tokens"] and done["budget"]["blocked_calls"] == 1


def test_seconds_budget_forces_a_direct_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_MAX_SECONDS", "0")
    job = make_job(tmp_path, ["ok"])
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "立刻回答。"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 200, "completion_tokens": 10}}))

    events = collect(run_agent(job, client_for(handler), "讲了什么"))
    assert "tools" not in bodies[0]
    assert events[-1]["budget"]["limit_hits"] == ["seconds"]


def test_intent_fallback_usage_counted_via_getattr(tmp_path, monkeypatch):
    no_prices(monkeypatch)
    monkeypatch.setenv("LLM_PRICE_IN_M", "2")
    monkeypatch.setenv("LLM_PRICE_OUT_M", "8")

    async def fake_classify(question, decider=None):
        route = intent_mod.by_keywords(question)        # a plain Intent...
        route.usage = {"prompt": 60, "completion": 6}   # ...plus module A's metadata
        route.elapsed_ms = 234
        return route

    monkeypatch.setattr("modules.agent.run.intent.classify", fake_classify)
    job = make_job(tmp_path, ["ok"])
    handler = lambda r: httpx.Response(200, text=sse_body(
        {"choices": [{"delta": {"content": "答"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 400, "completion_tokens": 20}}))
    done = collect(run_agent(job, client_for(handler), "讲了什么"))[-1]
    assert done["budget"]["prompt_tokens"] == 460 and done["budget"]["completion_tokens"] == 26
    assert done["budget"]["max_wait_ms"] >= 234
    assert done["cost"]["computable"] and done["cost"]["cny"] == pytest.approx((460 * 2 + 26 * 8) / 1e6)


# ---- the answer log line (app.py) -------------------------------------------------------------
def load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("GONGJING_DATA_DIR", str(tmp_path))  # never touch backend/data
    import app as app_module
    return importlib.reload(app_module)


def test_answer_log_carries_cost_and_budget_fields(tmp_path, monkeypatch):
    no_prices(monkeypatch)
    app_module = load_app(tmp_path, monkeypatch)
    job = make_job(tmp_path / "jobs" / "j1", ["ok", "ok"])
    app_module.jobs["j1"] = job
    app_module.store.create(job, "测试会话")
    handler = lambda r: httpx.Response(200, text=sse_body(
        {"choices": [{"delta": {"content": "答"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 500, "completion_tokens": 20}}))
    monkeypatch.setattr(app_module, "get_llm", lambda: client_for(handler))

    with TestClient(app_module.app) as client:
        body = "".join(part for part in client.post(
            "/api/agent/runs", json={"video_id": "j1", "question": "讲了什么", "history": False,
                                     "web": False, "papers": False, "scope": {"type": "all"}}).iter_lines())
    assert '"run.completed"' in body and '"cost"' in body

    lines = (tmp_path / "logs").glob("*.jsonl")
    records = [json.loads(line) for line in open(next(lines), encoding="utf-8")]
    answer = next(r for r in records if r["event"] == "answer")
    assert answer["status"] == "done" and answer["prompt_tokens"] == 500
    assert answer["cost_cny"] is None and answer["cost_computable"] is False
    assert "单价" in answer["cost_reason"]
    assert answer["max_wait_ms"] is not None and answer["external_calls"] == 0
    assert answer["frames_read"] == 0 and answer["tool_calls"] == 0
    assert answer["budget_limit_hits"] is None
