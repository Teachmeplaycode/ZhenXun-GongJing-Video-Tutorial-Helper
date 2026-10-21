"""On-screen text is read one video at a time; the others wait and are told where they stand."""
import asyncio

from modules.frames import FrameJob
from modules.screentext import ScreenText
from modules.store import SessionStore
from modules.transcript import Transcript
from modules.video_source import ResolvedVideo


def test_videos_wait_their_turn_for_ocr(tmp_path, monkeypatch):
    import app

    monkeypatch.setattr(app, "store", SessionStore(tmp_path / "db.sqlite3"))
    monkeypatch.setattr(app, "ocr_slots", None)
    monkeypatch.setattr(app, "ocr_queue", [])
    running, order, events = set(), [], {}
    gates = {}

    async def fake_ocr(job):
        running.add(job.id)
        assert len(running) == 1  # never two at once
        order.append(job.id)
        await gates[job.id].wait()
        job.screentext.status = "done"
        running.discard(job.id)

    monkeypatch.setattr(app, "run_screentext", fake_ocr)

    def make(job_id):
        video = ResolvedVideo("bilibili", job_id, "u", "t", 60.0, [])
        job = FrameJob(job_id, video, None, tmp_path / job_id, count=1)
        job.transcript, job.screentext = Transcript(), ScreenText()
        events[job_id] = []
        job.emit = events[job_id].append
        monkeypatch.setitem(app.jobs, job_id, job)
        app.store.create(job, "u")
        gates[job_id] = asyncio.Event()
        return job

    async def go():
        a, b, c = make("a"), make("b"), make("c")
        tasks = [asyncio.create_task(app.read_screen(j)) for j in (a, b, c)]
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert app.ocr_queue == ["b", "c"]
        assert "前面还有 2 个" in c.screentext.message
        gates["a"].set()
        await asyncio.sleep(0.01)
        assert app.ocr_queue == ["c"] and "前面还有 1 个" in c.screentext.message
        gates["b"].set()
        gates["c"].set()
        await asyncio.gather(*tasks)

    asyncio.run(go())
    assert order == ["a", "b", "c"] and app.ocr_queue == []
    assert any(e.get("queued") == 2 for e in events["c"])
