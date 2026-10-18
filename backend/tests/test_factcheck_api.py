import importlib
import json
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from modules.frames import FrameJob
from modules.video_source import ResolvedVideo
from modules.factcheck import api as factcheck_api


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('GONGJING_DATA_DIR', str(tmp_path))
    import app
    module = importlib.reload(app)
    job = FrameJob('factcheck-job', ResolvedVideo('local', 'v', 'local://v', 'video', 60, []), None, tmp_path / 'frames')
    module.jobs[job.id] = job
    module.store.create(job, 'test')
    monkeypatch.setattr(module, 'get_llm', lambda: object())
    with TestClient(module.app) as client:
        yield client, job


def events(response):
    return [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]


def test_completed_report_is_persisted_and_can_be_reloaded(api, monkeypatch):
    client, job = api
    report = {'version': 1, 'module': 'factcheck', 'job_id': job.id, 'claims': [], 'status': 'done', 'summary': {'total': 0}}
    async def completed(*args, **kwargs):
        yield {'type': 'factcheck.started', 'run_id': 'mock'}
        yield {'type': 'factcheck.completed', 'run_id': 'mock', 'report': report}
    monkeypatch.setattr(factcheck_api, 'run_factcheck', completed)
    assert client.get(f'/api/link-jobs/{job.id}/factcheck').status_code == 404
    response = client.post(f'/api/link-jobs/{job.id}/factcheck', json={})
    assert response.status_code == 200
    assert events(response)[-1]['report'] == report
    assert client.get(f'/api/link-jobs/{job.id}/factcheck').json() == report
    assert client.get('/api/sessions').status_code == 200


def test_unknown_job_returns_actionable_stream_error(api):
    client, _ = api
    response = client.post('/api/link-jobs/missing/factcheck', json={})
    assert events(response)[0]['code'] == 'job_not_found'
    assert client.get('/api/link-jobs/missing/factcheck').status_code == 404


def test_missing_transcript_is_reported_without_persisting_empty_success(api):
    client, job = api
    result = events(client.post(f'/api/link-jobs/{job.id}/factcheck', json={}))
    assert result[-1]['type'] == 'factcheck.error'
    assert result[-1]['code'] == 'no_content'
    assert client.get(f'/api/link-jobs/{job.id}/factcheck').status_code == 404


@pytest.mark.parametrize('channel', ['transcript', 'screentext'])
@pytest.mark.parametrize('status', ['pending', 'running'])
def test_incomplete_channel_does_not_persist_a_partial_report(api, channel, status):
    from modules.transcript import Transcript
    from modules.transcript.asr import Segment
    from modules.screentext import ScreenText
    from modules.screentext.merge import Caption

    client, job = api
    job.transcript = Transcript('done', '', [Segment(1, 2, '苹果含维生素C')])
    job.screentext = ScreenText('done', '', [Caption(3, 4, '苹果能治癌', 'bottom')])
    getattr(job, channel).status = status
    result = events(client.post(f'/api/link-jobs/{job.id}/factcheck', json={}))
    assert result[-1]['type'] == 'factcheck.error'
    assert result[-1]['code'] == 'content_not_ready' and result[-1]['retryable'] is True
    assert not any(event['type'] == 'factcheck.completed' for event in result)
    assert client.get(f'/api/link-jobs/{job.id}/factcheck').status_code == 404


def test_report_is_saved_before_completed_is_delivered_even_when_stream_closes(monkeypatch):
    saved = []
    report = {'version': 1, 'module': 'factcheck', 'summary': {'total': 0}, 'claims': []}

    async def completed(*args, **kwargs):
        yield {'type': 'factcheck.completed', 'report': report}

    monkeypatch.setattr(factcheck_api, 'run_factcheck', completed)
    store = SimpleNamespace(add_message=lambda *args, **kwargs: saved.append(kwargs['data']['factcheck']))
    router = factcheck_api.create_router(find_job=lambda _: SimpleNamespace(id='job'), get_llm=lambda: object(), store=store)

    async def consume_one_event():
        response = await router.routes[0].endpoint('job', factcheck_api.FactCheckRequest())
        event = json.loads((await anext(response.body_iterator))[5:])
        assert event['type'] == 'factcheck.completed'
        assert saved == [report]
        # A browser can close as soon as it sees completed. No next iteration may be required to save.
        await response.body_iterator.aclose()

    asyncio.run(consume_one_event())


def test_save_failure_sends_error_instead_of_completed(api, monkeypatch):
    client, job = api

    async def completed(*args, **kwargs):
        yield {'type': 'factcheck.completed', 'report': {'summary': {'total': 0}, 'claims': []}}

    def fail_save(*args, **kwargs):
        raise OSError('disk unavailable')

    monkeypatch.setattr(factcheck_api, 'run_factcheck', completed)
    import app
    monkeypatch.setattr(app.store, 'add_message', fail_save)
    result = events(client.post(f'/api/link-jobs/{job.id}/factcheck', json={}))
    assert [event['type'] for event in result] == ['factcheck.error']
    assert client.get(f'/api/link-jobs/{job.id}/factcheck').status_code == 404
