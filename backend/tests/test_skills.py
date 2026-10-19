"""Skills: the fact check and the fraud check as steps the agent can take."""
import asyncio

from modules.agent import skills
from modules.agent.tools import AgentTools, ToolResult, definitions


REPORT = {"summary": {"total": 2, "wrong": 1, "partial": 0}, "claims": [
    {"claim": "空腹喝醋能降血压", "verdict": "wrong", "risk": "high", "reason": "央视网辟谣",
     "timestamp": {"start": 73}, "evidence": {"source": "transcript"},
     "sources": [{"name": "央视网", "url": "https://jiankang.cctv.com/x"}]},
    {"claim": "高血压要遵医嘱服药", "verdict": "correct", "risk": "low", "reason": "卫健委", "timestamp": {"start": 90},
     "evidence": {"source": "screentext"}, "sources": []}]}


def test_the_model_reads_each_verdict_with_its_moment_and_links():
    text = skills.science_digest(REPORT)
    assert "1. [原声 01:13] 空腹喝醋能降血压 —— 错误，风险高：央视网辟谣" in text
    assert "https://jiankang.cctv.com/x" in text and "[画面文字 01:30]" in text
    assert "没有抽出" in skills.science_digest({"claims": [], "message": ""})


def test_skills_are_offered_by_the_composer_switches():
    names = lambda **kw: {d["function"]["name"] for d in definitions(**kw)}  # noqa: E731
    assert {"check_science", "check_fraud"} <= names()
    assert "check_science" not in names(web=False) and "check_fraud" in names(web=False)


def test_a_skill_streams_its_progress_then_returns_the_report(monkeypatch):
    async def fake_factcheck(job, llm, web=True, papers=True):
        yield {"type": "factcheck.claims_extracted", "count": 2}
        yield {"type": "factcheck.claim.verifying", "claim": "空腹喝醋能降血压"}
        yield {"type": "factcheck.claim.done"}
        yield {"type": "factcheck.completed", "report": REPORT}
    import modules.factcheck.run as fc
    monkeypatch.setattr(fc, "run_factcheck", fake_factcheck)
    tools = AgentTools(job=None, llm=object())

    async def go():
        return [item async for item in tools.stream("check_science", {})]
    items = asyncio.run(go())
    assert [i["step"] for i in items[:-1]] == ["科普核查：抽出 2 条说法，逐条查资料", "科普核查 1/2：空腹喝醋能降血压"]
    result = items[-1]
    assert isinstance(result, ToolResult) and not result.error
    assert result.summary == "2 条说法 · 错误 1 · 部分正确 0" and result.data == {"skill": "factcheck", "report": REPORT}


def test_a_skill_that_fails_says_so_to_the_model(monkeypatch):
    async def broken(job, llm, web=True, papers=True):
        yield {"type": "factcheck.error", "message": "转写尚未完成"}
    import modules.factcheck.run as fc
    monkeypatch.setattr(fc, "run_factcheck", broken)

    async def go():
        return [item async for item in AgentTools(job=None, llm=object()).stream("check_science", {})]
    result = asyncio.run(go())[-1]
    assert result.error and "转写尚未完成" in result.text
    assert asyncio.run(_first(AgentTools(job=None, llm=None).stream("check_fraud", {}))).error  # no model, no skill


async def _first(gen):
    async for item in gen:
        return item
