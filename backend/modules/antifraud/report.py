"""反诈分析报告数据结构 —— 对齐 #2 科普核查报告契约。

顶层字段：
  version=1
  module="antifraud"
  job_id
  video{title, author, platform, url, duration}
  created (Unix 秒)
  status (done|running|error|partial)
  message
  summary
  claims[]
  disclaimer

单条 claim：
  id
  claim (人类可读的结论句)
  original_text (原文片段)
  timestamp{start, end, label}
  evidence{source: transcript|screentext, segment_index}
  verdict (safe|suspicious|fraud)
  risk (high|medium|low)
  reason
  sources[] (本模块规则库 + 提取器，非外部权威来源)
  status (verified|unverified|error)

本模块不产出外部权威来源（如 WHO、证监会），sources 仅记录内部规则/工具；
因此 verdict 为 fraud 时必须基于规则命中 + 引流信号，不能把未知伪装成 safe。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

VERSION = 1
MODULE = "antifraud"

VERDICTS = ("safe", "suspicious", "fraud")
VERDICT_LABELS = {"safe": "未见明显信号", "suspicious": "可疑线索", "fraud": "高风险线索"}
LEVELS = ("high", "medium", "low")
LEVEL_LABELS = {"high": "高", "medium": "中", "low": "低"}
STATUS_OPTIONS = ("done", "running", "error", "partial")


@dataclass
class Timestamp:
    start: float
    end: float
    label: str = ""  # 可选：该片段的人类标签

    def as_dict(self) -> dict:
        return {"start": round(self.start, 2), "end": round(self.end, 2), "label": self.label}


@dataclass
class EvidenceRef:
    source: str          # "transcript" | "screentext" | "qrcode"
    segment_index: int | None = None   # 在对应列表中的索引（可选）

    def as_dict(self) -> dict:
        return {"source": self.source, "segment_index": self.segment_index}


@dataclass
class ClaimSource:
    """本模块内部来源：规则库、提取器、二维码解码器。不伪装成外部权威。"""
    title: str
    url: str = ""
    snippet: str = ""
    trusted: bool = False      # 本模块内部来源一律不标 trusted
    kind: str = ""             # "rule" | "extract" | "qrcode" | "scoring"
    name: str = ""

    def as_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet,
                "trusted": self.trusted, "kind": self.kind, "name": self.name}


@dataclass
class Claim:
    id: str
    claim: str
    original_text: str
    timestamp: Timestamp
    evidence: EvidenceRef
    verdict: str              # "safe" | "suspicious" | "fraud"
    risk: str                 # "high" | "medium" | "low"
    reason: str
    sources: list[ClaimSource] = field(default_factory=list)
    status: str = "verified"  # "verified" | "unverified" | "error"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "claim": self.claim,
            "original_text": self.original_text,
            "timestamp": self.timestamp.as_dict(),
            "evidence": self.evidence.as_dict(),
            "verdict": self.verdict,
            "risk": self.risk,
            "risk_label": LEVEL_LABELS.get(self.risk, self.risk),
            "verdict_label": VERDICT_LABELS.get(self.verdict, self.verdict),
            "reason": self.reason,
            "sources": [s.as_dict() for s in self.sources],
            "status": self.status,
        }


# ---- 向后兼容：旧 pipeline/score 使用的 Evidence/Reason ----

@dataclass
class Evidence:
    """一条带时间点的证据：话术命中、引流信号或二维码解码结果。

    保留用于向后兼容 score.py；新代码请使用 Claim 结构。
    """
    kind: str            # "rule_hit" | "drainage" | "qrcode"
    time: float          # seconds (segment start, or frame time for qrcode)
    end: float           # seconds (segment end; equals time for qrcode)
    source: str          # "transcript" | "screentext" | "qrcode"
    content: str         # human-readable description of what this evidence shows
    detail: dict = field(default_factory=dict)   # structured payload for the UI

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "time": round(self.time, 2),
            "end": round(self.end, 2),
            "source": self.source,
            "content": self.content,
            "detail": self.detail,
        }


@dataclass
class Reason:
    """一条风险理由：一句结论 + 支撑它的证据引用。

    保留用于向后兼容 score.py；新代码请使用 Claim 结构。
    """
    summary: str
    evidence: list[Evidence] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"summary": self.summary, "evidence": [e.as_dict() for e in self.evidence]}


@dataclass
class VideoMeta:
    title: str = ""
    author: str = ""
    platform: str = ""
    url: str = ""
    duration: float = 0.0

    def as_dict(self) -> dict:
        return {"title": self.title, "author": self.author, "platform": self.platform,
                "url": self.url, "duration": round(self.duration, 2)}


@dataclass
class AntifraudReport:
    version: int = VERSION
    module: str = MODULE
    job_id: str = ""
    video: VideoMeta = field(default_factory=VideoMeta)
    created: float = field(default_factory=lambda: time.time())
    status: str = "done"
    message: str = ""
    summary: str = ""
    claims: list[Claim] = field(default_factory=list)
    disclaimer: str = (
        "本报告仅提供风险线索与可用时的模型辅助判断，不构成权威机构认定。"
        "如需确认，请向公安机关、市场监管部门或相关机构核实。"
    )
    limitations: list[str] = field(default_factory=list)
    assessment: dict = field(default_factory=dict)
    score: dict = field(default_factory=dict)       # 内部评分详情
    drainage_signals: list[dict] = field(default_factory=list)
    rule_hits: list[dict] = field(default_factory=list)
    qrcodes: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "module": self.module,
            "job_id": self.job_id,
            "video": self.video.as_dict(),
            "created": round(self.created, 2),
            "status": self.status,
            "message": self.message,
            "summary": self.summary,
            "claims": [c.as_dict() for c in self.claims],
            "disclaimer": self.disclaimer,
            "score": self.score,
            "assessment": self.assessment,
            "limitations": self.limitations,
            "drainage_signals": self.drainage_signals,
            "rule_hits": self.rule_hits,
            "qrcodes": self.qrcodes,
        }
