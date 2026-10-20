"""Authoritative run usage includes routing exactly once, including failed route attempts."""
import asyncio

import pytest

from modules.agent import intent
from modules.agent.run import run_agent
from modules.llm import LLMError
from tests.test_tools import make_job


@pytest.mark.parametrize("how", ["主模型回退", "关键词"])
def test_route_and_continuation_are_counted_once(tmp_path, monkeypatch, how):
    monkeypatch.setenv("LLM_TOOLS", "off")
    calls = []

    async def route(*args):
        calls.append(1)
        return intent.Intent("content", None, {}, how, usage={"prompt_tokens": 11, "completion_tokens": 2})

    class Client:
        def __init__(self):
            self.calls = 0
            self.config = type("Config", (), {"model": "test"})()

        async def stream(self, messages, usage, **kwargs):
            self.calls += 1
            usage.prompt_tokens, usage.completion_tokens = 100, 10
            usage.finish_reason = "length" if self.calls == 1 else "stop"
            yield "answer"

    monkeypatch.setattr(intent, "classify", route)

    async def go():
        return [event async for event in run_agent(make_job(tmp_path), Client(), "question")]

    final = asyncio.run(go())[-1]
    assert calls == [1] and final["type"] == "run.completed"
    assert final["usage"] == {"prompt": 211, "completion": 22, "known_prompt": 211, "known_completion": 22, "complete": True}


def test_partial_route_usage_preserves_unknown_in_authoritative_total(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_TOOLS", "off")

    async def route(*args):
        return intent.Intent("content", None, {}, "关键词", usage={"prompt_tokens": 7, "completion_tokens": None})

    class Client:
        config = type("Config", (), {"model": "test"})()

        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, "stop"
            yield "answer"

    monkeypatch.setattr(intent, "classify", route)

    async def go():
        return [event async for event in run_agent(make_job(tmp_path), Client(), "question")]

    final = asyncio.run(go())[-1]
    assert final["usage"] == {"prompt": 107, "completion": None, "known_prompt": 107, "known_completion": 10, "complete": False}
    assert "未知" in final["summary"]


def test_answer_error_keeps_route_and_partial_answer_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_TOOLS", "off")

    async def route(*args):
        return intent.Intent("content", None, {}, "主模型回退", usage={"prompt_tokens": 11, "completion_tokens": 2})

    class Client:
        config = type("Config", (), {"model": "test"})()

        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens = 100
            raise LLMError("network", "offline")
            yield "unreachable"

    monkeypatch.setattr(intent, "classify", route)

    async def go():
        return [event async for event in run_agent(make_job(tmp_path), Client(), "question")]

    final = asyncio.run(go())[-1]
    assert final["type"] == "run.error"
    assert final["usage"] == {"prompt": 111, "completion": None, "known_prompt": 111, "known_completion": 2, "complete": False}
