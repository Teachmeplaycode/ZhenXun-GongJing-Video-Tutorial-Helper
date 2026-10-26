"""Chapters use available evidence now and refresh when later evidence arrives."""
import asyncio

import cv2
import numpy as np
import pytest

from modules.chapters import load, save, Chapter
from modules.chapters.router import ChapterService
from modules.frames import FrameJob, cuts
from modules.screentext import ScreenText, Caption
from modules.transcript import Transcript, Segment
from modules.video_source import ResolvedVideo


@pytest.fixture
def scenario(tmp_path):
    job = FrameJob('progress', ResolvedVideo('bilibili', 'BV1', 'url', '视频', 300, []), None, tmp_path, count=2)
    job.transcript = Transcript('running')
    job.screentext = ScreenText('running')
    for slot in job.slots:
        slot.status = 'ok'
        cv2.imwrite(str(job.frame_path(slot.index)), np.zeros((90, 160, 3), dtype=np.uint8))
    cuts.save(tmp_path, 'done', [])
    pending, calls = [], []

    class Client:
        async def stream(self, messages, usage, **kwargs):
            calls.append(messages)
            yield '\n'.join(f'画面章节{i}|可见画面的内容' for i in range(8))

    service = ChapterService(lambda _: job, pending.append, Client, set(), None)
    yield job, service, pending, calls
    for coroutine in pending:
        coroutine.close()


def test_available_frames_do_not_wait_for_speech_or_ocr(scenario, monkeypatch):
    job, service, _, _ = scenario

    async def no_wait(_):
        raise AssertionError('已有帧却仍在等待语音/OCR')

    monkeypatch.setattr('modules.chapters.router.asyncio.sleep', no_wait)
    asyncio.run(service.wait_inputs(job))


def test_visual_chapters_are_visible_then_refresh_after_ocr(scenario):
    job, service, pending, calls = scenario

    async def run():
        # Bound the old implementation's indefinite speech wait.
        await asyncio.wait_for(service.build(job), timeout=0.2)
        initial = load(job.root)
        assert initial['status'] == 'done' and initial['provisional'] is True
        assert any(part['type'] == 'image_url' for part in calls[0][1]['content'])
        # OCR progress alone should not pay for another identical model request.
        job.screentext.message = '正在识别文字 40/3732'
        assert (await service.get(job.id))['chapters'] == initial['chapters']
        assert pending == []
        job.transcript.status = 'done'
        job.transcript.segments = [Segment(0, 60, '后来识别的语音')]
        job.screentext.status = 'done'
        job.screentext.segments = [Caption(200, 250, '后半段的画面文字', 'middle')]
        response = await service.get(job.id)
        assert response['chapters'] == initial['chapters']
        assert response['updating'] is True
        assert len(pending) == 1
        await pending.pop()
        final = await service.get(job.id)
        assert final['provisional'] is False and not final.get('updating')
        assert '后半段的画面文字' in str(calls[-1])
        assert len(calls) == 2 and pending == []

    asyncio.run(run())


def test_old_cached_empty_chapters_rebuild_without_disappearing(scenario):
    job, service, pending, _ = scenario
    save(job.root, 'done', [Chapter(0, 300, '第 1 章', '（这一段没有语音和画面文字）')])
    response = asyncio.run(service.get(job.id))
    assert response['chapters'][0]['title'] == '第 1 章'
    assert response.get('updating') is True
    assert len(pending) == 1


def test_new_frames_are_coalesced_but_final_inputs_refresh_immediately(scenario):
    job, service, pending, _ = scenario

    async def run():
        await asyncio.wait_for(service.build(job), timeout=0.2)
        job.add_slots([290])
        job.slots[-1].status = 'ok'
        job.frame_path(2).write_bytes(job.frame_path(0).read_bytes())
        result = await service.get(job.id)
        assert result['provisional'] is True
        assert pending == []  # do not regenerate for every arriving frame
        job.transcript.status = job.screentext.status = 'done'
        await service.get(job.id)
        assert len(pending) == 1

    asyncio.run(run())


def test_failed_visual_summary_retries_without_new_inputs_and_then_stops(scenario, monkeypatch):
    job, service, pending, _ = scenario
    job.transcript.status = job.screentext.status = 'done'
    clock = [100.0]
    monkeypatch.setattr('modules.chapters.router.time.time', lambda: clock[0])
    calls = []

    class RecoveringClient:
        async def stream(self, *args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError('temporary failure')
            yield '\n'.join(f'恢复章节{i}|画面已读取' for i in range(8))

    monkeypatch.setattr(service, 'get_client', RecoveringClient)

    async def run():
        await service.build(job)
        first = await service.get(job.id)
        assert first['status'] == 'done' and first['provisional']
        assert first['needs_retry']
        assert pending == []
        clock[0] += 31
        assert (await service.get(job.id))['updating']
        await pending.pop()
        final = await service.get(job.id)
        assert not final['provisional'] and not final.get('needs_retry')
        assert any(c['title'].startswith('恢复章节') for c in final['chapters'])
        assert len(calls) == 2

    asyncio.run(run())


def test_model_failure_does_not_erase_previous_chapters_or_retry_forever(scenario, monkeypatch):
    job, service, pending, _ = scenario
    job.transcript.status = job.screentext.status = 'done'
    clock = [100.0]
    monkeypatch.setattr('modules.chapters.router.time.time', lambda: clock[0])

    class FailingClient:
        async def stream(self, *args, **kwargs):
            raise RuntimeError('model down')
            yield ''

    async def run():
        await service.build(job)
        previous = load(job.root)['chapters']
        monkeypatch.setattr(service, 'get_client', FailingClient)
        # New OCR evidence must refresh immediately, but a failed refresh must retain the list.
        job.screentext.segments = [Caption(0, 20, '新文字', 'middle')]
        assert (await service.get(job.id))['updating']
        await pending.pop()
        preserved = load(job.root)['chapters']
        for i, chapter in enumerate(previous):
            if chapter['title'].startswith('画面章节'):
                assert preserved[i] == chapter
        assert preserved[0]['summary'] == '新文字'
        for _ in range(5):
            clock[0] += 31
            await service.get(job.id)
            if pending:
                await pending.pop()
        final = await service.get(job.id)
        assert final['needs_retry'] and not final['provisional']
        assert not final['updating'] and pending == []
        assert load(job.root)['_attempts'] == 3
        for i, chapter in enumerate(previous):
            if chapter['title'].startswith('画面章节'):
                assert final['chapters'][i] == chapter

    asyncio.run(run())


def test_unselected_new_frame_does_not_resend_the_same_model_input(scenario, monkeypatch):
    job, service, pending, calls = scenario
    events = []
    monkeypatch.setattr('modules.chapters.router.log.event', lambda name, **fields: events.append((name, fields)))
    job.video.duration = 30
    job.transcript.status = job.screentext.status = 'done'
    job.slots[0].time, job.slots[1].time = 10, 20

    async def run():
        await service.build(job)
        original = load(job.root)
        assert original['chosen_images'] == 2
        assert events[-1][0] == 'chapters'
        assert events[-1][1]['chosen_images'] == 2
        assert events[-1][1]['input_version'] == original['input_version']
        job.add_slots([1])  # farther from both representative moments than the existing frames
        job.slots[-1].status = 'ok'
        job.frame_path(2).write_bytes(job.frame_path(0).read_bytes())
        response = await service.get(job.id)
        assert not response['updating'] and not response['provisional']
        assert response['chapters'] == original['chapters']
        assert len(calls) == 1 and pending == []

    asyncio.run(run())


def test_text_outside_the_model_budget_does_not_refresh_but_used_text_does(scenario):
    job, service, pending, calls = scenario
    job.video.duration = 30
    job.transcript.status = job.screentext.status = 'done'
    job.slots[0].time, job.slots[1].time = 10, 20
    job.transcript.segments = [Segment(0, 30, '原有内容' * 60)]

    async def run():
        await service.build(job)
        job.transcript.segments[0].text += '末尾新增内容'
        assert not (await service.get(job.id))['updating']
        assert len(calls) == 1 and pending == []
        job.transcript.segments[0].text = '开头已修改' + job.transcript.segments[0].text
        assert (await service.get(job.id))['updating']
        await pending.pop()
        assert len(calls) == 2 and '开头已修改' in str(calls[-1])

    asyncio.run(run())


def test_unused_cut_changes_do_not_resend_unchanged_chapter_boundaries(scenario):
    job, service, pending, calls = scenario
    job.video.duration = 30
    job.transcript.status = job.screentext.status = 'done'
    job.slots[0].time, job.slots[1].time = 10, 20

    async def run():
        await service.build(job)
        cuts.save(job.root, 'done', [12])  # a 30-second video still has one chapter
        assert not (await service.get(job.id))['updating']
        assert len(calls) == 1 and pending == []

    asyncio.run(run())


def test_better_selected_frame_and_changed_selected_file_refresh_the_model(scenario):
    job, service, pending, calls = scenario
    job.video.duration = 30
    job.transcript.status = job.screentext.status = 'done'
    job.slots[0].time, job.slots[1].time = 10, 20
    job.transcript.segments = [Segment(0, 30, '足够的章节文字' * 20)]

    async def run():
        await service.build(job)
        assert load(job.root)['chosen_images'] == 1
        job.add_slots([15])  # now exactly at the representative midpoint
        job.slots[-1].status = 'ok'
        job.frame_path(2).write_bytes(job.frame_path(0).read_bytes())
        assert (await service.get(job.id))['updating']
        await pending.pop()
        assert len(calls) == 2 and '15.00 秒' in str(calls[-1])
        # Replacing pixels at the same timestamp must invalidate the encoded-image cache too.
        cv2.imwrite(str(job.frame_path(2)), np.ones((180, 320, 3), dtype=np.uint8) * 200)
        assert (await service.get(job.id))['updating']
        await pending.pop()
        assert len(calls) == 3 and calls[-1] != calls[-2]
        assert not (await service.get(job.id))['updating']

    asyncio.run(run())
