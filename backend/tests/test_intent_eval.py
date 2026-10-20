"""Evaluation must never present keyword/main-model fallback as local-model accuracy."""
import asyncio

from modules.agent import intent
from scripts import intent_eval


def test_unavailable_decider_does_not_call_main_model(monkeypatch, capsys):
    async def forbidden(*args, **kwargs):
        raise AssertionError("classification fallback must not run in local-model benchmark")

    monkeypatch.setattr(intent, "classify", forbidden)

    class Offline:
        async def choice(self, *args, **kwargs):
            raise RuntimeError("offline")

    rows = asyncio.run(intent_eval.with_decider([("你好", "chat")], Offline()))
    assert rows == []
    intent_eval.report("决策模型", rows)
    printed = capsys.readouterr().out
    assert "不计算准确率" in printed and "%" not in printed


def test_main_model_accuracy_excludes_keyword_fallback(monkeypatch, capsys):
    async def classify(question, decider):
        return (intent.Intent("chat", None, {}, "主模型回退") if question == "hello"
                else intent.by_keywords(question))

    monkeypatch.setattr(intent, "classify", classify)
    rows, name = asyncio.run(intent_eval.with_fallback([("hello", "chat"), ("有没有风险", "fraud")]))
    model_rows = [(q, k, g) for q, k, g in rows if g.how == "主模型回退"]
    assert len(model_rows) == 1 and model_rows[0][0] == "hello"
    assert "1/2" in name
    intent_eval.report(name, model_rows, attempts=rows)
    assert "1/1 = 100%" in capsys.readouterr().out


def test_unknown_usage_is_reported_as_unknown_not_complete_zero(capsys):
    row = intent.Intent("chat", None, {}, "主模型回退", usage={"prompt_tokens": 7, "completion_tokens": None}, elapsed_ms=1)
    intent_eval.report("主模型", [("hello", "chat", row)])
    printed = capsys.readouterr().out
    assert "已知 token" in printed and "prompt 7" in printed
    assert "1 题用量不完整/未知" in printed


def test_failed_classification_still_reports_billable_usage(capsys):
    failed = intent.Intent("fraud", None, {}, "关键词", usage={"prompt_tokens": 9, "completion_tokens": 2})
    intent_eval.report("主模型不可用", [], attempts=[("risk?", "fraud", failed)])
    printed = capsys.readouterr().out
    assert "不计算准确率" in printed and "prompt 9 + completion 2" in printed
