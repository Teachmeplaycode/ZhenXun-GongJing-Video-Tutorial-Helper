"""权威来源白名单：用于核查报告的出处可信度标注。

核查养生/科普说法时，只有来自权威官方机构、学术期刊或公认医学知识库的来源才标
trusted=True。其余网页结果仍可引用，但标 trusted=False，并在前端以不同样式提示。

白名单按域名后缀匹配（含子域）。新增来源只需在 AUTHORITATIVE 里加一行。
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRule:
    domain: str        # 匹配的域名后缀，如 "nhc.gov.cn"
    name: str          # 展示名，如 "国家卫健委"
    kind: str          # 类别：gov | society | regulator | journal | medical | intl


# 权威来源白名单（Issue #2 要求：国家卫健委、中国营养学会、国家药监局、PubMed 等）
AUTHORITATIVE: list[SourceRule] = [
    SourceRule("nhc.gov.cn", "国家卫健委", "gov"),
    SourceRule("gov.cn", "中国政府网", "gov"),          # 兜底：各级政府官方站点
    SourceRule("nmpa.gov.cn", "国家药监局", "regulator"),
    SourceRule("cnsoc.org.cn", "中国营养学会", "society"),
    SourceRule("cma.org.cn", "中华医学会", "society"),
    SourceRule("chinacdc.cn", "中国疾控中心", "gov"),
    SourceRule("who.int", "世界卫生组织", "intl"),
    SourceRule("mayoclinic.org", "梅奥医学中心", "medical"),
    SourceRule("pubmed.ncbi.nlm.nih.gov", "PubMed", "journal"),
    SourceRule("ncbi.nlm.nih.gov", "美国国家生物技术信息中心", "journal"),
    SourceRule("doi.org", "学术文献 DOI", "journal"),
    SourceRule("openalex.org", "OpenAlex 学术库", "journal"),
    SourceRule("arxiv.org", "arXiv 预印本", "journal"),
    SourceRule("nature.com", "Nature", "journal"),
    SourceRule("nejm.org", "新英格兰医学杂志", "journal"),
    SourceRule("bmj.com", "BMJ 英国医学杂志", "journal"),
    SourceRule("lancet.com", "柳叶刀", "journal"),
    SourceRule("jamanetwork.com", "JAMA 美国医学会杂志", "journal"),
    SourceRule("sciencedirect.com", "ScienceDirect", "journal"),
    SourceRule("springer.com", "Springer", "journal"),
    SourceRule("wiley.com", "Wiley", "journal"),
]

# 类别 → 中文标签（前端展示用）
KIND_LABEL = {
    "gov": "政府官方", "society": "权威学会", "regulator": "监管部门",
    "journal": "学术期刊", "medical": "权威医学机构", "intl": "国际组织",
}


def _host(url: str) -> str:
    host = urllib.parse.urlsplit(url).hostname or ""
    return host.lower().rstrip(".")


def match(url: str) -> SourceRule | None:
    """返回 URL 命中的权威来源规则，未命中返回 None。子域也匹配。"""
    host = _host(url)
    if not host:
        return None
    # 从最长域名后缀开始匹配，避免 "x.gov.cn" 误命中更短的规则
    for rule in sorted(AUTHORITATIVE, key=lambda r: len(r.domain), reverse=True):
        if host == rule.domain or host.endswith("." + rule.domain):
            return rule
    return None


def is_trusted(url: str) -> bool:
    return match(url) is not None


def label(url: str) -> str:
    """来源的可信度展示标签：权威来源返回机构名，否则返回空串。"""
    rule = match(url)
    return rule.name if rule else ""


def kind_of(url: str) -> str:
    rule = match(url)
    return rule.kind if rule else ""
