"""Binding Bilibili must immediately leave a previously cached low-resolution detail frame."""
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from modules.agent.tools import AgentTools
from tests.test_replay import job_for


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    import app
    from modules import settings as config

    job = job_for(tmp_path)
    job.slots[0].status = 'ok'
    cv2.imwrite(str(job.frame_path(0)), np.zeros((360, 640, 3), np.uint8))
    binding = {'cookie': ''}
    calls = []
    monkeypatch.setattr(app, 'get_job', lambda _: job)
    monkeypatch.setattr(app.visitors, 'enabled', lambda: False)
    monkeypatch.setattr(config, 'settings', lambda: {'BILIBILI_COOKIE': binding['cookie']})

    async def sharp(self, timestamp, target, width):
        calls.append(target)
        w, h = (1920, 1080) if binding['cookie'] else (640, 360)
        cv2.imwrite(str(target), np.zeros((h, w, 3), np.uint8))
        return True

    monkeypatch.setattr(AgentTools, 'sharp', sharp)
    return TestClient(app.app), job, binding, calls


def test_binding_immediately_replaces_fresh_low_detail_without_changing_preview(scenario):
    client, job, binding, calls = scenario
    endpoint = '/api/link-jobs/job1/frames/0.jpg'
    preview = client.get(endpoint).content
    assert client.get(endpoint + '?detail=true').headers['x-frame-width'] == '640'
    assert client.get(endpoint + '?detail=true').headers['x-frame-width'] == '640'
    assert len(calls) == 1

    binding['cookie'] = 'SESSDATA=synthetic-bound-account'
    assert client.get(endpoint + '?detail=true').headers['x-frame-width'] == '1920'
    assert len(calls) == 2  # no 60-second wait after binding
    assert client.get(endpoint + '?detail=true').headers['x-frame-width'] == '1920'
    assert len(calls) == 2
    assert client.get(endpoint).content == preview == job.frame_path(0).read_bytes()
    cached = list((job.root / 'detail').glob('*.jpg'))
    assert len(cached) == 2
    assert all(binding['cookie'] not in path.name and 'SESSDATA' not in path.name for path in cached)


def test_different_bindings_use_distinct_caches_and_reuse_the_same_binding(scenario):
    client, _, binding, calls = scenario
    endpoint = '/api/link-jobs/job1/frames/0.jpg?detail=true'
    binding['cookie'] = 'SESSDATA=synthetic-account-a'
    assert client.get(endpoint).headers['x-frame-width'] == '1920'
    first = calls[-1]
    binding['cookie'] = 'SESSDATA=synthetic-account-b'
    assert client.get(endpoint).headers['x-frame-width'] == '1920'
    assert len(calls) == 2 and calls[-1] != first
    binding['cookie'] = ''
    assert client.get(endpoint).headers['x-frame-width'] == '640'
    assert len(calls) == 3
    binding['cookie'] = 'SESSDATA=synthetic-account-a'
    assert client.get(endpoint).headers['x-frame-width'] == '1920'
    assert len(calls) == 3


def test_bilibili_binding_does_not_invalidate_other_platform_detail(scenario):
    client, job, binding, calls = scenario
    job.video.platform = 'local'
    endpoint = '/api/link-jobs/job1/frames/0.jpg?detail=true'
    assert client.get(endpoint).status_code == 200
    binding['cookie'] = 'SESSDATA=synthetic-bound-account'
    assert client.get(endpoint).status_code == 200
    assert len(calls) == 1
