"""Question kinds decided before the agent starts, and what each changes."""
import asyncio
import json

import httpx
import pytest

from modules.agent import intent
from modules.agent.run import run_agent
from modules.llm import ChatClient, LLMConfig
from tests.test_tools import make_job, sse

QUESTIONS = [  # (question, kind) — the keyword fallback must get these right
    ("视频里第几秒点了哪个按钮，把数据透视表改成了表格形式？", "tutorial"),
    ("为什么我照着做到这一步就报错了", "tutorial"),
    ("这个视频说得对吗", "science"),
    ("帮我把这个视频的说法都核查一遍", "science"),
    ("85 种药物这个说法可靠吗？帮我上网核实一下", "verify"),
    ("这是不是骗局", "fraud"),
    ("他让加微信领资料，会不会被骗", "fraud"),
    ("视频主要讲了什么", "content"),
]


@pytest.mark.parametrize("question,kind", QUESTIONS)
def test_keywords_decide_without_the_decision_model(question, kind):
    got = asyncio.run(intent.classify(question, None))
    assert (got.kind, got.how, got.p) == (kind, "关键词", None)


class Decider:
    def __init__(self, probs):
        self.probs = probs

    async def choice(self, state, instructions, criteria, *, task=""):
        assert set(criteria) == set(intent.CRITERIA) and task == "intent"
        from modules.decide.client import Decision
        return Decision(self.probs, "fake", 1.0)


def test_the_decision_model_decides_and_an_unsure_decision_changes_nothing():
    sure = asyncio.run(intent.classify("这个说得对吗", Decider({"science": 0.8, "verify": 0.1, "content": 0.1})))
    assert (sure.kind, sure.p, sure.skill, sure.how) == ("science", 0.8, "check_science", "决策模型")
    unsure = asyncio.run(intent.classify("嗯", Decider({"tutorial": 0.4, "content": 0.35, "chat": 0.25})))
    assert unsure.kind == "tutorial" and unsure.skill is None and unsure.note == ""

    class Broken:
        async def choice(self, *a, **k):
            raise RuntimeError("ollama is not running")
    assert asyncio.run(intent.classify("这是不是骗局", Broken())).how == "关键词"


def test_a_tutorial_question_is_answered_step_by_step(tmp_path):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "01:24 点了「报表布局」。"}, "finish_reason": "stop"}]}))
    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))

    async def go():
        return [e async for e in run_agent(make_job(tmp_path), client, "第几秒点了哪个按钮")]
    events = asyncio.run(go())
    route = next(e for e in events if e.get("call_id") == "route" and e["type"] == "tool_call.output")
    assert route["data"]["kind"] == "tutorial" and route["stdout"].startswith("教程操作（关键词")
    assert seen[0]["messages"][-1]["content"].startswith("（回答方式）这是软件或操作教程类问题")


def test_a_fraud_question_runs_the_skill_first_and_the_model_answers_from_it(tmp_path, monkeypatch):
    from modules.agent import skills, tools
    from modules.agent.tools import ToolResult

    async def fake_run(name, job, llm, web=True, papers=True):
        yield {"type": "progress.update", "step": "反诈识别：查话术"}
        yield ("result", "反诈识别完成：综合风险高。", "风险高", 1, {"skill": "antifraud", "report": {"summary": "x"}}, False)
    monkeypatch.setattr(skills, "run", fake_run)
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "风险高 [推断]。"}, "finish_reason": "stop"}]}))
    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))

    async def go():
        return [e async for e in run_agent(make_job(tmp_path), client, "这是不是骗局")]
    events = asyncio.run(go())
    started = [e["tool_name"] for e in events if e["type"] == "tool_call.started"]
    assert "skill.antifraud" in started and "decision.research_intent" not in started
    first = seen[0]["messages"]
    assert first[-2]["tool_calls"][0]["function"]["name"] == "check_fraud" and first[-1]["content"] == "反诈识别完成：综合风险高。"
    assert len(seen) == 1  # answered from the skill, no further rounds forced
