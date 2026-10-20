"""The eval runner's automatic checks (scripts/eval.py)."""
from scripts.eval import check, summary


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


def test_summary_averages_costs_over_priced_cases_only():
    results = [
        {"passed": True, "seconds": 10, "prompt_tokens": 1000, "completion_tokens": 100,
         "cost_cny": 0.0028, "max_wait_ms": 2300, "judge": None},
        {"passed": True, "seconds": 20, "prompt_tokens": 2000, "completion_tokens": 200,
         "cost_cny": None, "max_wait_ms": 5000, "judge": None},  # no price / unknown usage
        {"passed": False, "seconds": 5, "prompt_tokens": 0, "completion_tokens": 0,
         "cost_cny": 0.0002, "max_wait_ms": 800, "judge": None},
    ]
    s = summary(results)
    assert s["cost_priced"] == "2/3" and s["avg_cost_cny"] == 0.0015 and s["max_cost_cny"] == 0.0028
    assert s["max_wait_s"] == 5.0 and s["avg_completion_k"] == 0.1


def test_summary_without_any_priced_case_reports_none():
    results = [{"passed": True, "seconds": 10, "prompt_tokens": 100, "completion_tokens": 10,
                "cost_cny": None, "max_wait_ms": None, "judge": None}]
    s = summary(results)
    assert s["avg_cost_cny"] is None and s["max_cost_cny"] is None
    assert s["cost_priced"] == "0/1" and s["max_wait_s"] is None
