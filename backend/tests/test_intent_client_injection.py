"""Injected per-answer metering survives route failures/cancellation without client ownership."""
import asyncio

import pytest

from modules.agent import intent


class MeteringSpy:
    def __init__(self, mode):
        self.mode = mode
        self.closed = False
        self.records = []
        self.entered = asyncio.Event()
        self.finished = asyncio.Event()
        self.active_usage = None

    async def aclose(self):
        self.closed = True

    async def stream(self, messages, usage, **kwargs):
        self.active_usage = usage
        usage.prompt_tokens, usage.completion_tokens = 11, 2
        self.entered.set()
        try:
            if self.mode == "error":
                raise RuntimeError("provider unavailable")
            if self.mode in {"timeout", "cancel"}:
                await asyncio.sleep(10)
            yield "content" if self.mode == "normal" else "not-a-label"
        finally:
            self.records.append({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
            self.active_usage = None
            self.finished.set()


@pytest.fixture(autouse=True)
def injected_client_only(monkeypatch):
    monkeypatch.setattr("modules.settings.settings", lambda: {"INTENT_LLM_FALLBACK_TIMEOUT": "0.02"})

    def forbidden(*args, **kwargs):
        raise AssertionError("injected client must not create a private model client/config")

    monkeypatch.setattr("modules.llm.create_client", forbidden)
    monkeypatch.setattr("modules.llm.client.LLMConfig.from_env", forbidden)


@pytest.mark.parametrize("mode", ["normal", "invalid", "error", "timeout"])
def test_injected_metering_records_every_route_attempt_without_private_client_or_close(mode):
    async def go():
        client = MeteringSpy(mode)
        got = await intent.classify("视频讲什么", client=client)
        await asyncio.wait_for(client.finished.wait(), 0.25)
        assert got.how == ("主模型回退" if mode == "normal" else "关键词")
        assert got.usage == {"prompt_tokens": 11, "completion_tokens": 2}
        assert client.records == [got.usage] and not client.closed
    asyncio.run(go())


def test_cancelled_route_leaves_partial_usage_visible_to_the_shared_meter():
    async def go():
        client = MeteringSpy("cancel")
        task = asyncio.create_task(intent.classify("视频讲什么", client=client))
        await client.entered.wait()
        # A real budget proxy can snapshot the same live Usage before cancelling open calls.
        assert client.active_usage.prompt_tokens == 11
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(client.finished.wait(), 0.25)
        assert client.records == [{"prompt_tokens": 11, "completion_tokens": 2}]
        assert not client.closed
    asyncio.run(go())
