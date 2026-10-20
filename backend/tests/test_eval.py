"""The eval runner's automatic checks (scripts/eval.py)."""
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


def test_unknown_token_totals_are_excluded_from_known_average(capsys):
    from scripts.eval import summary, print_report
    results = [{"id": "known", "prompt_tokens": 2000, "seconds": 1, "passed": True, "fails": []},
               {"id": "unknown", "prompt_tokens": None, "seconds": 1, "passed": True, "fails": []}]
    got = summary(results)
    assert got["avg_prompt_k"] == 2.0
    assert got["prompt_known_cases"] == 1 and got["prompt_unknown_cases"] == 1
    print_report(results, None)
    printed = capsys.readouterr().out
    assert "未知" in next(line for line in printed.splitlines() if "unknown" in line)
    assert "已知输入均值 2.0k" in printed and "已知 1/2，未知 1" in printed


def test_no_known_usage_has_no_numeric_average():
    from scripts.eval import summary
    got = summary([{"prompt_tokens": None, "seconds": 1, "passed": False}])
    assert got["avg_prompt_k"] is None and got["prompt_unknown_cases"] == 1
