"""Fact-check unit and orchestration cases collected by pytest."""
from __future__ import annotations

import asyncio
import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.factcheck import sources, exaggeration, report, extract, verify
from modules.factcheck.run import run_factcheck
from modules.frames import FrameJob
from modules.video_source import ResolvedVideo
from modules.transcript import Transcript
from modules.screentext import ScreenText

import pytest

_CASES = []


def t(name, fn):
    _CASES.append((name, fn))


# === sources.py ===

def _s1():
    r = sources.match("https://www.nhc.gov.cn/jkj/s3577/202301/abc.shtml")
    assert r is not None and r.name == "国家卫健委", f"got {r}"
t("匹配权威来源 nhc.gov.cn", _s1)

def _s2():
    r = sources.match("https://news.xxx.gov.cn/abc")
    assert r is not None and r.kind == "gov", f"got {r}"
t("子域匹配 gov.cn", _s2)

def _s3():
    r = sources.match("https://pubmed.ncbi.nlm.nih.gov/12345678/")
    assert r is not None and r.name == "PubMed", f"got {r}"
t("PubMed 命中", _s3)

def _s4():
    r = sources.match("https://www.some-random-blog.com/post")
    assert r is None, f"got {r}"
t("非权威来源返回 None", _s4)

def _s5():
    r = sources.match("")
    assert r is None, f"got {r}"
t("空 URL 返回 None", _s5)

def _s6():
    assert sources.is_trusted("https://www.who.int/news-room")
t("is_trusted 为真", _s6)

def _s7():
    assert not sources.is_trusted("https://example.com")
t("is_trusted 为假", _s7)

def _s8():
    lbl = sources.label("https://www.nmpa.gov.cn/xx/yy")
    assert lbl == "国家药监局", f"got {lbl}"
t("label 返回机构名", _s8)

def _s9():
    lbl = sources.label("https://example.com/foo")
    assert lbl == "", f"got {lbl!r}"
t("label 空串", _s9)

def _s10():
    k = sources.kind_of("https://arxiv.org/abs/1234.5678")
    assert k == "journal", f"got {k}"
t("kind_of 返回类别", _s10)

# === exaggeration.py ===

def _e1():
    d = exaggeration.detect("柚子千万别和降压药一起吃")
    assert d["detected"], "should detect"
    assert "千万别" in d["terms"], f"terms: {d['terms']}"
    assert "alarmist" in d["categories"], f"cats: {d['categories']}"
t("恐吓式用语检测", _e1)

def _e2():
    d = exaggeration.detect("这个方子包治百病")
    assert "cure" in d["categories"], f"cats: {d['categories']}"
t("夸大疗效检测", _e2)

def _e3():
    d = exaggeration.detect("所有人都一定会得这个病")
    assert "absolute" in d["categories"], f"cats: {d['categories']}"
t("绝对化用语检测", _e3)

def _e4():
    d = exaggeration.detect("千万别再不知道就晚了，包治百病")
    assert d["detected"]
    assert len(d["categories"]) >= 2, f"cats: {d['categories']}"
t("多类命中", _e4)

def _e5():
    d = exaggeration.detect("苹果是一种常见水果")
    assert not d["detected"], f"got {d}"
t("无夸大用语", _e5)

def _e6():
    d = exaggeration.detect("")
    assert not d["detected"]
t("空文本不报错", _e6)

# === report.py ===

def _rp1():
    s = report.build_source("PubMed 文章", "https://pubmed.ncbi.nlm.nih.gov/12345678/", "摘要...")
    assert s["trusted"], "should be trusted"
    assert s["name"] == "PubMed", f"got {s['name']}"
    assert s["kind"] == "journal", f"got {s['kind']}"
t("build_source 标注权威", _rp1)

def _rp2():
    s = report.build_source("某博客", "https://blog.example.com/post", "...")
    assert not s["trusted"]
    assert s["name"] == "", f"got {s['name']!r}"
t("build_source 普通来源", _rp2)

def _rp3():
    assert report.clock(0) == "00:00"
    assert report.clock(65) == "01:05"
    assert report.clock(3661) == "61:01"
t("clock 格式化", _rp3)

def _rp4():
    c = report.build_claim("c1", "命题", "原话", 12.5, 15.0, "transcript", 3)
    assert c["id"] == "c1"
    assert c["claim"] == "命题"
    assert c["original_text"] == "原话"
    assert c["timestamp"]["start"] == 12.5
    assert c["timestamp"]["label"] == "00:12"
    assert c["verdict"] == "unverifiable"
    assert c["exaggeration"]["detected"] is False
t("build_claim 基础", _rp4)

def _rp5():
    c = report.build_claim("c2", "命题", "千万别吃", 0, 5, "transcript", 0)
    assert c["exaggeration"]["detected"]
    assert "千万别" in c["exaggeration"]["terms"]
t("build_claim 夸大用语", _rp5)

def _rp6():
    c = report.build_claim("c3", "x", "x", 0, 1, "transcript", 0, verdict="invalid")
    assert c["verdict"] == "unverifiable"
t("build_claim verdict 校验", _rp6)

def _rp7():
    claims = [
        report.build_claim("c1", "", "", 0, 1, "transcript", 0, verdict="correct",
                           srcs=[report.build_source("", "https://pubmed.ncbi.nlm.nih.gov/123", "")]),
        report.build_claim("c2", "", "", 0, 1, "transcript", 0, verdict="partial"),
        report.build_claim("c3", "", "千万别", 0, 1, "transcript", 0, verdict="wrong",
                           srcs=[report.build_source("", "https://who.int/", ""),
                                 report.build_source("", "https://example.com", "")]),
    ]
    s = report.summarize(claims)
    assert s["total"] == 3
    assert s["correct"] == 1
    assert s["partial"] == 1
    assert s["wrong"] == 1
    assert s["exaggerations"] == 1
    assert s["trusted_sources"] == 2
t("summarize 统计", _rp7)

def _rp8():
    claims = [report.build_claim("c1", "命题", "原话", 0, 1, "transcript", 0, verdict="correct")]
    r = report.build_report("job123", {
        "title": "测试视频", "author": "测试者", "platform": "wechat",
        "canonical_url": "https://example.com", "duration": 23.0
    }, claims)
    assert r["version"] == 1
    assert r["module"] == "factcheck"
    assert r["job_id"] == "job123"
    assert r["video"]["title"] == "测试视频"
    assert r["disclaimer"] == "辅助判断，不构成医疗建议"
    assert len(r["claims"]) == 1
    assert r["summary"]["total"] == 1
t("build_report 完整", _rp8)

# === extract.py ===

def _ex1():
    t = extract.transcript_text([
        {"start": 0, "end": 2, "text": "你好"},
        {"start": 2.5, "end": 5, "text": "世界"},
    ])
    assert "[00 0.0-2.0] 你好" in t
    assert "[01 2.5-5.0] 世界" in t
t("transcript_text 拼接", _ex1)

def _ex2():
    t = extract.screentext_text([{"start": 10, "end": 12, "text": "画面文字"}])
    assert "画面文字" in t
t("screentext_text 拼接", _ex2)

def _ex3():
    data = extract._parse('[{"claim":"test","original_text":"t","start":1,"end":2,"source":"transcript","segment_index":0}]')
    assert len(data) == 1
    assert data[0]["claim"] == "test"
t("_parse 纯 JSON", _ex3)

def _ex4():
    data = extract._parse("```json\n[{\"claim\":\"x\"}]\n```")
    assert len(data) == 1
    assert data[0]["claim"] == "x"
t("_parse 代码块围栏", _ex4)

def _ex5():
    data = extract._parse('{"claims":[{"claim":"a"}]}')
    assert len(data) == 1
    assert data[0]["claim"] == "a"
t("_parse 含 claims 字段", _ex5)

def _ex6():
    assert extract._parse("") == []
    assert extract._parse("not json") == []
t("_parse 空/无效", _ex6)

def _ex7():
    c = extract._clean({"claim": "命题", "original_text": "原话", "start": 1, "end": 3, "source": "transcript", "segment_index": 2})
    assert c["claim"] == "命题"
    assert c["start"] == 1.0
    assert c["end"] == 3.0
    assert c["source"] == "transcript"
t("_clean 完整条目", _ex7)

def _ex8():
    c = extract._clean({"original_text": "原话", "start": 0, "end": 1})
    assert c["claim"] == "原话"
t("_clean 缺 claim 用 original 补", _ex8)

def _ex9():
    assert extract._clean({}) is None
t("_clean 空条目丢弃", _ex9)

def _ex10():
    c = extract._clean({"claim": "x", "original_text": "x", "start": 5, "end": 2})
    assert c["start"] == 2.0 and c["end"] == 5.0, f"start={c['start']} end={c['end']}"
t("_clean 自动翻转 start>end", _ex10)

def _ex11():
    c = extract._clean({"claim": "x" * 300, "original_text": "y" * 500, "start": 0, "end": 1})
    assert len(c["claim"]) <= 200
    assert len(c["original_text"]) <= 300
t("_clean 截断超长文本", _ex11)

# === verify.py ===

def _v1():
    srcs = [
        report.build_source("PubMed", "https://pubmed.ncbi.nlm.nih.gov/123", "摘要"),
        report.build_source("Blog", "https://blog.example.com", "普通"),
    ]
    d = verify._source_digest(srcs)
    assert "[权威]" in d
    assert "[普通]" in d
    assert "PubMed" in d
t("_source_digest 权威标记", _v1)

def _v2():
    assert verify._source_digest([]) == "（无来源）"
t("_source_digest 空", _v2)

def _v3():
    v = verify._parse_verdict('{"verdict":"wrong","risk":"high","reason":"与权威来源矛盾"}')
    assert v["verdict"] == "wrong"
    assert v["risk"] == "high"
    assert "矛盾" in v["reason"]
t("_parse_verdict 完整 JSON", _v3)

def _v4():
    v = verify._parse_verdict("```json\n{\"verdict\":\"correct\",\"risk\":\"low\"}\n```")
    assert v["verdict"] == "correct"
t("_parse_verdict 代码块围栏", _v4)

def _v5():
    v = verify._parse_verdict("not json")
    assert v["verdict"] == "unverifiable"
    assert v["risk"] == "low"
t("_parse_verdict 无效回退", _v5)

def _v6():
    v = verify._parse_verdict("")
    assert v["verdict"] == "unverifiable"
t("_parse_verdict 空回退", _v6)

def _v7():
    v = verify._parse_verdict('{"verdict":"invalid","risk":"invalid"}')
    assert v["verdict"] == "unverifiable"
    assert v["risk"] == "low"
t("_parse_verdict 校验取值", _v7)

def _v8():
    assert verify.risk_for_verdict("wrong") == "high"
    assert verify.risk_for_verdict("partial") == "medium"
    assert verify.risk_for_verdict("correct") == "low"
t("risk_for_verdict 兜底", _v8)

# === 集成：模拟抽取+核实流程 ===


async def mock_ask(messages, max_tokens):
    if "医学/科普事实核查员" in messages[0]["content"]:
        return json.dumps({"verdict": "partial", "risk": "medium", "reason": "需区分具体药物"})
    return json.dumps([{
        "claim": "西柚与降压药相互作用",
        "original_text": "柚子千万别和降压药一起吃",
        "start": 12, "end": 15,
        "source": "transcript", "segment_index": 0
    }], ensure_ascii=False)


async def mock_search(query, limit):
    return [report.build_source(
        "PubMed 文章", "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "西柚汁与某些降压药存在相互作用，可影响药物代谢。")]


def _int1():
    import tempfile
    from pathlib import Path
    video = ResolvedVideo("wechat", "test123", "https://example.com", "测试视频", 60.0, [],
                          parts=[], author="测试")
    tmpdir = Path(tempfile.mkdtemp())
    job = FrameJob("job_test", video, None, tmpdir)
    job.transcript = Transcript("done", "", [
        type("Seg", (), {"as_dict": lambda s: {"start": 0, "end": 2, "text": "你好"}, "start": 0, "end": 2, "text": "你好"})(),
        type("Seg", (), {"as_dict": lambda s: {"start": 12, "end": 15, "text": "柚子千万别和降压药一起吃"},
              "start": 12, "end": 15, "text": "柚子千万别和降压药一起吃"})(),
    ])
    job.screentext = ScreenText("done", "", [])

    async def run():
        events = []
        async for ev in run_factcheck(job, None, ask=mock_ask, search=mock_search):
            events.append(ev)

        assert any(e["type"] == "factcheck.started" for e in events), "缺少 started"
        assert any(e["type"] == "factcheck.claims_extracted" for e in events), "缺少 claims_extracted"
        assert any(e["type"] == "factcheck.claim.verifying" for e in events), "缺少 verifying"
        assert any(e["type"] == "factcheck.claim.done" for e in events), "缺少 claim.done"
        completed = [e for e in events if e["type"] == "factcheck.completed"]
        assert len(completed) == 1, f"completed count: {len(completed)}"
        rpt = completed[0]["report"]
        assert rpt["summary"]["total"] == 1
        assert len(rpt["claims"]) == 1
        claim = rpt["claims"][0]
        assert claim["verdict"] == "partial"
        assert claim["risk"] == "medium"
        assert claim["exaggeration"]["detected"]
        assert "千万别" in claim["exaggeration"]["terms"]
        assert claim["exaggeration"]["categories"] == ["alarmist"]
        assert len(claim["sources"]) > 0
        assert claim["sources"][0]["trusted"]

    asyncio.run(run())

t("完整流程 mock 抽取+核实", _int1)


@pytest.mark.parametrize("name,fn", _CASES, ids=[name for name, _ in _CASES])
def test_factcheck_case(name, fn):
    fn()
