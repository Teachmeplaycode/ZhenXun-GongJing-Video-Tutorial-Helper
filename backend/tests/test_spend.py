"""The public site's daily spend: priced model calls and transcriptions, a cap, owners exempt."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from modules import spend
from modules.llm.client import ChatClient, LLMConfig, Usage
from tests.test_visitors import api  # noqa: F401 (the public-demo fixture)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    monkeypatch.setattr(spend, "_path", lambda: tmp_path / "spend.sqlite3")
    for name in ("LLM_PRICE", "ASR_PRICE_PER_HOUR", "DAILY_BUDGET_YUAN"):
        monkeypatch.delenv(name, raising=False)


def test_calls_are_priced_by_their_tokens_and_seconds(ledger):
    spend.llm(1_000_000, 500_000, 100_000)  # 0.5M new in × 2 + 0.5M cached × 0.5 + 0.1M out × 8
    spend.asr(3600)  # an hour of audio
    day = spend.total()
    assert day["kinds"]["llm"]["yuan"] == pytest.approx(2.05)
    assert day["kinds"]["asr"]["yuan"] == pytest.approx(0.288)
    assert day["yuan"] == pytest.approx(2.338)


def test_prices_and_the_cap_can_be_set(ledger, monkeypatch):
    monkeypatch.setenv("LLM_PRICE", "1,0,2")
    monkeypatch.setenv("DAILY_BUDGET_YUAN", "0.5")
    spend.llm(200_000, 0, 100_000)  # 0.2 + 0.2
    spend.check()  # 0.4 < 0.5
    spend.llm(100_000, 0, 0)
    with pytest.raises(Exception) as e:
        spend.check()
    assert e.value.status_code == 429 and e.value.detail["code"] == "budget_exceeded"
    monkeypatch.setenv("DAILY_BUDGET_YUAN", "0")  # 0: no cap
    spend.check()


def test_the_desktop_app_keeps_no_ledger(tmp_path, monkeypatch):
    monkeypatch.delenv("PUBLIC_DEMO", raising=False)
    monkeypatch.setattr(spend, "_path", lambda: tmp_path / "spend.sqlite3")
    spend.llm(10_000_000, 0, 10_000_000)
    spend.check()
    assert not (tmp_path / "spend.sqlite3").exists()


def test_a_streamed_answer_is_priced_from_its_reported_usage(ledger):
    def handler(request):
        body = "\n".join([
            "data: " + json.dumps({"choices": [{"delta": {"content": "好"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}],
                                   "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0, "prompt_cache_hit_tokens": 0}}),
            "data: [DONE]", ""])
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "sk-test"), transport=httpx.MockTransport(handler))

    async def go():
        async for _ in client.stream([{"role": "user", "content": "hi"}], Usage()):
            pass
        await client.aclose()

    asyncio.run(go())
    assert spend.total()["kinds"]["llm"]["yuan"] == pytest.approx(2.0)


def test_over_budget_new_questions_and_imports_stop_except_for_owners(api, ledger, monkeypatch):  # noqa: F811
    app, _ = api
    monkeypatch.setenv("DAILY_BUDGET_YUAN", "1")
    monkeypatch.setenv("OWNER_ACCOUNTS", "linyi")
    spend.record("llm", 1.2)

    class Bili:
        platform = "bilibili"
    monkeypatch.setattr(app.registry, "find", lambda url: Bili())
    judge = TestClient(app.app)
    judge.post("/api/auth/register", json={"name": "评委", "password": "secret1"})
    r = judge.post("/api/link-jobs", json={"url": "https://www.bilibili.com/video/BV1"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "budget_exceeded"
    assert "今日额度已满" in r.json()["detail"]["message"]
    assert "spend" not in judge.get("/api/health").json()["user"]  # only owners see the site's spend

    owner = TestClient(app.app)
    owner.post("/api/auth/register", json={"name": "linyi", "password": "secret1"})
    me = owner.get("/api/health").json()["user"]
    assert me["spend"]["yuan"] == pytest.approx(1.2) and me["spend"]["limit"] == 1

    class Bili:
        platform = "bilibili"

    async def no_network(url, part=None):
        raise app.ResolveError("network", "测试里不联网")
    monkeypatch.setattr(app.registry, "find", lambda url: Bili())
    monkeypatch.setattr(app.registry, "resolve", no_network)
    r = owner.post("/api/link-jobs", json={"url": "https://www.bilibili.com/video/BV1"})
    assert r.status_code != 429  # past the cap check, stopped only by the stubbed resolver
