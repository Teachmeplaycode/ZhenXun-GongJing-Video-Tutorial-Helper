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


def test_chapters_wait_for_pending_inputs_and_cuts(api, monkeypatch):
    app, job, _ = api
    real_sleep = asyncio.sleep
    job.transcript.status = "pending"
    app.cutting.add(job.id)
    waits = []

    async def finish_inputs(_):
        waits.append(True)
        job.transcript.status = "done"
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
