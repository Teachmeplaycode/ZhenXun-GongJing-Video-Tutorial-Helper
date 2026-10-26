"""Small-print reading preserves source pixels without slowing down timeline thumbnails."""


import asyncio


import shutil


import subprocess


import cv2


import numpy as np


import pytest


from fastapi.testclient import TestClient


from modules.agent.tools import AgentTools


from modules.frames.grabber import DETAIL_WIDTH, grab_frame, GrabResult


from modules.video_source import Stream


from tests.test_replay import job_for


def write_image(path, width, height):
    cv2.imwrite(str(path), np.full((height, width, 3), 90, np.uint8))


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='needs ffmpeg')
def test_source_detail_keeps_1080p_while_preview_remains_small(tmp_path):
    video = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=1920x1080:rate=1:duration=1', '-c:v', 'libx264',
                    '-preset', 'ultrafast', str(video)], check=True)
    stream = Stream(str(video), {}, 'local')
    preview, detail = tmp_path / 'preview.jpg', tmp_path / 'detail.jpg'
    assert asyncio.run(grab_frame(stream, 0, preview)).ok
    assert asyncio.run(grab_frame(stream, 0, detail, width=DETAIL_WIDTH)).ok
    assert cv2.imread(str(preview)).shape[:2] == (360, 640)
    assert cv2.imread(str(detail)).shape[:2] == (1080, 1920)
    # Requesting 4K must never invent pixels in a 1080p source.
    assert cv2.imread(str(detail)).shape[1] < DETAIL_WIDTH


def test_detail_endpoint_caches_separately_and_retries_changed_timestamp(tmp_path, monkeypatch):
    import app
    job = job_for(tmp_path)
    job.slots[0].status = 'ok'
    write_image(job.frame_path(0), 640, 360)
    monkeypatch.setitem(app.jobs, 'job1', job)
    calls = []

    async def sharp(self, t, out, width):
        calls.append((t, width))
        write_image(out, 1920, 1080)
        return True
    monkeypatch.setattr(AgentTools, 'sharp', sharp)
    client = TestClient(app.app)
    for _ in range(2):
        response = client.get('/api/link-jobs/job1/frames/0.jpg?detail=true')
        assert response.status_code == 200
        assert response.headers['x-frame-width'] == '1920'
        assert cv2.imdecode(np.frombuffer(response.content, np.uint8), 1).shape[:2] == (1080, 1920)
    assert len(calls) == 1
    preview = client.get('/api/link-jobs/job1/frames/0.jpg')
    assert cv2.imdecode(np.frombuffer(preview.content, np.uint8), 1).shape[:2] == (360, 640)
    job.slots[0].time += 1
    assert client.get('/api/link-jobs/job1/frames/0.jpg?detail=true').status_code == 200
    assert len(calls) == 2


def test_detail_failure_does_not_break_preview(tmp_path, monkeypatch):
    import app
    job = job_for(tmp_path)
    job.slots[0].status = 'ok'
    write_image(job.frame_path(0), 640, 360)
    monkeypatch.setitem(app.jobs, 'job1', job)
    async def unavailable(*args):
        return False
    monkeypatch.setattr(AgentTools, 'sharp', unavailable)
    client = TestClient(app.app)
    assert client.get('/api/link-jobs/job1/frames/0.jpg?detail=true').status_code == 503
    assert client.get('/api/link-jobs/job1/frames/0.jpg').status_code == 200
    assert client.get('/api/link-jobs/job1/frames/999.jpg?detail=true').status_code == 404


def test_failed_hd_track_reports_the_stream_actually_read(tmp_path, monkeypatch):
    import modules.agent.tools as tools
    job = job_for(tmp_path)
    async def fake_grab(stream, t, out, **kw):
        return GrabResult(stream.label != 'hd', 'forbidden')
    monkeypatch.setattr(tools, 'grab_frame', fake_grab)
    reader = AgentTools(job)
    reader.hd = [Stream('https://hd', {}, 'hd', 1080)]
    assert asyncio.run(reader.sharp(10, tmp_path / 'out.jpg', DETAIL_WIDTH))
    assert job.video.extra['read_height'] == 720
