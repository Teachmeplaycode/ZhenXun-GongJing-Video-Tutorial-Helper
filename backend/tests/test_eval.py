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
