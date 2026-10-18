import importlib
import json

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
