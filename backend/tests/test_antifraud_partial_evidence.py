"""Partial evidence must not become reassurance; actual QR provenance stays private."""
import asyncio
import json

import pytest

from modules.antifraud.pipeline import analyze_job
from modules.antifraud.qrcode import decode_qrcodes
from modules.antifraud.review import analyze_reviewed
from test_antifraud import _job, _Model


STAGES = [(source, state) for source in ('transcript', 'screentext')
          for state in ('pending', 'running', 'failed', 'unavailable')]
STAGES += [('frames', 'running'), ('frames', 'failed'), ('frames', 'missing_file')]


def unfinished(job, source, state):
    if source == 'frames':
        job.running = state == 'running'
        if state == 'missing_file':
            job.frame_path(0).unlink()
        else:
            job.slots[0].status = 'pending' if state == 'running' else 'missing'
    else:
        getattr(job, source).status = state


@pytest.mark.parametrize(('source', 'state'), STAGES)
@pytest.mark.parametrize('has_risk', [False, True])
def test_partial_sources_do_not_offer_safety_or_erase_risk(tmp_path, source, state, has_risk):
    text = '保本保息，内部消息，加微信 abc12345' if has_risk else '今天讨论公园里的花草'
    job = _job(tmp_path, text)
    unfinished(job, source, state)
    # Even a model proposing low risk cannot assure safety from incomplete inputs.
    model = _Model('{"risk":"low","reason":"这里看起来很安全","evidence_ids":["segment-transcript-0"]}')
    report = asyncio.run(analyze_reviewed(job, client=model))
    assert report.status == 'partial'
    assert not any(claim.verdict == 'safe' for claim in report.claims)
    assert '风险等级：低' not in report.summary
    assert '看起来很安全' not in report.assessment['reason']
    if has_risk:
        assert report.score['level'] == report.assessment['risk'] == 'high'
        assert report.score['total'] >= 12
        assert '高风险线索' in report.summary
        assert '高风险线索' in report.assessment['reason']
        assert any(claim.risk == 'high' for claim in report.claims)
        assert report.rule_hits
    else:
        assert report.score['level'] == 'unknown'
        assert report.assessment['risk'] is None
        assert '无法判断' in report.summary
        assert '无法判断' in report.assessment['reason']
        assert report.claims == []


def test_partial_sources_keep_model_discovered_risk_above_low_rule_score(tmp_path):
    job = _job(tmp_path, '请把钱汇到视频中的账户')
    job.transcript.status = 'running'
    model = _Model('{"risk":"high","reason":"当前片段要求向未知账户转账，请核实","evidence_ids":["segment-transcript-0"]}')
    report = asyncio.run(analyze_reviewed(job, client=model))
    assert report.score['total'] == 0
    assert report.score['level'] == report.assessment['risk'] == 'high'
    assert report.claims[0].id == 'model-assessment'
    assert report.claims[0].risk == 'high'


@pytest.mark.parametrize('has_risk', [False, True])
def test_partial_api_remains_consistent_without_a_model(tmp_path, monkeypatch, has_risk):
    import app as api
    import httpx
    job = _job(tmp_path, '保本保息，内部消息' if has_risk else '讨论植物生长')
    job.screentext.status = 'failed'
    monkeypatch.setitem(api.jobs, 'partial-evidence', job)
    monkeypatch.setattr(api, 'get_llm', lambda: None)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
            result = (await client.get('/api/link-jobs/partial-evidence/antifraud')).json()
            assert result['status'] == 'partial'
            assert not any(c['verdict'] == 'safe' for c in result['claims'])
            assert result['score']['level'] == ('high' if has_risk else 'unknown')
            assert result['assessment']['risk'] == ('high' if has_risk else None)
            assert ('高风险线索' if has_risk else '无法判断') in result['summary']
    asyncio.run(run())


def test_real_qr_report_and_api_expose_frame_reference_not_server_path(tmp_path, monkeypatch):
    import app as api
    import cv2
    import httpx
    import segno
    installation = tmp_path / 'private-server-installation' / 'jobs'
    job = _job(installation, '这是公开资料的链接')
    png = installation / 'encoded.png'
    payload = 'https://example.com?invite=qr-safe-evidence'
    segno.make(payload, micro=False).save(png, scale=8, border=4)
    path = job.frame_path(0)
    cv2.imwrite(str(path), cv2.imread(str(png)))
    hits = decode_qrcodes([(0, job.slots[0].time, path)])
    assert len(hits) == 1 and hits[0].content == payload
    assert hits[0].source_path == str(path)  # still usable internally
    serialized = analyze_job(job).as_dict()
    assert serialized['qrcodes'][0]['frame_index'] == 0
    assert serialized['qrcodes'][0]['content'] == payload
    assert 'source_path' not in json.dumps(serialized)
    assert str(installation) not in json.dumps(serialized)
    monkeypatch.setitem(api.jobs, 'qr-private-path', job)
    monkeypatch.setattr(api, 'get_llm', lambda: None)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
            response = await client.get('/api/link-jobs/qr-private-path/antifraud')
            assert response.status_code == 200
            result = response.json()
            assert result['qrcodes'][0]['frame_index'] == 0
            assert result['qrcodes'][0]['content'] == payload
            assert 'source_path' not in response.text
            assert str(installation) not in response.text
    asyncio.run(run())


@pytest.mark.parametrize(('text', 'level'), [('专家推荐这款产品', 'medium'), ('内部消息', 'high')])
def test_partial_sources_preserve_individual_risk_clues_below_total_threshold(tmp_path, text, level):
    job = _job(tmp_path, text)
    job.transcript.status = 'failed'
    report = asyncio.run(analyze_reviewed(job))
    assert report.score['level'] == report.assessment['risk'] == level
    assert any(claim.risk == level for claim in report.claims)
    assert report.score['total'] == (5 if level == 'medium' else 7)
