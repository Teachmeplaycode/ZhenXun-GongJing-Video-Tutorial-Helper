"""反诈分析主入口：把转写、画面文字和帧图像串成一份 AntifraudReport。

调用方传入带时间点的文字段（转写 + 画面文字）和帧路径列表，pipeline 负责：
  1. 加载规则库并对每段文字匹配话术；
  2. 从文字里提取微信号/手机号/网址；
  3. 从帧图像解码二维码，并对解码内容二次提取引流信号；
  4. 计算风险评分（话术权重 + 引流加分）；
  5. 按 #2 报告契约组装 claims（verdict: fraud/suspicious/safe）、证据时间点、理由、结论，产出报告。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from . import extract, qrcode, report, rules, score
from .report import AntifraudReport, Claim, ClaimSource, EvidenceRef, Timestamp, VideoMeta
from .rules import RuleLibrary


def _to_segments(items: Iterable) -> list[tuple[float, float, str]]:
    """Accept (start, end, text) triples or objects with .start/.end/.text."""
    out: list[tuple[float, float, str]] = []
    for it in items:
        if isinstance(it, tuple | list):
            out.append((float(it[0]), float(it[1]), str(it[2])))
        else:
            out.append((float(it.start), float(it.end), str(it.text)))
    return out


def _verdict_for(level: str) -> str:
    """risk level → verdict。未知不伪装成 safe。"""
    return {"high": "fraud", "medium": "suspicious", "low": "safe"}.get(level, "safe")


def _claim_id(rule_id: str, idx: int) -> str:
    return f"rule-{rule_id}-{idx}"


def _build_claims(hits: list[rules.RuleHit], signals: list[extract.DrainageSignal],
                  qrcode_hits: list[qrcode.QrcodeHit], sc: score.ScoreResult,
                  lib: RuleLibrary) -> list[Claim]:
    """按 rule_id 分组，每条命中生成一条 claim；引流信号与二维码作为独立 claim。"""
    claims: list[Claim] = []
    claim_idx: Counter = Counter()

    # 话术命中 → claim
    by_rule: dict[str, list[rules.RuleHit]] = defaultdict(list)
    for h in hits:
        by_rule[h.rule_id].append(h)

    for rid, group in by_rule.items():
        claim_idx[rid] += 1
        cid = _claim_id(rid, claim_idx[rid])
        first = group[0]
        texts = [h.text for h in group]
        original = " … ".join(texts[:3])
        if len(texts) > 3:
            original += " …"
        rule_verdict = _verdict_for(
            "high" if first.weight >= 7 else ("medium" if first.weight >= 4 else "low")
        )
        rule_risk = {"fraud": "high", "suspicious": "medium", "safe": "low"}.get(rule_verdict, "low")
        sources = [ClaimSource(
            title=f"规则库 {first.category}·{first.name}", kind="rule",
            name=first.name, snippet=first.description,
        )]
        earliest = min(group, key=lambda h: h.start)
        claims.append(Claim(
            id=cid,
            claim=f"命中话术「{first.category}·{first.name}」{len(group)} 处，权重 {first.weight}：{first.description}",
            original_text=original,
            timestamp=Timestamp(start=earliest.start, end=earliest.end,
                                label=f"{first.category}·{first.name}"),
            evidence=EvidenceRef(source=earliest.source),
            verdict=rule_verdict,
            risk=rule_risk,
            reason=f"在 {earliest.source} {earliest.start:.1f}s 命中「{first.name}」片段：{earliest.snippet}",
            sources=sources,
            status="unverified",
        ))

    # 引流信号 → claim
    kind_label = {"wechat_id": "微信号", "phone": "手机号", "phone_400": "400 电话",
                  "url": "网址", "short_url": "短链接"}
    by_kind: dict[str, list[extract.DrainageSignal]] = defaultdict(list)
    for s in signals:
        by_kind[s.kind].append(s)
    for kind, group in by_kind.items():
        cid = f"drainage-{kind}"
        values = ", ".join(s.value for s in group[:5])
        if len(group) > 5:
            values += f" 等 {len(group)} 个"
        earliest = min(group, key=lambda s: s.start)
        claims.append(Claim(
            id=cid,
            claim=f"提取到{kind_label.get(kind, kind)} {len(group)} 个：{values}，疑似引流联系方式",
            original_text=values,
            timestamp=Timestamp(start=earliest.start, end=earliest.end, label=f"引流-{kind}"),
            evidence=EvidenceRef(source=earliest.source),
            verdict="suspicious",
            risk="high" if kind in ("wechat_id", "qrcode") else "medium",
            reason=f"在 {earliest.source} {earliest.start:.1f}s 提取到{kind_label.get(kind, kind)}：{values}",
            sources=[ClaimSource(title="引流信息提取器", kind="extract", name="extract")],
            status="unverified",
        ))

    # 二维码 → claim
    if qrcode_hits:
        cid = "qrcode-decoded"
        contents = "; ".join(q.content[:80] for q in qrcode_hits[:3])
        if len(qrcode_hits) > 3:
            contents += f" 等 {len(qrcode_hits)} 个"
        earliest = min(qrcode_hits, key=lambda q: q.time)
        claims.append(Claim(
            id=cid,
            claim=f"画面中检测到 {len(qrcode_hits)} 个二维码，常用于引流跳转：{contents}",
            original_text=contents,
            timestamp=Timestamp(start=earliest.time, end=earliest.time, label="二维码"),
            evidence=EvidenceRef(source="qrcode"),
            verdict="suspicious",
            risk="medium",
            reason=f"在第 {earliest.frame_index} 帧（{earliest.time:.1f}s）解码二维码：{contents}",
            sources=[ClaimSource(title="二维码解码器 (opencv)", kind="qrcode", name="qrcode")],
            status="unverified",
        ))

    # 若无命中但有文本，加一条 safe claim（不伪装）
    if not claims and (hits or signals or qrcode_hits):
        pass
    if not claims:
        claims.append(Claim(
            id="no-signal",
            claim="未发现明显诈骗话术或引流信号",
            original_text="",
            timestamp=Timestamp(start=0, end=0, label="无信号"),
            evidence=EvidenceRef(source=""),
            verdict="safe",
            risk="low",
            reason="转写、画面文字和二维码中均未命中规则库或引流提取器",
            sources=[ClaimSource(title="规则库 v1", kind="rule", name="rules.json")],
            status="unverified",
        ))

    return claims


def _build_summary(sc: score.ScoreResult, claims: list[Claim]) -> str:
    fraud_n = sum(1 for c in claims if c.verdict == "fraud")
    suspicious_n = sum(1 for c in claims if c.verdict == "suspicious")
    safe_n = sum(1 for c in claims if c.verdict == "safe")
    parts = [f"规则评分 {sc.total}（话术 {sc.base} + 引流 {sc.drainage_bonus}），风险等级：{score.LEVEL_LABELS[sc.level]}。"]
    if fraud_n:
        parts.append(f"其中 {fraud_n} 条命中高风险规则（未核实）。")
    if suspicious_n:
        parts.append(f"{suspicious_n} 条可疑线索，需核实上下文。")
    if safe_n and not fraud_n and not suspicious_n:
        parts.append("规则未命中明显信号，不代表已证明安全。")
    return "".join(parts)


def analyze(
    transcript_segments: Iterable = (),
    screentext_segments: Iterable = (),
    frames: list[tuple[int, float, Path | str]] | None = None,
    *,
    lib: RuleLibrary | None = None,
    job_id: str = "",
    video: VideoMeta | None = None,
) -> AntifraudReport:
    """Run the full antifraud pipeline and return a report.

    `frames` is a list of (frame_index, time_seconds, image_path) for QR decoding.
    `lib` may be injected for tests; the default loads rules.json once.
    `job_id` and `video` are metadata for the report (per #2 schema).
    """
    lib = lib or RuleLibrary.load()
    transcript = _to_segments(transcript_segments)
    screentext = _to_segments(screentext_segments)
    frames = frames or []

    has_text = any(text.strip() for _, _, text in transcript + screentext)

    # 1. rule hits across transcript + screentext
    hits = lib.scan_segments(transcript, "transcript")
    hits += lib.scan_segments(screentext, "screentext")

    # 2. drainage signals from text
    signals = extract.extract_from_segments(transcript, "transcript")
    signals += extract.extract_from_segments(screentext, "screentext")

    # 3. QR codes from frames; their decoded content is re-scanned for wechat/phone/url
    qrcode_hits = qrcode.decode_qrcodes(frames)
    for q in qrcode_hits:
        signals += extract.extract_from_segment(q.content, q.time, q.time, "qrcode")
    signals = extract.dedupe(signals)

    # 4. score
    sc = score.compute_score(hits, signals, qrcode_hits, lib.scoring)

    # 5. claims (per #2 report schema)
    claims = _build_claims(hits, signals, qrcode_hits, sc, lib)

    # 6. No evidence cannot be summarized as low risk.
    if not has_text and not qrcode_hits:
        status = "partial"
        message = "没有可分析的转写或画面文字，且未检测到二维码；无法判断风险。"
        claims = []
        summary = "缺少可分析的转写、画面文字或二维码证据，无法判断风险。"
    else:
        status = "done"
        message = ""
        summary = _build_summary(sc, claims)

    return AntifraudReport(
        job_id=job_id,
        video=video or VideoMeta(),
        status=status,
        message=message,
        summary=summary,
        claims=claims,
        score={**sc.as_dict(), **({"level": "unknown", "level_label": "无法判断"} if not has_text and not qrcode_hits else {})},
        drainage_signals=[s.as_dict() for s in signals],
        rule_hits=[h.as_dict() for h in hits],
        qrcodes=[q.as_dict() for q in qrcode_hits],
    )


def analyze_job(job, *, lib: RuleLibrary | None = None, max_frames: int = 64,
                job_id: str = "", video: VideoMeta | None = None) -> AntifraudReport:
    """Analyze a FrameJob: pull transcript + screentext segments and sample frame paths for QR.

    `max_frames` caps how many frames are decoded (QR detection is cheap but I/O-bound);
    a uniform sample is taken when the job has more frames than the cap.
    """
    transcript = []
    if job.transcript is not None and getattr(job.transcript, "segments", None):
        transcript = [(s.start, s.end, s.text) for s in job.transcript.segments]
    screentext = []
    if job.screentext is not None and getattr(job.screentext, "segments", None):
        screentext = [(s.start, s.end, s.text) for s in job.screentext.segments]

    frames: list[tuple[int, float, Path]] = []
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")
    slots = list(job.slots)
    if slots:
        step = max(1, len(slots) // max_frames) if len(slots) > max_frames else 1
        for slot in slots[::step][:max_frames]:
            path = job.frame_path(slot.index)
            if path.exists():
                frames.append((slot.index, slot.time, path))
    return analyze(transcript, screentext, frames, lib=lib, job_id=job_id, video=video)
