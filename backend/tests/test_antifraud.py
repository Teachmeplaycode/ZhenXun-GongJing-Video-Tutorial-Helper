"""反诈模块单元测试：规则匹配、引流提取、评分、报告结构。

测试覆盖：
  - 规则库加载与匹配（含边界情况）
  - 微信号/手机号/网址提取（含边界情况）
  - 风险评分阈值与等级映射
  - 报告结构对齐 #2 schema（verdict: safe|suspicious|fraud, risk: high|medium|low）
  - 二维码解码（无 cv2 时跳过，不伪造通过）

不依赖网络、不依赖 LLM、不依赖真实视频文件。
"""
import shutil
from pathlib import Path

import pytest

from modules.antifraud import analyze, Rule, RuleHit, RuleLibrary
from modules.antifraud.extract import (
    DrainageSignal, extract_from_segment, extract_wechat_ids, extract_phones, extract_urls,
)
from modules.antifraud.qrcode import QrcodeHit, decode_qrcode_image
from modules.antifraud.report import AntifraudReport, Claim, ClaimSource, EvidenceRef, Timestamp, VideoMeta
from modules.antifraud.rules import RuleLibrary as _
from modules.antifraud.score import compute_score


# ---- 规则库与规则匹配 -------------------------------------------------------


class TestRuleLibrary:
    def test_loads_rules_json(self):
        lib = RuleLibrary.load()
        assert lib.version == 1
        assert len(lib.rules) >= 5
        assert any(r.id == "guaranteed_high_return" for r in lib.rules)

    def test_rule_matches_phrase(self):
        lib = RuleLibrary.load()
        hits = lib.scan_text("这个产品保本保息，年化收益高达 20%", 0, 10, "transcript")
        assert len(hits) >= 1
        ids = {h.rule_id for h in hits}
        assert "guaranteed_high_return" in ids or "exaggerated_return" in ids

    def test_rule_matches_nothing(self):
        lib = RuleLibrary.load()
        hits = lib.scan_text("今天天气真好，适合散步", 0, 10, "transcript")
        assert hits == []

    def test_rule_case_insensitive(self):
        lib = RuleLibrary.load()
        hits = lib.scan_text("稳赚不赔", 0, 10, "transcript")
        assert len(hits) >= 1
        hits2 = lib.scan_text("WENZHuan BU PEI", 0, 10, "transcript")
        # 中文不会被 case-insensitive 影响，但确认至少不报错

    def test_rule_hit_has_evidence(self):
        lib = RuleLibrary.load()
        hits = lib.scan_text("加微信领资料", 0, 10, "transcript")
        assert hits
        h = hits[0]
        assert h.snippet
        assert h.start == 0
        assert h.end == 10
        assert h.source == "transcript"


# ---- 引流信息提取 -----------------------------------------------------------


class TestWechatExtraction:
    def test_prefix_wechat(self):
        ids = extract_wechat_ids("加微信 abc12345")
        assert ids == ["abc12345"]

    def test_vx_prefix(self):
        ids = extract_wechat_ids("VX: xyz78901")
        assert ids == ["xyz78901"]

    def test_no_prefix_no_match(self):
        """Bare English word without prefix must NOT be matched."""
        ids = extract_wechat_ids("hello12345")
        assert ids == []

    def test_too_short_no_match(self):
        ids = extract_wechat_ids("加微信 abc12")
        assert ids == []

    def test_dedup(self):
        ids = extract_wechat_ids("加微信 abc12345 加我微信 abc12345")
        assert ids == ["abc12345"]

    def test_multiple_ids(self):
        ids = extract_wechat_ids("加微信 abc12345 加V xyz98765")
        assert len(ids) == 2
        assert "abc12345" in ids
        assert "xyz98765" in ids


class TestPhoneExtraction:
    def test_mobile(self):
        kinds, values = zip(*extract_phones("电话 13812345678"))
        assert "phone" in kinds
        assert "13812345678" in values

    def test_mobile_with_spaces(self):
        kinds, values = zip(*extract_phones("138 1234 5678"))
        assert "phone" in kinds
        assert "13812345678" in values

    def test_mobile_with_dash(self):
        kinds, values = zip(*extract_phones("138-1234-5678"))
        assert "phone" in kinds
        assert "13812345678" in values

    def test_no_false_positive_long_number(self):
        """A 15-digit number must not match."""
        result = extract_phones("138123456789012")
        assert not result

    def test_400_number(self):
        kinds, values = zip(*extract_phones("400-123-4567"))
        assert "phone_400" in kinds
        assert "4001234567" in values


class TestUrlExtraction:
    def test_http_url(self):
        kinds, values = zip(*extract_urls("访问 https://example.com/path"))
        assert "url" in kinds
        assert "https://example.com/path" in values

    def test_short_domain(self):
        kinds, values = zip(*extract_urls("t.cn/abc123"))
        assert "short_url" in kinds
        assert "t.cn/abc123" in values

    def test_url_prefix(self):
        kinds, values = zip(*extract_urls("网址 example.com"))
        assert "url" in kinds
        assert "example.com" in values


class TestDrainageSignal:
    def test_extract_from_segment(self):
        signals = extract_from_segment("加微信 abc12345 电话 13812345678", 0, 10, "transcript")
        kinds = {s.kind for s in signals}
        assert "wechat_id" in kinds
        assert "phone" in kinds

    def test_dedupe(self):
        from modules.antifraud.extract import dedupe
        # extract_from_segment 内部已去重，所以构造两个不同时间的相同信号
        s1 = DrainageSignal("wechat_id", "abc12345", "abc12345", 0, 10, "transcript", "加微信 abc12345")
        s2 = DrainageSignal("wechat_id", "abc12345", "abc12345", 1, 11, "transcript", "加微信 abc12345")
        deduped = dedupe([s1, s2])
        assert len(deduped) == 1


# ---- 风险评分 ---------------------------------------------------------------


class TestScoring:
    def test_empty_score(self):
        sc = compute_score([], [], [], {})
        assert sc.total == 0
        assert sc.level == "low"

    def test_rule_weight_sums(self):
        lib = RuleLibrary.load()
        # 用一个 weight=8 的规则，阈值 high=12, medium=6，所以 level=medium
        hits = [RuleHit(
            rule_id="guaranteed_high_return", category="保本高收益", name="保本/稳赚/零风险承诺",
            weight=8, snippet="保本保息", text="保本保息", start=0, end=10, source="transcript"
        )]
        sc = compute_score(hits, [], [], lib.scoring)
        assert sc.base == 8
        assert sc.level == "medium"

    def test_distinct_rules_only(self):
        lib = RuleLibrary.load()
        hits = [
            RuleHit("r1", "c", "n", 8, "s", "t", 0, 10, "transcript"),
            RuleHit("r1", "c", "n", 8, "s", "t", 1, 11, "transcript"),
            RuleHit("r2", "c", "n", 5, "s", "t", 2, 12, "transcript"),
        ]
        sc = compute_score(hits, [], [], lib.scoring)
        assert sc.base == 13  # 8 + 5

    def test_drainage_bonus(self):
        lib = RuleLibrary.load()
        signals = [DrainageSignal("wechat_id", "abc12345", "abc12345", 0, 10, "transcript", "加微信 abc12345")]
        sc = compute_score([], signals, [], lib.scoring)
        assert sc.drainage_bonus >= 3

    def test_qrcode_bonus(self):
        lib = RuleLibrary.load()
        hits = [QrcodeHit(0, 0, "https://evil.com", "frame.jpg")]
        sc = compute_score([], [], hits, lib.scoring)
        assert sc.drainage_bonus >= 4

    def test_medium_threshold(self):
        lib = RuleLibrary.load()
        hits = [RuleHit("r", "c", "n", 6, "s", "t", 0, 10, "transcript")]
        sc = compute_score(hits, [], [], lib.scoring)
        assert sc.level == "medium"

    def test_low_threshold(self):
        lib = RuleLibrary.load()
        hits = [RuleHit("r", "c", "n", 3, "s", "t", 0, 10, "transcript")]
        sc = compute_score(hits, [], [], lib.scoring)
        assert sc.level == "low"


# ---- 报告结构 ---------------------------------------------------------------


class TestReportSchema:
    def test_report_has_required_fields(self):
        r = AntifraudReport(job_id="j1", status="done", summary="test")
        d = r.as_dict()
        assert d["version"] == 1
        assert d["module"] == "antifraud"
        assert d["job_id"] == "j1"
        assert "video" in d
        assert "created" in d
        assert "status" in d
        assert "summary" in d
        assert "claims" in d
        assert "disclaimer" in d

    def test_claim_has_required_fields(self):
        c = Claim(
            id="c1", claim="test", original_text="原文",
            timestamp=Timestamp(0, 10, "label"),
            evidence=EvidenceRef(source="transcript"),
            verdict="fraud", risk="high", reason="因为…",
            sources=[ClaimSource(title="规则库", kind="rule", name="r")],
            status="verified",
        )
        d = c.as_dict()
        assert d["id"] == "c1"
        assert d["verdict"] == "fraud"
        assert d["risk"] == "high"
        assert "timestamp" in d
        assert "evidence" in d
        assert "sources" in d
        assert "risk_label" in d
        assert "verdict_label" in d

    def test_claim_sources_not_trusted(self):
        c = Claim(
            id="c1", claim="test", original_text="",
            timestamp=Timestamp(0, 0), evidence=EvidenceRef(source=""),
            verdict="safe", risk="low", reason="",
            sources=[ClaimSource(title="规则库", kind="rule", name="r")],
        )
        assert c.sources[0].trusted is False

    def test_disclaimer_present(self):
        r = AntifraudReport()
        assert r.disclaimer
        # 免责声明应明确说明不构成权威机构认定
        assert "不构成" in r.disclaimer or "权威" in r.disclaimer


# ---- 端到端分析 -------------------------------------------------------------


class TestAnalyze:
    def test_fraud_text_produces_claims(self):
        r = analyze(
            transcript_segments=[(0, 10, "保本保息，年化收益 20%，加微信 abc12345 领资料")],
        )
        assert r.status == "done"
        assert r.claims
        fraud_claims = [c for c in r.claims if c.verdict == "fraud"]
        assert len(fraud_claims) >= 1

    def test_safe_text_produces_safe_claim(self):
        r = analyze(
            transcript_segments=[(0, 10, "今天天气真好，适合散步")],
        )
        assert r.status == "done"
        assert r.claims
        assert all(c.verdict == "safe" for c in r.claims)

    def test_no_data_status(self):
        r = analyze()
        assert r.status == "partial"

    def test_schema_fields_present(self):
        r = analyze(
            transcript_segments=[(0, 10, "保本保息")],
            job_id="j1",
            video=VideoMeta(title="测试视频", platform="bilibili", duration=60),
        )
        d = r.as_dict()
        assert d["job_id"] == "j1"
        assert d["video"]["title"] == "测试视频"
        assert d["video"]["platform"] == "bilibili"
        assert d["video"]["duration"] == 60


# ---- 二维码解码（无 cv2 时跳过） --------------------------------------------


class TestQrcode:
    def test_missing_file_returns_empty(self):
        results = decode_qrcode_image("/nonexistent/file.jpg")
        assert results == []

    def test_qrcode_hit_structure(self):
        hit = QrcodeHit(frame_index=5, time=10.0, content="https://example.com", source_path="f.jpg")
        d = hit.as_dict()
        assert d["frame_index"] == 5
        assert d["time"] == 10.0
        assert d["content"] == "https://example.com"


# ---- 边界情况 ---------------------------------------------------------------


class TestEdgeCases:
    def test_empty_segment(self):
        lib = RuleLibrary.load()
        hits = lib.scan_text("", 0, 10, "transcript")
        assert hits == []

    def test_whitespace_segment(self):
        lib = RuleLibrary.load()
        hits = lib.scan_text("   \n\t  ", 0, 10, "transcript")
        assert hits == []

    def test_extract_empty_segment(self):
        signals = extract_from_segment("", 0, 10, "transcript")
        assert signals == []

    def test_score_with_empty_lists(self):
        lib = RuleLibrary.load()
        sc = compute_score([], [], [], lib.scoring)
        assert sc.total == 0
        assert sc.level == "low"
        assert sc.rule_weights == {}
        assert sc.drainage_breakdown == {}


def test_wechat_overlength_is_not_silently_truncated():
    assert extract_wechat_ids('微信 abcdefghijklmnopqrstuvwxyz') == []


@pytest.mark.parametrize('text', [
    '请相信 teacher123 的判断', '这封书信 teacher123 已经读过',
    '请信任 teacher123 的判断', '信 teacher123',
    'avxteacher123', 'envx: teacher123', 'index: teacher123',
    'nav/x: teacher123', 'box/v: teacher123',
])
def test_wechat_requires_a_complete_prefix_outside_ascii_words(text):
    assert extract_wechat_ids(text) == []


@pytest.mark.parametrize('prefix', [
    '微信', '微信号', '加微信', '加我微信', '加我微信号',
    'VX', 'vx', 'Vx', '加VX', '加我VX', '加V', '加X', '加 v', '加 x',
    'v:', 'x：', 'v/x', 'x/v', '威信', '薇信',
])
def test_explicit_wechat_prefixes_preserve_the_entire_id(prefix):
    assert extract_wechat_ids(prefix + ' teacher123') == ['teacher123']


@pytest.mark.parametrize('prefix', ['加VX', '加vx', '加Vx', '加v/x', '加x/v'])
def test_overlapping_wechat_prefixes_do_not_duplicate_or_shift_the_id(prefix):
    assert extract_wechat_ids(prefix + 'abc12345') == ['abc12345']
    assert extract_wechat_ids(prefix + 'abc12') == []
    assert extract_wechat_ids(prefix + 'abcdefghijklmnopqrstuvwxyz') == []


@pytest.mark.parametrize('source', ['transcript', 'screentext'])
@pytest.mark.parametrize('text', [
    '请相信 teacher123 的判断', '这封书信 teacher123 已经读过', '请信任 teacher123 的判断',
])
def test_ordinary_trust_and_letter_text_does_not_create_drainage_claims(source, text):
    result = analyze(**{source + '_segments': [(4, 9, text)]})
    assert result.drainage_signals == []
    assert result.score['drainage_bonus'] == 0
    assert not any(c.id.startswith('drainage-') or c.risk == 'high' for c in result.claims)


def test_dedupe_keeps_earliest_across_input_sources():
    from modules.antifraud.extract import dedupe
    late = DrainageSignal('phone', '13812345678', '', 40, 41, 'transcript', '')
    early = DrainageSignal('phone', '13812345678', '', 3, 4, 'screentext', '')
    assert dedupe([late, early])[0].start == 3


def test_normal_chinese_character_is_not_a_trading_pattern():
    hits = RuleLibrary.load().scan_text('单人入场，老师讲历史。', 0, 2, 'transcript')
    assert not any(h.rule_id == 'follow_and_trade' for h in hits)


def test_real_qr_decode_and_pipeline(tmp_path):
    import cv2
    import segno
    path = tmp_path / 'qr.png'
    segno.make('https://example.com/offer', micro=False).save(path, scale=8, border=4)
    assert cv2.imread(str(path)) is not None
    assert decode_qrcode_image(path) == ['https://example.com/offer']
    result = analyze(frames=[(2, 12.5, path), (3, 13.5, path)])
    assert len(result.qrcodes) == 1
    assert result.qrcodes[0]['time'] == 12.5
    assert any(c.timestamp.start == 12.5 and c.evidence.source == 'qrcode' for c in result.claims)
    assert result.drainage_signals[0]['value'] == 'https://example.com/offer'


def _job(tmp_path, text='这是反诈教育，不要相信保本保息。'):
    from types import SimpleNamespace
    from modules.frames import FrameJob
    from modules.video_source import ResolvedVideo
    v = ResolvedVideo('local', 'v', '', '反诈教学', 30, [], author='作者')
    job = FrameJob('j1', v, None, tmp_path, count=1)
    # A complete source fixture has one actual readable frame, not pending placeholders.
    import cv2
    import numpy as np
    cv2.imwrite(str(job.frame_path(0)), np.full((120, 160, 3), 255, dtype=np.uint8))
    job.slots[0].status = 'ok'
    job.transcript = SimpleNamespace(status='done', segments=[SimpleNamespace(start=10, end=20, text=text)])
    job.screentext = SimpleNamespace(status='empty', segments=[])
    return job


@pytest.mark.parametrize('text', [
    '请相信 teacher123 的判断', '这封书信 teacher123 已经读过', '请信任 teacher123 的判断',
])
@pytest.mark.parametrize('partial', [False, True])
def test_api_ordinary_trust_text_never_becomes_high_risk_drainage(tmp_path, monkeypatch, text, partial):
    import asyncio
    import httpx
    import app as api
    job = _job(tmp_path, text)
    if partial:
        job.screentext.status = 'running'
    monkeypatch.setitem(api.jobs, 'trust-text', job)
    monkeypatch.setattr(api, 'get_llm', lambda: None)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
            response = await client.get('/api/link-jobs/trust-text/antifraud')
            assert response.status_code == 200
            report = response.json()
            assert report['drainage_signals'] == []
            assert report['score']['drainage_bonus'] == 0
            assert report['score']['level'] == ('unknown' if partial else 'low')
            assert not any(c['id'].startswith('drainage-') or c['risk'] == 'high' for c in report['claims'])
            assert report['assessment']['risk'] != 'high'
    asyncio.run(run())


class _Model:
    def __init__(self, answer):
        self.answer = answer
        self.messages = None

    async def stream(self, messages, usage, **kwargs):
        self.messages = messages
        yield self.answer


def test_model_review_uses_context_and_observed_evidence(tmp_path):
    import asyncio
    from modules.antifraud.review import analyze_reviewed
    model = _Model('{"risk":"low","reason":"这是引用骗局话术的反诈教育，请勿转账。","evidence_ids":["segment-transcript-0"]}')
    result = asyncio.run(analyze_reviewed(_job(tmp_path), client=model, job_id='j1'))
    assert result.assessment['risk'] == 'low'
    assert result.status == 'done'
    assert result.video.title == '反诈教学'
    assert result.claims[0].timestamp.start == 10
    assert result.claims[0].status == 'unverified'
    assert '反诈教育' in model.messages[1]['content']
    assert '机构' in result.message


def test_model_cannot_invent_evidence_ids(tmp_path):
    import asyncio
    from modules.antifraud.review import analyze_reviewed
    model = _Model('{"risk":"high","reason":"编造","evidence_ids":["invented"]}')
    result = asyncio.run(analyze_reviewed(_job(tmp_path), client=model))
    assert result.assessment['status'] == 'error'
    assert result.assessment['risk'] is None
    assert all(c.id != 'model-assessment' for c in result.claims)


def test_missing_model_is_honest_partial_result(tmp_path):
    import asyncio
    from modules.antifraud.review import analyze_reviewed
    result = asyncio.run(analyze_reviewed(_job(tmp_path)))
    assert result.assessment['status'] == 'unavailable'
    assert result.status == 'partial'
    assert '模型综合判断未执行' in result.assessment['reason']


def test_model_timeout_keeps_rule_evidence(tmp_path):
    import asyncio
    from modules.antifraud.review import analyze_reviewed
    class Slow:
        async def stream(self, *args, **kwargs):
            await asyncio.sleep(5)
            yield '{}'
    result = asyncio.run(analyze_reviewed(_job(tmp_path), client=Slow(), timeout=0.01))
    assert result.assessment['status'] == 'error'
    assert result.rule_hits


def test_api_real_frame_job_metadata_and_no_missing_model_500(tmp_path, monkeypatch):
    import asyncio
    import httpx
    import app as api
    from modules.llm import LLMError
    monkeypatch.setitem(api.jobs, 'j1', _job(tmp_path))
    def missing():
        raise LLMError('no_api_key', '未配置模型')
    monkeypatch.setattr(api, 'get_llm', missing)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
            r = await client.get('/api/link-jobs/j1/antifraud')
            assert r.status_code == 200
            assert r.json()['video']['title'] == '反诈教学'
            assert r.json()['assessment']['status'] == 'unavailable'
            assert (await client.get('/api/link-jobs/missing/antifraud')).status_code == 404
    asyncio.run(run())


@pytest.mark.parametrize("segments", [[], [(0, 1, "   ")]])
def test_empty_input_cannot_claim_low_risk_or_safety(segments):
    result = analyze(transcript_segments=segments)
    assert result.claims == []
    assert result.score['level'] == 'unknown'
    assert result.score['level_label'] == '无法判断'
    assert '无法判断' in result.summary
    assert '风险等级：低' not in result.summary


def test_absolute_short_url_is_one_signal_and_one_weight():
    assert extract_urls('访问 https://t.cn/abc123') == [('url', 'https://t.cn/abc123')]
    result = analyze(transcript_segments=[(0, 4, '保本保息，访问 https://t.cn/abc123')])
    assert len(result.drainage_signals) == 1
    assert result.score['base'] == 8
    assert result.score['drainage_bonus'] == 2
    assert result.score['total'] == 10
    assert result.score['level'] == 'medium'


def test_plain_investment_narration_is_not_guided_trading():
    lib = RuleLibrary.load()
    for text in ('在交易所买入基金', '记录这笔卖出交易和建仓成本', '昨天的价格拉升后又出货'):
        assert not any(hit.rule_id == 'follow_and_trade' for hit in lib.scan_text(text, 0, 4, 'transcript'))
    assert any(hit.rule_id == 'follow_and_trade' for hit in lib.scan_text('跟我买入，老师带单指导操作', 0, 4, 'transcript'))


@pytest.mark.parametrize('text', [
    '施工现场的安全风险管理', '消防安全风险评估', '食品安全风险监测', '交通安全风险提示',
])
def test_neutral_safety_risk_material_does_not_become_a_no_risk_promise(text):
    result = analyze(transcript_segments=[(12, 18, text)])
    assert result.score['base'] == 0
    assert result.score['level'] == 'low'
    assert not any(hit['rule_id'] == 'guaranteed_high_return' for hit in result.rule_hits)
    assert not any(claim.risk == 'high' for claim in result.claims)


@pytest.mark.parametrize('text', ['本产品承诺安全无风险', '投资无风险，保证收益'])
def test_actual_no_risk_promises_remain_evidence(text):
    hits = RuleLibrary.load().scan_text(text, 2, 5, 'transcript')
    assert any(hit.rule_id == 'guaranteed_high_return' for hit in hits)


@pytest.mark.parametrize(('text', 'expected'), [
    ('https://example.com?invite=abc', 'https://example.com?invite=abc'),
    ('https://example.com#join', 'https://example.com#join'),
    ('https://example.com:8443', 'https://example.com:8443'),
    ('https://example.com:443?invite=abc#join', 'https://example.com:443?invite=abc#join'),
    ('https://example.com:8443/landing?invite=abc#join', 'https://example.com:8443/landing?invite=abc#join'),
    ('详情（https://example.com?invite=abc#join），请核实。', 'https://example.com?invite=abc#join'),
    ('“https://example.com?invite=abc”；不要转账！', 'https://example.com?invite=abc'),
    ('HTTPS://EXAMPLE.COM:443#join。', 'HTTPS://EXAMPLE.COM:443#join'),
])
def test_complete_url_evidence_survives_query_fragment_port_and_chinese_punctuation(text, expected):
    assert extract_urls(text) == [('url', expected)]
    signals = extract_from_segment(text, 9, 12, 'screentext')
    assert len(signals) == 1
    assert signals[0].value == expected
    assert signals[0].raw == expected
    assert signals[0].start == 9 and signals[0].context == text


@pytest.mark.parametrize(('text', 'expected'), [
    ('链接 example.com:8443?invite=abc#join。', ('url', 'example.com:8443?invite=abc#join')),
    ('t.cn/abc?invite=abc#join，后文', ('short_url', 't.cn/abc?invite=abc#join')),
    ('https://t.cn/abc?invite=abc#join！', ('url', 'https://t.cn/abc?invite=abc#join')),
])
def test_bare_and_short_links_share_complete_suffix_without_double_counting(text, expected):
    assert extract_urls(text) == [expected]


@pytest.mark.parametrize('text', [
    '做数据分析推荐使用开源算法', '统计分析推荐使用 pandas', '性能分析推荐使用火焰图',
])
def test_neutral_analysis_recommendations_are_not_analyst_endorsements(text):
    result = analyze(transcript_segments=[(3, 7, text)])
    assert result.score['base'] == 0
    assert not any(hit['rule_id'] == 'expert_endorsement' for hit in result.rule_hits)


@pytest.mark.parametrize('text', ['证券分析师推荐这款理财产品', '专家推荐这款保健品', '资深分析师推荐投资该产品'])
def test_complete_analyst_or_expert_endorsement_remains_a_reviewable_signal(text):
    hits = RuleLibrary.load().scan_text(text, 3, 7, 'transcript')
    assert any(hit.rule_id == 'expert_endorsement' for hit in hits)


@pytest.mark.parametrize('text', ['请主动向老师反馈', '在平台内推荐热门文章', '项目内代码审核流程'])
def test_neutral_words_do_not_form_truncated_insider_phrases(text):
    result = analyze(transcript_segments=[(4, 9, text)])
    assert result.score['base'] == 0
    assert not any(hit['rule_id'] == 'insider_info' for hit in result.rule_hits)


@pytest.mark.parametrize('text', ['内部推荐', '内部代码', '提前布局', '主力动向', '庄家洗盘'])
def test_complete_insider_phrases_remain_reviewable(text):
    assert any(hit.rule_id == 'insider_info' for hit in RuleLibrary.load().scan_text(text, 4, 9, 'transcript'))


@pytest.mark.parametrize(('rid', 'neutral', 'positive'), [
    ('guaranteed_high_return', '社保高收益测算只用于解释计算方法', ['保本高收益', '稳赚不亏']),
    ('exaggerated_return', '基金今天收高2%，记录真实行情', ['收益高达30%', '年收益30%', '年化收益30%', '年化100%']),
    ('limited_urgency', '系统出错一年后才修复', ['即将截止', '最后3个名额', '错过再等一年', '今日特惠']),
    ('expert_endorsement', '报名推荐系统课程，融资推荐算法服务', ['名师推荐', '资深推荐', '专家背书', '首席分析师']),
    ('add_wechat_for_benefit', '有人私领包裹，保安正在登记', ['加微信领资料', '进群领资料', '加好友领资料', '私聊领资料', '免费领资料加微信']),
    ('false_authority', '设计总监认可这份草图', ['政府背景', '国企背景', '银行合作', '监管认可', '权威机构认证']),
    ('health_therapy', '故宫秘方是本次历史展览的主题', ['彻底治愈', '神奇疗效', '百病不生', '提高免疫力防癌', '祖传秘方', '宫廷秘方']),
    ('target_elderly', '我爸爸买了电影票，准备周末看电影', ['中老年专享', '退休人士专享', '养老理财', '给爸妈买', '中老年必备', '老年特惠', '孝敬父母']),
])
def test_other_rules_require_complete_words_while_preserving_real_phrases(rid, neutral, positive):
    lib = RuleLibrary.load()
    assert not any(hit.rule_id == rid for hit in lib.scan_text(neutral, 0, 2, 'transcript'))
    for text in positive:
        assert any(hit.rule_id == rid for hit in lib.scan_text(text, 0, 2, 'transcript')), text


@pytest.mark.parametrize('text', ['', '   '])
def test_empty_api_report_is_consistently_unassessable_and_never_asks_model(tmp_path, monkeypatch, text):
    import asyncio
    import httpx
    import app as api
    class MustNotCall:
        called = False
        async def stream(self, *args, **kwargs):
            self.called = True
            yield '{"risk":"low","reason":"不应执行","evidence_ids":["invented"]}'
    model = MustNotCall()
    monkeypatch.setitem(api.jobs, 'empty-evidence', _job(tmp_path, text))
    monkeypatch.setattr(api, 'get_llm', lambda: model)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
            response = await client.get('/api/link-jobs/empty-evidence/antifraud')
            assert response.status_code == 200
            report = response.json()
            assert report['status'] == 'partial'
            assert report['score']['level'] == 'unknown'
            assert report['score']['level_label'] == '无法判断'
            assert report['claims'] == []
            assert report['assessment']['risk'] is None
            for value in (report['summary'], report['message'], report['assessment']['reason']):
                assert '无法判断' in value
                assert '风险等级：低' not in value
    asyncio.run(run())
    assert not model.called



def test_classical_filial_phrase_is_not_automatically_elderly_marketing():
    hits = RuleLibrary.load().scan_text('本节古文课程解释“孝父母”一语的含义', 0, 2, 'transcript')
    assert not any(hit.rule_id == 'target_elderly' for hit in hits)
