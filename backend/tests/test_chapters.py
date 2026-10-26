"""Chapter splitting and titled table-of-contents generation."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from modules.chapters import Chapter, Chapters, load, run_chapters, save, split
from modules.transcript import Segment


def test_segment_returns_empty_for_zero_duration():
    assert split.segment(0) == []
    assert split.segment(-10) == []


def test_segment_covers_the_whole_timeline():
    spans = split.segment(600)
    assert spans[0][0] == 0.0 and spans[-1][1] == 600.0
    for (a, b), (c, d) in zip(spans, spans[1:]):
        assert abs(b - c) < 1e-6


def test_long_video_produces_5_to_15_chapters():
    for minutes in (30, 45, 60, 90):
        spans = split.segment(minutes * 60)
        assert 5 <= len(spans) <= 15, f"{minutes}min -> {len(spans)} chapters"


def test_splits_snap_to_shot_changes_within_the_window():
    spans = split.segment(360, cuts=[120, 240])
    boundaries = [b for _a, b in spans[:-1]]
    assert 120 in boundaries and 240 in boundaries


def test_too_short_chapters_merge():
    spans = split.segment(100, cuts=[10, 20, 30, 40, 50, 60, 70, 80])
    for a, b in spans:
        assert b - a >= split.MIN_SPAN or len(spans) == 1


def test_pauses_detect_silence_gaps():
    transcript = [(0, 10, "a"), (15, 20, "b"), (40, 50, "c")]
    p = split.pauses(transcript)
    assert 10 in p and 20 in p


def test_candidate_bounds_dedupes_and_sorts():
    bounds = split.candidate_bounds(cuts=[200.0, 100.0, 100.0], transcript=(), duration=300)
    assert bounds == [100.0, 200.0]


def test_run_chapters_splits_titles_and_caches(tmp_path):
    transcript = [(i * 60, i * 60 + 55, f"第{i + 1}段内容") for i in range(8)]

    async def complete(messages):
        return "\n".join(f"标题{i + 1}|摘要{i + 1}" for i in range(8))

    record = asyncio.run(run_chapters(tmp_path, transcript, [], {"cuts": []}, 480, complete=complete))
    assert record["status"] == "done" and len(record["chapters"]) >= 5
    assert load(tmp_path) == record
    assert record["chapters"][0]["title"] == "标题1"


def test_run_chapters_falls_back_when_the_model_fails(tmp_path):
    transcript = [(0, 50, "今天讲讲机器学习的基础")]

    async def complete(messages):
        raise RuntimeError("model down")

    record = asyncio.run(run_chapters(tmp_path, transcript, [], None, 300, complete=complete))
    assert record["status"] == "done" and record["chapters"]
    assert record["chapters"][0]["title"]


def test_run_chapters_without_a_model_uses_text_titles(tmp_path):
    transcript = [(0, 40, "开篇介绍"), (40, 80, "正片开始")]
    record = asyncio.run(run_chapters(tmp_path, transcript, [], None, 80))
    assert record["status"] == "done"
    assert all(c["title"] for c in record["chapters"])


def test_run_chapters_empty_when_duration_unknown(tmp_path):
    record = asyncio.run(run_chapters(tmp_path, [], [], None, 0))
    assert record["status"] == "empty" and record["chapters"] == []


def test_save_and_load_roundtrip(tmp_path):
    ch = [Chapter(0, 60, "开头", "介绍"), Chapter(60, 120, "正文", "讲解")]
    record = save(tmp_path, "done", ch, "已生成 2 个章节")
    assert load(tmp_path) == record
    assert record["chapters"][0] == {"start": 0.0, "end": 60.0, "title": "开头", "summary": "介绍"}


def test_chapters_dataclass():
    c = Chapters("done", "ok", [Chapter(0, 10, "a", "b")])
    assert c.summary() == {"status": "done", "message": "ok", "count": 1}
    assert c.as_dict()["chapters"][0]["title"] == "a"
    assert Chapters("running").running is True
    assert Chapters("done").running is False


@pytest.fixture
def api(tmp_path, monkeypatch):
    import app
    from modules.frames import FrameJob
    from modules.screentext import ScreenText
    from modules.store import SessionStore
    from modules.transcript import Transcript
    from modules.video_source import ResolvedVideo, Stream

    video = ResolvedVideo("bilibili", "BV1", "u", "t", 300.0, [Stream("https://a/720", {}, "s", 720)])
    job = FrameJob("job1", video, None, tmp_path / "jobs" / "job1", count=2)
    job.transcript = Transcript("done", "已转写", [Segment(0, 50, "开头"), Segment(50, 100, "正文")])
    job.screentext = ScreenText("done", "已识别", [])
    store = SessionStore(tmp_path / "db.sqlite3")
    store.create(job, "https://www.bilibili.com/video/BV1")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "store", store)
    monkeypatch.setitem(app.jobs, "job1", job)
    app.chapter_service.running.clear()
    app.chapter_service.deleted.clear()
    app.cutting.clear()
    from modules.frames import cuts
    cuts.save(job.root, "done", [])
    return app, job, store


def test_chapters_endpoint_serves_cache_and_starts_generation_once(api, monkeypatch):
    app, job, _ = api
    started = []

    async def fake(job):
        started.append(job.id)

    monkeypatch.setattr(app.chapter_service, "build", fake)
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/chapters").json()["status"] == "running"
    assert started == ["job1"]
    save(job.root, "done", [Chapter(0, 150, "上半", "介绍"), Chapter(150, 300, "下半", "讲解")])
    body = client.get("/api/link-jobs/job1/chapters").json()
    assert body["status"] == "done" and len(body["chapters"]) == 2


def test_app_generates_chapters_from_real_job_states(api, monkeypatch):
    app, job, _ = api
    from modules.llm import LLMError

    def unavailable():
        raise LLMError("unavailable", "test has no model")

    monkeypatch.setattr(app, "get_llm", unavailable)
    asyncio.run(app.chapter_service.build(job))
    record = load(job.root)
    assert record["status"] == "done"
    assert record["chapters"][0]["title"].startswith("开头")
    assert job.id not in app.chapter_service.running


def test_chapters_wait_only_until_the_first_input_arrives(api, monkeypatch):
    app, job, _ = api
    real_sleep = asyncio.sleep
    job.transcript.status = "pending"
    job.transcript.segments = []
    app.cutting.add(job.id)
    waits = []

    async def finish_inputs(_):
        waits.append(True)
        job.transcript.status = "done"
        job.transcript.segments = [Segment(0, 20, '首段文字')]
        app.cutting.discard(job.id)
        await real_sleep(0)

    monkeypatch.setattr(app.asyncio, "sleep", finish_inputs)
    asyncio.run(app.chapter_service.wait_inputs(job))
    assert waits == [True]


def test_chapter_input_timeout_does_not_generate_incomplete_cache(api):
    app, job, _ = api
    job.transcript.status = "running"
    with pytest.raises(TimeoutError):
        asyncio.run(app.chapter_service.wait_inputs(job, timeout=0))
    assert load(job.root) is None


def test_overview_is_cached_separately_from_chapter_titles(tmp_path):
    async def complete(messages):
        return "章节标题|本章摘要\n总摘要|整段视频介绍科学原理及应用。"

    record = asyncio.run(run_chapters(tmp_path, [(0, 50, "科学原理")], [], None, 50, complete=complete))
    assert record["summary"] == "整段视频介绍科学原理及应用。"
    assert record["chapters"][0]["title"] == "章节标题"
    assert load(tmp_path)["summary"] == record["summary"]


def test_duplicate_chapter_requests_only_schedule_one_build(api, monkeypatch):
    app, job, _ = api
    pending = []
    monkeypatch.setattr(app.chapter_service, "spawn", pending.append)
    app.chapter_service.start(job)
    app.chapter_service.start(job)
    assert len(pending) == 1
    pending[0].close()
    app.chapter_service.running.clear()


def test_ocr_boundaries_use_real_caption_gaps():
    from modules.screentext import Caption
    captions = [Caption(0, 5, '开场', 'middle'), Caption(12, 16, '第二章', 'middle'),
                Caption(16, 20, '继续介绍', 'bottom'), Caption(30, 35, '第三章', 'top')]
    assert split.pauses(screen=captions) == [0, 12, 30]


def test_first_boundary_cannot_create_a_short_chapter():
    assert split.segment(60, cuts=[15]) == [(0.0, 60)]


def test_touching_segments_do_not_leak_into_adjacent_prompts():
    from modules.chapters.task import _chapter_text
    rows = [(0, 30, '前一章'), (30, 60, '当前章'), (60, 90, '后一章'), (29, 31, '跨界')]
    assert _chapter_text(rows, [], 30, 60) == '当前章 跨界'


def test_inputs_can_run_longer_than_ten_minutes(api, monkeypatch):
    app, job, _ = api
    from modules.chapters import router
    job.transcript.status = 'running'
    job.transcript.segments = []
    ticks = iter([0, 700, 1400, 2100])
    monkeypatch.setattr(router.time, 'monotonic', lambda: next(ticks, 9999))
    waits = []

    async def finish(_):
        waits.append(True)
        job.transcript.status = 'done'
        job.transcript.segments = [Segment(0, 20, '迟到的首段文字')]

    monkeypatch.setattr(router.asyncio, 'sleep', finish)
    asyncio.run(app.chapter_service.wait_inputs(job))
    assert waits == [True]


def test_retry_discards_cached_and_inflight_old_chapters(api, monkeypatch):
    app, job, _ = api
    service = app.chapter_service
    calls = []
    save(job.root, 'done', [Chapter(0, 300, '旧标题', '旧摘要')])
    pending = []
    monkeypatch.setattr(service, 'spawn', pending.append)

    class Client:
        async def stream(self, messages, usage, **kwargs):
            calls.append(messages)
            if len(calls) == 1:
                job.transcript.segments = [Segment(0, 100, '重试后的文字')]
                service.invalidate(job)
                assert load(job.root) is None
                yield '过时标题|过时摘要'
            else:
                yield '新标题|新摘要'

    monkeypatch.setattr(service, 'get_client', Client)
    service.invalidate(job)
    assert load(job.root) is None
    assert len(pending) == 1
    asyncio.run(pending[0])
    assert len(calls) == 2
    assert len(pending) == 1
    assert '重试后的文字' in calls[1][1]['content']
    assert load(job.root)['chapters'][0]['title'] == '新标题'


def test_deleted_session_cancels_builder_without_recreating_files(api, monkeypatch):
    import shutil
    app, job, _ = api
    service = app.chapter_service

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        class Client:
            async def stream(self, *args, **kwargs):
                started.set()
                await release.wait()
                yield '标题|摘要'

        monkeypatch.setattr(service, 'get_client', Client)
        task = asyncio.create_task(service.build(job))
        await started.wait()
        service.remove(job.id)
        shutil.rmtree(job.root)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not job.root.exists()
        assert job.id not in service.running

    asyncio.run(scenario())


def test_restored_session_runs_missing_cut_detection_before_build(api, monkeypatch):
    from modules.frames import cuts
    app, job, _ = api
    (job.root / cuts.FILE).unlink()
    called = []

    async def ensure(job):
        called.append(job.id)
        cuts.save(job.root, 'done', [100, 200])

    from modules.llm import LLMError
    def no_client():
        raise LLMError('unavailable', 'test')

    monkeypatch.setattr(app.chapter_service, 'get_client', no_client)
    monkeypatch.setattr(app.chapter_service, 'ensure_cuts', ensure)
    asyncio.run(app.chapter_service.build(job))
    assert called == [job.id]
    assert load(job.root)['status'] == 'done'
    assert 100 in {c['end'] for c in load(job.root)['chapters']}


def test_available_speech_does_not_wait_for_screen_text_and_cuts(api, monkeypatch):
    app, job, _ = api
    job.transcript.status = "done"
    job.screentext.status = "running"   # OCR still queued on the server
    app.cutting.add(job.id)              # the cut pass still reading the video
    clock = [0.0]
    monkeypatch.setattr("modules.chapters.router.time.monotonic", lambda: clock[0])

    async def tick(_):
        clock[0] += 2

    monkeypatch.setattr(app.asyncio, "sleep", tick)
    asyncio.run(app.chapter_service.wait_inputs(job))
    assert clock[0] == 0  # existing evidence is enough; late OCR/cuts refresh the result
    app.cutting.discard(job.id)
