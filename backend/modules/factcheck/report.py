"""核查报告的 JSON 结构（Issue #2）。

这份结构同时是给 Issue #3（反诈识别）模块的契约：#3 的反诈报告复用同一组字段
（claim/original_text、timestamp/evidence、verdict/risk、reason、sources、status），
只是 verdict 的取值集合和 risk 的含义不同。主协调者会把本结构交给 #3 的独立 agent。

== 顶层报告结构 ==
{
  "version": 1,                       # 结构版本号
  "module": "factcheck",              # 模块名
  "job_id": "abc123",                 # 对应的 link job id
  "video": {                          # 视频元信息
    "title": "...", "author": "...", "platform": "wechat", "url": "...", "duration": 23.0
  },
  "created": 1731900000.0,            # 报告生成时间（Unix 秒）
  "status": "done",                   # done | running | error | partial
  "message": "",                      # status != done 时的说明
  "summary": {                        # 汇总统计
    "total": 5, "correct": 2, "partial": 1, "wrong": 1, "unverifiable": 1,
    "exaggerations": 2, "trusted_sources": 3
  },
  "claims": [ <claim>, ... ],         # 逐条说法（见下）
  "disclaimer": "辅助判断，不构成医疗建议"   # 固定页脚提示
}

== 单条说法 claim 结构（与 #3 反诈模块共享字段）==
{
  "id": "c1",                         # 说法编号
  "claim": "西柚会与某些降压药发生相互作用",   # 标准化命题（用于检索/判定）
  "original_text": "柚子千万别和降压药一起吃", # 视频里的原话
  "timestamp": {                      # 时间点（#3 约定字段）
    "start": 12.5, "end": 15.0, "label": "00:12"
  },
  "evidence": {                       # 证据来源（#3 约定字段）
    "source": "transcript",           # transcript | screentext
    "segment_index": 3                # 在对应转写/画面文字里的段序号
  },
  "verdict": "partial",               # 判定（#3 约定字段，见 VERDICTS）
  "risk": "medium",                   # 风险等级（#3 约定字段，见 RISKS）
  "reason": "西柚确实会与某些降压药相互作用，但普通柚子影响有限，视频未区分种类。",  # 判定理由
  "sources": [                        # 出处（#3 约定字段）
    {
      "id": "s1",                    # 核实模型实际引用的来源编号
      "title": "...", "url": "...", "snippet": "...",
      "trusted": true, "kind": "journal", "name": "PubMed"
    }
  ],
  "exaggeration": {                   # 夸大用语标注
    "detected": true, "terms": ["千万别"], "categories": ["alarmist"], "note": "恐吓式表述"
  },
  "status": "verified"                # verified | unverified | error（#3 约定字段）
}

== 字段取值约定 ==
verdict（factcheck 取值）:
  correct       正确：说法与权威来源一致
  partial       部分正确：大体对，但有夸大、遗漏或不严谨之处
  wrong         错误：与权威来源矛盾
  unverifiable  无法核实：找不到可靠来源，或说法本身不可证伪

risk（与 #3 对齐的等级，factcheck 语义）:
  high    错误或严重夸大，可能误导用户做出有害健康决定
  medium  部分正确或轻度夸大，需补充说明
  low     正确或无法核实但无害

status:
  verified    已完成核实（有 verdict）
  unverified  未能核实（检索失败、无来源）
  error       处理出错

#3 反诈模块复用说明：#3 的 verdict 取值集合为 {safe, suspicious, fraud}，risk 取值
集合同为 {high, medium, low}（high=疑似诈骗），其余字段（claim/original_text、
timestamp/evidence、reason、sources、status）结构一致，便于主协调者合并展示。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import exaggeration, sources

VERSION = 1
MODULE = "factcheck"
DISCLAIMER = "辅助判断，不构成医疗建议"

VERDICTS = ("correct", "partial", "wrong", "unverifiable")
VERDICT_LABEL = {"correct": "正确", "partial": "部分正确", "wrong": "错误", "unverifiable": "无法核实"}
RISKS = ("high", "medium", "low")
RISK_LABEL = {"high": "高风险", "medium": "中风险", "low": "低风险"}
CLAIM_STATUS = ("verified", "unverified", "error")
REPORT_STATUS = ("done", "running", "error", "partial")


def clock(seconds: float) -> str:
    t = max(0, int(seconds))
    return f"{t // 60:02d}:{t % 60:02d}"


def build_source(title: str, url: str, snippet: str = "") -> dict:
    """构造一个出处条目，自动标注可信度。"""
    rule = sources.match(url)
    return {
        "title": title or url,
        "url": url,
        "snippet": snippet,
        "trusted": rule is not None,
        "kind": rule.kind if rule else "",
        "name": rule.name if rule else "",
    }


def build_claim(
    cid: str,
    claim: str,
    original_text: str,
    start: float,
    end: float,
    evidence_source: str,
    segment_index: int,
    verdict: str = "unverifiable",
    risk: str = "low",
    reason: str = "",
    srcs: list[dict] | None = None,
    status: str = "unverified",
) -> dict:
    """构造一条说法记录。"""
    return {
        "id": cid,
        "claim": claim,
        "original_text": original_text,
        "timestamp": {"start": round(float(start), 2), "end": round(float(end), 2), "label": clock(start)},
        "evidence": {"source": evidence_source, "segment_index": segment_index},
        "verdict": verdict if verdict in VERDICTS else "unverifiable",
        "risk": risk if risk in RISKS else "low",
        "reason": reason,
        "sources": srcs or [],
        "exaggeration": exaggeration.detect(original_text),
        "status": status if status in CLAIM_STATUS else "unverified",
    }


def summarize(claims: list[dict]) -> dict:
    counts = {v: 0 for v in VERDICTS}
    exag = 0
    trusted = set()
    for c in claims:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
        if c["exaggeration"]["detected"]:
            exag += 1
        for s in c["sources"]:
            if s.get("trusted") and s.get("url"):
                trusted.add(s["url"])
    return {
        "total": len(claims),
        "correct": counts["correct"],
        "partial": counts["partial"],
        "wrong": counts["wrong"],
        "unverifiable": counts["unverifiable"],
        "exaggerations": exag,
        "trusted_sources": len(trusted),
    }


def build_report(
    job_id: str,
    video: dict,
    claims: list[dict],
    status: str = "done",
    message: str = "",
) -> dict:
    """构造完整报告。video 取 ResolvedVideo.public() 的子集。"""
    return {
        "version": VERSION,
        "module": MODULE,
        "job_id": job_id,
        "video": {
            "title": video.get("title", ""),
            "author": video.get("author", ""),
            "platform": video.get("platform", ""),
            "url": video.get("canonical_url", ""),
            "duration": video.get("duration"),
        },
        "created": time.time(),
        "status": status if status in REPORT_STATUS else "done",
        "message": message,
        "summary": summarize(claims),
        "claims": claims,
        "disclaimer": DISCLAIMER,
    }


# 报告存进会话时用的 message data 键
DATA_KEY = "factcheck"
