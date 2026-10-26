"""Available evidence reaches notes and chat before background OCR finishes."""
import asyncio
from pathlib import Path
import threading

import pytest

from modules.notes.router import NotesService
from modules.notes.task import load
from modules.screentext.task import run_screentext
from modules.screentext.ocr import Line
from modules.frames.grabber import GrabResult
from tests.test_screentext import make_job


def test_notes_use_ready_text_without_waiting_for_ocr_or_chapters(tmp_path, monkeypatch):
    job = make_job(tmp_path)
    job.screentext.status = 'running'
    service = NotesService(None, None, None, chapters_busy=lambda _: True)
    async def no_wait(_):
        raise AssertionError('usable text must not wait for OCR or chapter completion')
    monkeypatch.setattr('modules.notes.router.asyncio.sleep', no_wait)
    assert asyncio.run(service._inputs_ready(job)) is None


def test_notes_wait_for_first_evidence_is_bounded(tmp_path, monkeypatch):
    job = make_job(tmp_path)
    job.transcript.segments = []
    job.transcript.status = 'running'
    job.screentext.status = 'running'
    service = NotesService(None, None, None)
    waits = []
    async def tick(seconds):
        waits.append(seconds)
        assert sum(waits) <= 8, 'empty input must not make a note wait indefinitely'
    monkeypatch.setattr('modules.notes.router.asyncio.sleep', tick)
    assert asyncio.run(service._inputs_ready(job)) is None
    assert sum(waits) == 8


def test_ocr_publishes_first_batch_before_recognizing_the_next(tmp_path):
    job = make_job(tmp_path, duration=81)
    published = []
    event_thread = threading.get_ident()
    original_emit = job.emit
    def emit(event):
        assert threading.get_ident() == event_thread, 'OCR must publish on the event loop thread'
        original_emit(event)
    job.emit = emit
    async def read(stream, folder, timeout):
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, 82):
            (folder / f'{i:05d}.jpg').write_bytes(b'jpg')
        return GrabResult(True)
    def recognize(path):
        index = int(Path(path).stem)
        if index == 41:
            assert job.screentext.status == 'running'
            assert job.screentext.segments, 'first OCR batch is unavailable until the entire video finishes'
            assert max(s.end for s in job.screentext.segments) <= 40
            published.append((job.screentext.segments, [s.as_dict() for s in job.screentext.segments]))
        return [Line(f'课程知识点{index}', 1.0, (index % 8) / 10, .85, .1, .05)]
    asyncio.run(run_screentext(job, read=read, recognize=recognize))
    assert job.screentext.status == 'done', job.screentext.message
    assert max(s.end for s in job.screentext.segments) == 81
    earlier, values = published[0]
    assert job.screentext.segments is not earlier
    assert [s.as_dict() for s in earlier] == values, 'later OCR batches must not mutate a note/chat snapshot'


@pytest.mark.parametrize('ready_after', [0, 2, 8])
def test_notes_build_from_frames_without_text_and_show_partial_scope(tmp_path, monkeypatch, ready_after):
    job = make_job(tmp_path)
    job.transcript.segments = []
    job.transcript.status = 'running'
    job.screentext.status = 'running'
    waits = []
    seen = []

    def ready_frame():
        job.frame_path(0).write_bytes(b'jpg')
        job.slots[0].status = 'ok'

    async def tick(seconds):
        waits.append(seconds)
        if sum(waits) == ready_after:
            ready_frame()
        assert sum(waits) <= ready_after, 'notes waited past the first usable frame'

    async def build_note(**inputs):
        assert not inputs['transcript'] and not inputs['screen']
        pictures = inputs['pictures'](0, job.video.duration)
        assert [path for _, path in pictures] == [job.frame_path(0)]
        seen.append(pictures)
        return {'sections': [], 'summary': '已有画面摘要'}

    if ready_after == 0:
        ready_frame()
    monkeypatch.setattr('modules.notes.router.asyncio.sleep', tick)
    monkeypatch.setattr('modules.notes.router.build_note', build_note)
    service = NotesService(None, None, lambda: object(), chapters_busy=lambda _: True)
    asyncio.run(service.build(job))

    record = load(job.root)
    assert record['status'] == 'done', record
    assert seen and sum(waits) == ready_after
    assert record['note']['summary'].startswith(record['note']['coverage_note'])
    assert '语音、画面文字、画面尚未完成' in record['note']['summary']
    assert record['note']['summary'].endswith('已有画面摘要')
    assert '部分内容仍在处理' in record['message']


def test_notes_with_no_material_stop_after_eight_seconds_without_model_calls(tmp_path, monkeypatch):
    job = make_job(tmp_path)
    job.transcript.segments = []
    job.transcript.status = 'running'
    job.screentext.status = 'running'
    waits = []

    async def tick(seconds):
        waits.append(seconds)
        assert sum(waits) <= 8

    async def must_not_build(**inputs):
        raise AssertionError('an empty import must not start model generation')

    monkeypatch.setattr('modules.notes.router.asyncio.sleep', tick)
    monkeypatch.setattr('modules.notes.router.build_note', must_not_build)
    service = NotesService(None, None, lambda: object())
    asyncio.run(service.build(job))
    record = load(job.root)
    assert sum(waits) == 8
    assert record['status'] == 'failed'
    assert '尚未取得可用画面或文字' in record['message']


def test_notes_with_finished_empty_sources_do_not_wait(tmp_path, monkeypatch):
    job = make_job(tmp_path)
    job.transcript.segments = []
    job.transcript.status = 'unavailable'
    job.screentext.status = 'empty'
    for slot in job.slots:
        slot.status = 'missing'

    async def no_wait(_):
        raise AssertionError('no unfinished source remains to wait for')

    monkeypatch.setattr('modules.notes.router.asyncio.sleep', no_wait)
    service = NotesService(None, None, lambda: object())
    asyncio.run(service.build(job))
    record = load(job.root)
    assert record['status'] == 'failed'
    assert '尚未取得可用画面或文字' in record['message']
