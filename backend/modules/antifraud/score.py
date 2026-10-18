"""风险评分：规则命中权重 + 引流信号加分 → 风险等级（低/中/高）+ 理由 + 证据时间点。

评分配置来自 rules.json 的 scoring 段。同一规则多次命中只计一次权重（按 rule_id 去重），
但命中次数和所有时间点都保留在证据里。引流信号按类型计分，每种上限 max_per_type 个。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .extract import DrainageSignal
from .qrcode import QrcodeHit
from .report import Evidence, Reason
from .rules import RuleHit, RuleLibrary

DEFAULT_THRESHOLDS = {"high": 12, "medium": 6}
DEFAULT_DRAINAGE_WEIGHTS = {
    "wechat_id": 3, "phone": 2, "phone_400": 1, "url": 2, "short_url": 2, "qrcode": 4,
    "max_per_type": 3,
}
LEVEL_LABELS = {"low": "低", "medium": "中", "high": "高"}


@dataclass
class ScoreResult:
    base: int               # sum of distinct rule weights
    drainage_bonus: int     # from wechat/phone/qrcode/url signals
    total: int              # base + drainage_bonus
    level: str              # "low" | "medium" | "high"
    thresholds: dict
    rule_weights: dict      # {rule_id: weight}  (distinct rules that hit)
    drainage_breakdown: dict  # {kind: count_used}

    def as_dict(self) -> dict:
        return {
            "base": self.base,
            "drainage_bonus": self.drainage_bonus,
            "total": self.total,
            "level": self.level,
            "level_label": LEVEL_LABELS.get(self.level, self.level),
            "thresholds": self.thresholds,
            "rule_weights": self.rule_weights,
            "drainage_breakdown": self.drainage_breakdown,
        }


def _thresholds(scoring: dict) -> dict:
    t = scoring.get("thresholds", {})
    return {"high": int(t.get("high", DEFAULT_THRESHOLDS["high"])),
            "medium": int(t.get("medium", DEFAULT_THRESHOLDS["medium"]))}


def _drainage_weights(scoring: dict) -> dict:
    w = scoring.get("drainage_weights", {})
    merged = dict(DEFAULT_DRAINAGE_WEIGHTS)
    merged.update(w)
    return merged


def compute_score(hits: list[RuleHit], signals: list[DrainageSignal],
                  qrcode_hits: list[QrcodeHit], scoring: dict) -> ScoreResult:
    """Base = sum of distinct rule weights; drainage bonus from signals + qrcodes."""
    # distinct rule weights
    rule_weights: dict[str, int] = {}
    for h in hits:
        if h.rule_id not in rule_weights or h.weight > rule_weights[h.rule_id]:
            rule_weights[h.rule_id] = h.weight
    base = sum(rule_weights.values())

    # drainage bonus
    dw = _drainage_weights(scoring)
    cap = int(dw.get("max_per_type", 3))
    counts: Counter = Counter()
    for s in signals:
        counts[s.kind] += 1
    if qrcode_hits:
        counts["qrcode"] += len(qrcode_hits)
    bonus = 0
    breakdown: dict[str, int] = {}
    for kind, n in counts.items():
        used = min(n, cap)
        weight = int(dw.get(kind, 0))
        bonus += used * weight
        if used:
            breakdown[kind] = used

    total = base + bonus
    th = _thresholds(scoring)
    if total >= th["high"]:
        level = "high"
    elif total >= th["medium"]:
        level = "medium"
    else:
        level = "low"
    return ScoreResult(base=base, drainage_bonus=bonus, total=total, level=level,
                       thresholds=th, rule_weights=rule_weights, drainage_breakdown=breakdown)


def _earliest(hits: list[RuleHit]) -> tuple[float, float, RuleHit] | None:
    if not hits:
        return None
    h = min(hits, key=lambda x: x.start)
    return h.start, h.end, h


def build_reasons(hits: list[RuleHit], signals: list[DrainageSignal],
                  qrcode_hits: list[QrcodeHit], lib: RuleLibrary) -> list[Reason]:
    """One reason per hit rule category + one per drainage kind, each citing time-point evidence."""
    reasons: list[Reason] = []
    # group hits by rule_id, keep category order by first appearance
    by_rule: dict[str, list[RuleHit]] = defaultdict(list)
    order: list[str] = []
    for h in hits:
        if h.rule_id not in by_rule:
            order.append(h.rule_id)
        by_rule[h.rule_id].append(h)
    for rid in order:
        group = by_rule[rid]
        first = group[0]
        ev = [Evidence(kind="rule_hit", time=h.start, end=h.end, source=h.source,
                        content=f"在 {h.source} {h.start:.1f}s 命中「{h.name}」：{h.snippet}",
                       detail=h.as_dict()) for h in group]
        reasons.append(Reason(
            summary=f"命中话术「{first.category}·{first.name}」{len(group)} 处，权重 {first.weight}：{first.description}",
            evidence=ev,
        ))
    # drainage signals
    by_kind: dict[str, list[DrainageSignal]] = defaultdict(list)
    kind_order: list[str] = []
    for s in signals:
        if s.kind not in by_kind:
            kind_order.append(s.kind)
        by_kind[s.kind].append(s)
    kind_label = {"wechat_id": "微信号", "phone": "手机号", "phone_400": "400 电话",
                  "url": "网址", "short_url": "短链接"}
    for kind in kind_order:
        group = by_kind[kind]
        ev = [Evidence(kind="drainage", time=s.start, end=s.end, source=s.source,
                       content=f"在 {s.source} {s.start:.1f}s 提取到{kind_label.get(kind, kind)}：{s.value}",
                       detail=s.as_dict()) for s in group]
        reasons.append(Reason(
            summary=f"提取到{kind_label.get(kind, kind)} {len(group)} 个，疑似引流联系方式",
            evidence=ev,
        ))
    # qrcodes
    if qrcode_hits:
        ev = [Evidence(kind="qrcode", time=q.time, end=q.time, source="qrcode",
                       content=f"在第 {q.frame_index} 帧（{q.time:.1f}s）解码二维码：{q.content[:80]}",
                       detail=q.as_dict()) for q in qrcode_hits]
        reasons.append(Reason(
            summary=f"画面中检测到 {len(qrcode_hits)} 个二维码，常用于引流跳转",
            evidence=ev,
        ))
    return reasons


def build_conclusion(score: ScoreResult, hits: list[RuleHit],
                     signals: list[DrainageSignal], qrcode_hits: list[QrcodeHit]) -> str:
    """A one-paragraph Chinese conclusion stating the level and the key signals."""
    label = LEVEL_LABELS[score.level]
    parts: list[str] = []
    if score.level == "high":
        parts.append("该视频存在较高诈骗风险。")
    elif score.level == "medium":
        parts.append("该视频存在一定诈骗风险，需进一步核实。")
    else:
        if not hits and not signals and not qrcode_hits:
            return "未发现明显诈骗话术或引流信号，风险等级低。"
        parts.append("该视频命中少量风险信号，风险等级低，但建议留意。")
    cats = []
    seen = set()
    for h in hits:
        if h.category not in seen:
            seen.add(h.category)
            cats.append(h.category)
    if cats:
        parts.append("命中话术类别：" + "、".join(cats) + "。")
    if signals or qrcode_hits:
        kinds = []
        sc = Counter(s.kind for s in signals)
        if qrcode_hits:
            sc["qrcode"] += len(qrcode_hits)
        kind_label = {"wechat_id": "微信号", "phone": "手机号", "phone_400": "400 电话",
                      "url": "网址", "short_url": "短链接", "qrcode": "二维码"}
        for k, n in sc.items():
            kinds.append(f"{kind_label.get(k, k)}×{n}")
        parts.append("提取到引流信号：" + "、".join(kinds) + "。")
    parts.append(f"综合评分 {score.total}（话术 {score.base} + 引流 {score.drainage_bonus}），风险等级：{label}。")
    return "".join(parts)
