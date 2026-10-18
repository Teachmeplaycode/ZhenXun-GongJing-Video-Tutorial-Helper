"""The eval runner's automatic checks (scripts/eval.py)."""
import asyncio
import json

import pytest

from scripts import eval as evaluator
from scripts.eval import check


def run(answer="", tools=(), status="done"):
    return {"answer": answer, "tools": [{"name": t} for t in tools], "status": status, "error": "繁忙"}


def test_checks_pass_and_fail_with_reasons():
    case = {"checks": {"tools_any": ["web.search", "papers.search"], "tools_none": ["browser.use"],
                       "contains_any": [["6600"], ["够", "不够"]], "contains_none": ["李宗盛"], "timestamps": True}}
    assert check(case, run("电池 6600 毫安时，作者觉得不够大 [03:07]", ["web.search"])) == []
    assert check(case, run("电池 6600，03:07 说的，够用", ["papers.search"])) == []  # bare times count too
    fails = check(case, run("李宗盛", ["browser.use"]))
    assert fails == ["没有调用 web.search / papers.search", "不该调用 browser.use", "回答里没有「6600」",
                     "回答里没有「够 / 不够」", "回答里不该出现「李宗盛」", "没有引用时间点"]


def test_errors_and_no_timestamps():
    assert check({}, run(status="error")) == ["出错：繁忙"]
    assert check({"checks": {"timestamps": False}}, run("共 12:30 分钟")) == ["不该引用时间点"]
    assert check({"checks": {"timestamps": False}}, run("版本 1.12.300")) == []


def test_text_checks_ignore_spaces():
    assert check({"checks": {"contains_any": [["9块9"]]}}, run("咖啡 9 块 9 一杯")) == []


@pytest.mark.parametrize("field,value,error", [
    ("category", None, "缺少 category"),
    ("category", "unknown", "category=unknown"),
    ("qtype", None, "缺少 qtype"),
    ("qtype", "unknown", "qtype=unknown"),
    ("question", 123, "question 应为非空字符串"),
    ("checks", {"tools_any": [[]]}, "tools_any 应为字符串数组"),
    ("checks", {"contains_none": [1]}, "contains_none 应为字符串数组"),
    ("url", {"value": "https://example.com/video"}, "url 应为非空字符串"),
    ("note", True, "note 应为非空字符串"),
    ("checks", {"contains_any": [[]]}, r"contains_any\[0\]"),
    ("checks", {"contains_any": [[""]]}, r"contains_any\[0\]"),
    ("checks", {"contains_none": [" \t\n"]}, "contains_none 应为字符串数组"),
    ("web", [], "web 应为布尔值"),
    ("papers", {}, "papers 应为布尔值"),
    ("webb", False, "case 不支持字段 webb"),
    ("frame", [1], "case 不支持字段 frame"),
])
def test_main_rejects_invalid_dataset_before_starting_backend(tmp_path, monkeypatch, field, value, error):
    spec = {"videos": {"v": {"url": "x", "note": "n", "category": "vlog"}},
            "cases": [{"id": "c1", "video": "v", "question": "q", "rubric": "answer", "qtype": "summary"}]}
    target = spec["videos"]["v"] if field in {"category", "url", "note"} else spec["cases"][0]
    if value is None:
        target.pop(field)
    else:
        target[field] = value
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(evaluator, "CASES", path)
    # Even cases excluded by --only must be validated before backend work or result reads.
    monkeypatch.setattr("sys.argv", ["eval.py", "--only", "different-case"])

    def unexpected_side_effect(*args, **kwargs):
        pytest.fail("invalid data must be rejected before accessing results or starting a backend")

    monkeypatch.setattr(evaluator, "previous", unexpected_side_effect)
    monkeypatch.setattr(evaluator, "Backend", unexpected_side_effect)
    with pytest.raises(ValueError, match=error):
        asyncio.run(evaluator.main())


@pytest.mark.parametrize("controls,expected", [
    ({}, {"web": True, "papers": True, "scope": {"type": "all"}}),
    ({"web": False, "papers": False, "frames": []}, {"web": False, "papers": False, "scope": {"type": "all"}}),
    ({"web": False, "papers": True, "frames": [0, 2]}, {"web": False, "papers": True, "scope": {"type": "frames", "frames": [0, 2]}}),
])
def test_validated_case_controls_preserve_the_actual_request_permissions_and_scope(tmp_path, controls, expected):
    import httpx
    from evals.schema import load

    case = {"id": "c", "video": "v", "question": "question", "rubric": "answer", "qtype": "summary", **controls}
    spec = {"videos": {"v": {"url": "https://example.com/video", "note": "confirmed", "category": "vlog"}}, "cases": [case]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(spec))
    validated = load(path)["cases"][0]
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text='data: {"type":"run.completed"}\n\n')

    async def run_case():
        async with httpx.AsyncClient(base_url="https://backend.test", transport=httpx.MockTransport(handle)) as client:
            result = await evaluator.ask(client, "job", validated)
            assert result["status"] == "done"

    asyncio.run(run_case())
    assert requests == [{"video_id": "job", "question": "question", "history": False, **expected}]
