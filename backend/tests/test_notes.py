"""Study notes: sections from chapters, one model call each, figures inside their section, the mind map,
the Markdown export (in the editor's order) and the HTTP routes."""
import asyncio
import io
import json
import zipfile

from fastapi.testclient import TestClient

from modules.frames import FrameJob
from modules.notes import export
from modules.notes.task import build_note, parse_json, section_from, spans, stretch_text
from modules.store import SessionStore
from modules.video_source import ResolvedVideo, Stream

TRANSCRIPT = [(10, 20, "今天讲数列极限的定义"), (130, 140, "看例题七"), (400, 410, "夹逼准则")]
SCREEN = [(15, 25, "ε-N 定义"), (135, 150, "a_n = 1/n")]
CHAPTERS = [{"start": 0, "end": 120, "title": "定义"}, {"start": 120, "end": 300, "title": "例题"},
            {"start": 300, "end": 600, "title": "夹逼"}]


def test_sections_follow_chapters_else_even_stretches():
    assert [s[:2] for s in spans(600, CHAPTERS)] == [(0, 120), (120, 300), (300, 600)]
    assert len(spans(1200, None)) == 4 and spans(1200, None)[-1][1] == 1200  # ~5 minutes each
    assert spans(0, None) == []


def test_stretch_text_keeps_the_section_and_its_times():
    speech, shown = stretch_text(TRANSCRIPT, SCREEN, 120, 300)
    assert speech == "[02:10] 看例题七" and shown == "[02:15] a_n = 1/n"


def test_parse_json_tolerates_fences_and_chatter():
    assert parse_json('好的：\n```json\n{"title": "定义"}\n```') == {"title": "定义"}
    assert parse_json("没有 JSON") is None


def test_figures_outside_their_section_are_dropped():
    s = section_from({"title": "例题", "points": ["a", "a", "b"], "figures": [
        {"time": 130, "caption": "例题七板书"}, {"time": 500, "caption": "别的节"}, {"time": "x"}]}, "s2", 120, 300, "")
    assert [f.time for f in s.figures] == [130] and s.points == ["a", "b"]
    assert section_from(None, "s3", 0, 10, "夹逼").title == "夹逼"  # a failed call keeps the chapter title


def fake_model(calls):
    async def complete(messages):
        calls.append(messages)
        if "思维导图" in messages[0]["content"]:
            return json.dumps({"title": "数列极限笔记", "summary": "讲定义、例题和夹逼准则",
                               "mindmap": {"label": "数列极限", "children": [{"label": "定义"}, {"label": "例题"}]}})
        start = float(messages[1]["content"].split("本节时间：")[1].split("–")[0])
        return json.dumps({"title": f"节{int(start)}", "points": ["要点"], "formulas": ["\\lim a_n"],
                           "figures": [{"time": start + 5, "caption": "板书"}]}, ensure_ascii=False)
    return complete


def test_build_note_writes_sections_figures_and_a_mind_map():
    calls, steps = [], []

    async def grab(t):
        return None if t > 300 else f"/api/link-jobs/j/extra/{int(t * 100):08d}.jpg"

    note = asyncio.run(build_note(title="视频", duration=600, transcript=TRANSCRIPT, screen=SCREEN, chapters=CHAPTERS,
                                  complete=fake_model(calls), grab=grab, progress=lambda d, t, m: steps.append((d, t))))
    assert [s["title"] for s in note["sections"]] == ["节0", "节120", "节300"]
    assert note["sections"][0]["figures"] == [{"time": 5.0, "caption": "板书", "src": "/api/link-jobs/j/extra/00000500.jpg"}]
    assert note["sections"][2]["figures"] == []  # no picture could be read: the figure is dropped
    assert note["title"] == "数列极限笔记" and note["mindmap"]["children"][0]["label"] == "定义"
    assert len(calls) == 4 and steps[-1] == (5, 5)


def test_an_unusable_overview_still_gives_a_mind_map_of_the_sections():
    async def complete(messages):
        return "抱歉" if "思维导图" in messages[0]["content"] else json.dumps({"title": "节", "keywords": ["k1", "k2"]})

    async def grab(t):
        return None

    note = asyncio.run(build_note(title="视频", duration=600, transcript=TRANSCRIPT, screen=SCREEN, chapters=CHAPTERS,
                                  complete=complete, grab=grab))
    assert note["title"] == "视频" and len(note["mindmap"]["children"]) == 3
    assert note["mindmap"]["children"][0]["children"] == [{"label": "k1"}, {"label": "k2"}]


NOTE = {"title": "数列极限", "summary": "摘要", "video": {"title": "原视频"},
        "sections": [{"id": "s1", "title": "定义", "start": 0, "end": 120, "points": ["ε-N"], "formulas": ["\\lim a_n = a"],
                      "examples": [], "keywords": [], "figures": [{"time": 15, "caption": "板书", "src": "/api/link-jobs/j/extra/00001500.jpg"}]}],
        "mindmap": {"label": "极限", "children": [{"label": "定义"}]}}


def unzip(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    return z, z.read("笔记.md").decode()


def test_export_without_a_board_follows_the_note(tmp_path):
    pic = tmp_path / "extra" / "00001500.jpg"
    pic.parent.mkdir()
    pic.write_bytes(b"\xff\xd8jpg")
    data, title = export.to_zip(NOTE, None, lambda src: pic if src.endswith("00001500.jpg") else None)
    page = export.to_preview_html(NOTE, None, lambda src: pic if src.endswith("00001500.jpg") else None)
    assert "data:image/jpeg;base64," in page and "images/" not in page  # pictures inlined
    z, md = unzip(data)
    assert title == "数列极限" and md.startswith("# 数列极限\n\n> 摘要")
    assert "## 定义（00:00–02:00）" in md and "$$\n\\lim a_n = a\n$$" in md
    assert "![板书](images/01-extra-00001500.jpg)" in md and "images/01-extra-00001500.jpg" in z.namelist()
    assert md.index("## 定义") < md.index("![板书]") < md.index("## 思维导图") and "  - 定义" in md


def test_export_follows_the_board_in_reading_order(tmp_path):
    pic = tmp_path / "p.jpg"
    pic.write_bytes(b"\xff\xd8")
    board = {"blocks": [
        {"type": "figure", "x": 0, "y": 500, "src": "/api/link-jobs/j/extra/00001500.jpg", "caption": "挪到最后的图"},
        {"type": "section", "x": 400, "y": 100, "title": "右边的节", "points": ["改过的要点"]},
        {"type": "title", "x": 0, "y": 0, "text": "我的标题"},
        {"type": "text", "x": 0, "y": 110, "text": "左边的批注"},
        {"type": "figure", "x": 0, "y": 600, "src": "https://evil.example/x.jpg", "caption": "外部图片"},
    ]}
    _, md = unzip(export.to_zip(NOTE, board, lambda src: pic)[0])
    assert md.index("# 我的标题") < md.index("左边的批注") < md.index("## 右边的节") < md.index("挪到最后的图")
    assert "改过的要点" in md and "外部图片" not in md  # only the job's own pictures are bundled


def api(tmp_path, monkeypatch):
    import app
    video = ResolvedVideo("bilibili", "BV1", "u", "数列极限", 600.0, [Stream("https://a/720", {}, "s", 720)])
    job = FrameJob("job1", video, None, tmp_path / "jobs" / "job1", count=2)
    store = SessionStore(tmp_path / "db.sqlite3")
    store.create(job, "u")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app, "store", store)
    monkeypatch.setitem(app.jobs, "job1", job)
    return app, job


def test_routes_generate_save_the_board_and_export(tmp_path, monkeypatch):
    app, job = api(tmp_path, monkeypatch)
    service = app.notes_service

    async def fake_build(job, request=None):
        from modules.notes.task import write
        write(job.root, {"status": "done", "message": "", "progress": {}, "note": NOTE})
        service.running.discard(job.id)

    monkeypatch.setattr(service, "build", fake_build)
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/notes").json()["status"] == "none"  # nothing runs until asked
    assert client.put("/api/link-jobs/job1/notes/board", json={"blocks": []}).status_code == 409
    assert client.post("/api/link-jobs/job1/notes", json={"kind": "lecture"}).json()["status"] in {"running", "done"}
    state = client.get("/api/link-jobs/job1/notes").json()
    assert state["status"] == "done" and state["note"]["title"] == "数列极限" and state["board"] is None

    board = {"blocks": [{"id": "b1", "type": "title", "x": 0, "y": 0, "w": 400, "h": 80, "text": "改名"}], "viewport": {"x": 0, "y": 0, "zoom": 1}}
    assert client.put("/api/link-jobs/job1/notes/board", json=board).status_code == 200
    assert client.get("/api/link-jobs/job1/notes").json()["board"]["blocks"][0]["text"] == "改名"
    assert client.put("/api/link-jobs/job1/notes/board", json={"blocks": "x"}).status_code == 422

    r = client.get("/api/link-jobs/job1/notes/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert unzip(r.content)[1].startswith("# 改名")

    page = client.get("/api/link-jobs/job1/notes/export?preview=1")  # what the export will read like
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "<h1>改名</h1>" in page.text

    async def shot(page):
        assert "<h1>改名</h1>" in page
        return b"\x89PNG fake"

    monkeypatch.setattr(export, "to_long_image", shot)  # the real one needs Chromium
    image = client.get("/api/link-jobs/job1/notes/export?image=1")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png" and image.content.startswith(b"\x89PNG")


def test_a_note_cut_off_by_a_restart_reads_as_failed(tmp_path, monkeypatch):
    app, job = api(tmp_path, monkeypatch)
    from modules.notes.task import write
    write(job.root, {"status": "running", "message": "", "progress": {}, "note": None})
    state = TestClient(app.app).get("/api/link-jobs/job1/notes").json()
    assert state["status"] == "failed" and "重新生成" in state["message"]


def test_sections_without_speech_are_written_from_their_frames(tmp_path):
    pic = tmp_path / "f.jpg"
    pic.write_bytes(b"\xff\xd8board")
    seen = []

    async def complete(messages):
        if "思维导图" in messages[0]["content"]:
            return "{}"
        seen.append(messages[1]["content"])
        return json.dumps({"title": "板书整理", "points": ["从画面读到的定义"]})

    async def grab(t):
        return None

    chapters = [{"start": 0, "end": 120, "title": "定义"}, {"start": 1000, "end": 1100, "title": "空"}]
    note = asyncio.run(build_note(title="课", duration=1100, transcript=[], screen=[], chapters=chapters,
                                  complete=complete, grab=grab,
                                  pictures=lambda a, b: [("画面 · 00:30", pic)] if a < 120 else []))
    first, empty = note["sections"]
    assert first["points"] == ["从画面读到的定义"]
    parts = seen[0]
    assert [p["type"] for p in parts] == ["text", "text", "image_url"] and "（无）" in parts[0]["text"]
    assert parts[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert empty["title"] == "空" and "没有读到" in empty["points"][0] and len(seen) == 1  # nothing to read: no call


def test_figure_moments_in_other_forms_are_understood():
    from modules.notes.task import figure_time
    assert figure_time("33:00", 1956, 2238) == 1980          # mm:ss
    assert figure_time("0:33:00", 1956, 2238) == 1980        # h:mm:ss
    assert figure_time(120, 1956, 2238) == 2076              # counted from the section start
    assert figure_time(1990.5, 1956, 2238) == 1990.5
    assert figure_time(3000, 1956, 2238) is None and figure_time("下一页", 1956, 2238) is None


def test_a_section_without_a_usable_moment_gets_its_middle_frame():
    grabbed = []

    async def complete(messages):
        if "思维导图" in messages[0]["content"]:
            return "{}"
        return json.dumps({"title": "节", "points": ["p"], "figures": [{"time": "下一页"}]})

    async def grab(t):
        grabbed.append(t)
        return f"/api/link-jobs/j/extra/{int(t * 100):08d}.jpg"

    note = asyncio.run(build_note(title="课", duration=600, transcript=TRANSCRIPT, screen=SCREEN, chapters=CHAPTERS,
                                  complete=complete, grab=grab))
    assert [s["figures"][0]["time"] for s in note["sections"]] == [60.0, 210.0, 450.0] and sorted(grabbed) == [60.0, 210.0, 450.0]
