import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import factcheck_eval as fe  # noqa: E402

ITEM = {"id": "vinegar", "url": "https://x", "reviewed": True, "claims": [
    {"id": "c1", "claim": "每天空腹喝白醋能降血压，不用吃药", "label": "wrong", "evidence": ["https://kepuchina.cn/1"]},
    {"id": "c2", "claim": "高血压要遵医嘱长期服药", "label": "correct", "evidence": ["https://nhc.gov.cn/2"]},
    {"id": "c3", "claim": "醋能软化血管", "label": "wrong", "evidence": ["https://cctv.com/3"]},
]}
RUN = {"claims": [
    {"claim": "高血压患者应坚持服药", "verdict": "wrong", "sources": [{"trusted": True}]},
    {"claim": "空腹喝醋可以替代降压药", "verdict": "wrong", "sources": [{"trusted": True}]},
]}


def test_rows_and_metrics():
    rows = fe.grade(ITEM, RUN, {"c1": 1, "c2": 0, "c3": None})
    m = fe.metrics(rows)
    assert m["claims"] == 3 and m["found"] == {"rate": 0.667, "n": 3, "hit": 2}
    assert m["accuracy"]["hit"] == 1             # c1 right, c2 wrong
    assert m["caught"] == {"rate": 0.5, "n": 2, "hit": 1}   # c3 was never extracted: not caught
    assert m["false_alarm"] == {"rate": 1.0, "n": 1, "hit": 1}
    assert m["sourced"]["rate"] == 1.0
    assert m["confusion"]["wrong"]["wrong"] == 1 and m["confusion"]["wrong"]["未抽取"] == 1
    assert m["confusion"]["correct"]["wrong"] == 1


def test_validation_names_each_problem():
    assert fe.validate({"items": {"vinegar": {k: v for k, v in ITEM.items() if k != "id"}}}) == []
    bad = {"items": {"x": {"url": "", "reviewed": True, "claims": [
        {"id": "a", "claim": "说法", "label": "maybe"}, {"id": "a", "claim": " ", "label": "wrong"}]}}}
    errors = fe.validate(bad)
    assert any("url" in e for e in errors) and any("重复" in e for e in errors)
    assert any("label" in e for e in errors) and any("空的" in e for e in errors) and any("出处" in e for e in errors)


def test_matching_keeps_one_to_one_and_ignores_bad_indexes(monkeypatch):
    async def fake(llm, system, user):
        return {"matches": {"c1": 1, "c2": 1, "c3": "7"}}  # c2 reuses 1, c3 is out of range
    monkeypatch.setattr(fe, "ask_json", fake)
    got = asyncio.run(fe.match(None, ITEM["claims"], RUN["claims"]))
    assert got == {"c1": 1, "c2": None, "c3": None}
    assert asyncio.run(fe.match(None, ITEM["claims"], [])) == {"c1": None, "c2": None, "c3": None}
