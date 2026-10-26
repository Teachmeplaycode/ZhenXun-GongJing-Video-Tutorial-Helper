"""Discussion scope, preview-before-apply, edited baselines and optimistic concurrency."""
import asyncio
import copy
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from modules.frames import FrameJob
from modules.notes.discussion import build_discussion_note, selected_turns
from modules.notes.revisions import effective_note, fingerprint, revision_board
from modules.notes.router import NotesService
from modules.notes.task import BOARD, load, write
from modules.video_source import ResolvedVideo, Stream


def note(title="旧笔记", point="旧要点"):
    return {"title": title, "summary": "原摘要", "video": {"title": "原片", "duration": 60},
            "sections": [{"id": "s1", "title": "构图", "start": 0, "end": 60, "points": [point],
                          "formulas": [], "examples": [], "keywords": [], "figures": []}],
            "mindmap": {"label": "镜头", "children": [{"label": "构图"}]}}


ROWS = [{"id": 11, "role": "user", "content": "这个分镜为什么使用低机位？", "status": "done", "command": "细看", "frames": [0]},
        {"id": 12, "role": "assistant", "content": "00:10 低机位强化了体量，属于画面分析。", "status": "done"},
        {"id": 13, "role": "user", "content": "再说说剪辑关系", "status": "done"},
        {"id": 14, "role": "assistant", "content": "这里通过动作匹配衔接。", "status": "done"}]


@pytest.fixture
def env(tmp_path, monkeypatch):
    video = ResolvedVideo("bilibili", "BV1", "u", "镜头语言", 60, [Stream("https://x", {}, "s", 720)])
    job = FrameJob("j", video, None, tmp_path / "j", count=2)
    job.root.mkdir(parents=True, exist_ok=True)
    job.slots[0].status = "ok"
    job.frame_path(0).write_bytes(b"jpeg")
    tasks = []

    def spawn(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    service = NotesService(lambda _: job, spawn, lambda: object(), get_messages=lambda _: copy.deepcopy(ROWS))

    async def fake_discussion(**inputs):
        result = effective_note(inputs["current_note"], inputs["current_board"]) or note("分镜笔记")
        result["sections"][0]["points"] = ["分析：低机位强化体量"]
        result["sections"].append({"id": "discussion-new", "title": "剪辑关系", "start": 10, "end": 30,
                                   "points": ["分析：动作匹配"], "formulas": [], "examples": [], "keywords": [], "figures": []})
        return result, ["s1", "discussion-new"]

    monkeypatch.setattr("modules.notes.router.build_discussion_note", fake_discussion)
    app = FastAPI()
    app.include_router(service.router)
    return service, job, TestClient(app), tasks


def seed(job):
    old = note()
    board = revision_board(old, None)
    board["blocks"][0]["text"] = "我的手改标题"
    section = next(b for b in board["blocks"] if b["type"] == "section")
    section.update(points=["我写的镜头解读"], x=37, y=450)
    board["blocks"].append({"id": "mine", "type": "text", "text": "导演访谈待补", "x": 0, "y": 900, "w": 500})
    write(job.root, {"status": "done", "note": old, "made": 100})
    write(job.root, board, BOARD)
    return old, board


def test_selected_turns_are_resolved_in_saved_order_and_keep_command():
    turns = selected_turns(ROWS, [14, 13, 12, 11])
    assert [t["question"]["id"] for t in turns] == [11, 13]
    assert turns[0]["question"]["command"] == "细看"


@pytest.mark.parametrize("ids,code", [([11], 422), ([12], 422), ([11, 12, 999], 400),
                                      ([], 422), ([True, 12], 422), (["11", 12], 422)])
def test_selection_requires_owned_complete_turns(ids, code):
    with pytest.raises(HTTPException) as err:
        selected_turns(ROWS, ids)
    assert err.value.status_code == code


def test_pending_or_manual_answers_are_not_note_sources():
    for extra in ({"status": "running"}, {"status": "error"}, {"manual": "replay"}, {"content": ""}):
        rows = copy.deepcopy(ROWS[:2])
        rows[1].update(extra)
        with pytest.raises(HTTPException):
            selected_turns(rows, [11, 12])


def test_skill_report_without_prose_is_a_completed_answer_source():
    from modules.notes.discussion import conversation_text
    rows = copy.deepcopy(ROWS[:2])
    rows[1].update(content="", events=[{"type": "tool_call.output", "data": {
        "report": {"summary": "已核查三条说法", "claims": [{"text": "说法一", "verdict": "正确"}], "images": ["large"]}}}])
    turns = selected_turns(rows, [11, 12])
    assert "已核查三条说法" in conversation_text(turns)
    assert "large" not in conversation_text(turns)


def test_first_discussion_applies_directly_but_a_revision_preserves_current_until_apply(env):
    service, job, client, tasks = env
    result = asyncio.run(service.build(job, {"source": "conversation", "message_ids": [11, 12],
                        "instruction": "按镜头关系整理", "turns": selected_turns(ROWS, [11, 12])}))
    first = client.get("/api/link-jobs/j/notes").json()
    assert first["status"] == "done" and first["draft"] is None and first["revision"]
    assert first["source"] == "conversation" and first["message_ids"] == [11, 12]
    assert first["board"] is None  # first editor opening measures its real default layout

    old, board = seed(job)
    asyncio.run(service.build(job, {"source": "conversation", "message_ids": [11, 12],
                "instruction": "", "turns": selected_turns(ROWS, [11, 12])}))
    state = client.get("/api/link-jobs/j/notes").json()
    assert state["note"] == old and state["board"] == board
    draft = state["draft"]
    assert state["status"] == "done" and state["generation"]["status"] == "done"
    assert draft["changes"] == ["改写小节：构图", "新增小节：剪辑关系"]
    assert draft["note"]["title"] == "我的手改标题"
    assert next(b for b in draft["board"]["blocks"] if b["id"] == "mine") == board["blocks"][-1]
    assert next(b for b in draft["board"]["blocks"] if b["id"] == "sec-s1")["x"] == 37
    assert "动作匹配" in client.get("/api/link-jobs/j/notes/export?draft=1&preview=1").text
    assert "动作匹配" not in client.get("/api/link-jobs/j/notes/export?preview=1").text

    applied = client.post(f"/api/link-jobs/j/notes/revisions/{draft['id']}/apply", json={"base_revision": state["revision"]}).json()
    assert applied["draft"] is None and len(applied["history"]) == 1
    assert applied["revision"] != state["revision"]
    assert "动作匹配" in client.get("/api/link-jobs/j/notes/export?preview=1").text
    saved = applied["history"][0]
    restored = client.post(f"/api/link-jobs/j/notes/revisions/{saved['id']}/restore", json={"base_revision": applied["revision"]}).json()
    assert restored["note"] == old and restored["board"] == board
    assert len(restored["history"]) == 2
    assert restored["history"][0]["id"] != saved["id"]


def test_hand_edit_during_generation_keeps_both_and_blocks_apply(env, monkeypatch):
    service, job, client, _ = env
    _, original_board = seed(job)

    async def edit_while_building(**inputs):
        changed_board = copy.deepcopy(original_board)
        changed_board["blocks"][-1]["text"] = "生成期间的新批注"
        write(job.root, changed_board, BOARD)
        return note("草稿", "新内容"), ["s1"]

    monkeypatch.setattr("modules.notes.router.build_discussion_note", edit_while_building)
    asyncio.run(service.build(job))
    state = client.get("/api/link-jobs/j/notes").json()
    assert state["board"]["blocks"][-1]["text"] == "生成期间的新批注"
    assert state["draft"]["conflict"]
    response = client.post(f"/api/link-jobs/j/notes/revisions/{state['draft']['id']}/apply", json={"base_revision": state["revision"]})
    assert response.status_code == 409 and "手动修改" in response.json()["detail"]
    assert client.delete("/api/link-jobs/j/notes/draft").json()["draft"] is None
    assert load(job.root, BOARD)["blocks"][-1]["text"] == "生成期间的新批注"


def test_failure_and_cancellation_never_replace_current_note_or_board(env, monkeypatch):
    service, job, client, _ = env
    old, board = seed(job)

    async def fail(**inputs):
        raise ValueError("模型返回不完整")

    monkeypatch.setattr("modules.notes.router.build_discussion_note", fail)
    asyncio.run(service.build(job))
    state = client.get("/api/link-jobs/j/notes").json()
    assert state["status"] == "done" and state["generation"]["status"] == "failed"
    assert state["note"] == old and state["board"] == board

    async def interrupted(**inputs):
        raise asyncio.CancelledError()

    monkeypatch.setattr("modules.notes.router.build_discussion_note", interrupted)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.build(job))
    state = client.get("/api/link-jobs/j/notes").json()
    assert state["note"] == old and state["board"] == board
    assert state["generation"]["status"] == "failed" and not service.running


def test_restart_marks_only_generation_failed_and_retains_manual_copy(env):
    service, job, client, _ = env
    old, board = seed(job)
    write(job.root, {"status": "done", "note": old, "generation": {"status": "running"}})
    state = client.get("/api/link-jobs/j/notes").json()
    assert state["status"] == "done" and state["generation"]["status"] == "failed"
    assert state["note"] == old and state["board"] == board


def test_stale_editor_save_and_stale_actions_are_rejected(env):
    service, job, client, _ = env
    _, board = seed(job)
    base = client.get("/api/link-jobs/j/notes").json()["revision"]
    next_board = copy.deepcopy(board)
    next_board["blocks"][-1]["text"] = "保存的新批注"
    saved = client.put("/api/link-jobs/j/notes/board", json={**next_board, "base_revision": base})
    assert saved.status_code == 200 and saved.json()["revision"] != base
    assert "base_revision" not in load(job.root, BOARD)
    assert client.put("/api/link-jobs/j/notes/board", json={**board, "base_revision": base}).status_code == 409
    assert client.post("/api/link-jobs/j/notes", json={"source": "video", "base_revision": base}).status_code == 409
    assert client.post("/api/link-jobs/j/notes/revisions/missing/restore", json={"base_revision": base}).status_code == 409
    # Pan/zoom changes do not invalidate a revision or another editor's content fingerprint.
    revision = saved.json()["revision"]
    next_board["viewport"] = {"x": 999, "y": 20, "zoom": 0.5}
    moved = client.put("/api/link-jobs/j/notes/board", json={**next_board, "base_revision": revision})
    assert moved.json()["revision"] == revision


@pytest.mark.parametrize("body,code", [({"source": []}, 422), ({"source": "conversation", "message_ids": [11]}, 422),
    ({"source": "conversation", "message_ids": [11, 12, 55]}, 400),
    ({"source": "video", "message_ids": {}}, 422), ({"instruction": "a" * 2001}, 422)])
def test_routes_validate_selection_before_any_work(env, body, code):
    service, job, client, tasks = env
    assert client.post("/api/link-jobs/j/notes", json=body).status_code == code
    assert not tasks and not service.running and load(job.root) is None


def test_post_resolves_only_selected_rows_and_returns_finished_first_note(env, monkeypatch):
    service, job, client, _ = env
    captured = []

    async def build(**inputs):
        captured.extend(inputs["turns"])
        return note("分镜讨论"), ["s1"]

    monkeypatch.setattr("modules.notes.router.build_discussion_note", build)
    response = client.post("/api/link-jobs/j/notes", json={"source": "conversation", "message_ids": [12, 11], "base_revision": None})
    assert response.status_code == 200
    assert response.json()["note"]["title"] == "分镜讨论"
    assert response.json()["message_ids"] == [11, 12]
    assert len(captured) == 1 and captured[0]["question"]["frame_times"] == [job.slots[0].time]


def test_apply_write_failure_rolls_back_both_current_files_and_retains_draft(env, monkeypatch):
    import modules.notes.revisions as revisions
    service, job, client, _ = env
    old, board = seed(job)
    asyncio.run(service.build(job))
    before = load(job.root)
    state = service._state(job)
    original_replace = revisions.os.replace
    failed = False

    def fail_new_note(source, target):
        nonlocal failed
        if str(source).endswith("/next-note.json") and not failed:
            failed = True
            raise OSError("simulated full disk during commit")
        return original_replace(source, target)

    monkeypatch.setattr(revisions.os, "replace", fail_new_note)
    with pytest.raises(OSError):
        asyncio.run(service.apply("j", state["draft"]["id"], {"base_revision": state["revision"]}))
    assert load(job.root) == before and load(job.root, BOARD) == board
    assert service._state(job)["draft"]["id"] == state["draft"]["id"]
    applied = asyncio.run(service.apply("j", state["draft"]["id"], {"base_revision": state["revision"]}))
    assert applied["draft"] is None and applied["note"] != old


def test_interrupted_commit_recovers_original_before_serving_get(env):
    from modules.notes.revisions import COMMIT_DIR
    service, job, client, _ = env
    old, board = seed(job)
    previous = load(job.root)
    stage = job.root / COMMIT_DIR
    write(stage, previous, "previous-note.json")
    write(stage, board, "previous-board.json")
    write(stage, {"had_note": True, "had_board": True}, "pending.json")
    write(job.root, {"blocks": [{"id": "new", "type": "text", "text": "only half committed"}]}, BOARD)
    response = client.get("/api/link-jobs/j/notes").json()
    assert response["note"] == old and response["board"] == board
    assert not stage.exists()


def test_old_versions_remain_recoverable_after_more_than_twenty_updates(tmp_path):
    from modules.notes.revisions import archive, history_snapshot
    record = {"note": note("最初的手改"), "history": []}
    oldest = None
    for i in range(25):
        record["history"] = archive(tmp_path, record, None)
        oldest = oldest or record["history"][0]
        record["note"] = note(f"第{i + 1}版")
    assert len(record["history"]) == 25
    assert history_snapshot(tmp_path, record, oldest["id"])["note"]["title"] == "最初的手改"


def test_all_mutations_require_the_owned_job(env):
    service, job, client, _ = env
    seed(job)

    def denied(_):
        raise HTTPException(403, "示例不能修改")

    service.own_job = denied
    assert client.get("/api/link-jobs/j/notes").status_code == 200
    for method, path, body in [
        ("post", "notes", {}), ("put", "notes/board", {"blocks": []}),
        ("post", "notes/revisions/x/apply", {}), ("post", "notes/revisions/x/restore", {}),
        ("delete", "notes/draft", None),
    ]:
        response = client.request(method, "/api/link-jobs/j/" + path, json=body)
        assert response.status_code == 403


def test_topic_note_uses_questions_and_manual_content_instead_of_tutorial_template():
    old = note()
    board = revision_board(old, None)
    next(b for b in board["blocks"] if b["type"] == "section")["points"] = ["我手写的构图观察"]
    calls = []

    async def complete(messages):
        calls.append(messages)
        if len(calls) == 1:
            assert "这个分镜" in messages[1]["content"] and "我手写的构图观察" in messages[1]["content"]
            assert "选择的任务：细看" in messages[1]["content"]
            return json.dumps({"goal": "分镜中的低机位", "sections": [
                {"title": "低机位的作用", "start": 0, "end": 30, "target_id": "s1"},
                {"title": "动作匹配", "start": 30, "end": 60, "target_id": ""}]})
        assert "不要写软件按钮" in messages[0]["content"]
        assert "原素材语音" in messages[1]["content"] and "讨论中的分析判断" in messages[0]["content"]
        return json.dumps({"title": "镜头观察", "points": ["分析：低机位强化体量"], "figures": [{"time": 10, "caption": "低机位"}]})

    async def grab(t):
        return f"/api/link-jobs/j/extra/{int(t * 100):08d}.jpg"

    result, changed = asyncio.run(build_discussion_note(title="电影", duration=60,
        transcript=[(0, 30, "人物进入画面")], screen=[], chapters=None,
        turns=selected_turns(ROWS, [11, 12]), instruction="关注分镜", current_note=old,
        current_board=board, complete=complete, grab=grab))
    assert len(calls) == 3 and result["title"] == "旧笔记"
    assert result["sections"][0]["points"] == ["分析：低机位强化体量"]
    assert changed[0] == "s1" and len(changed) == 2
    assert result["sections"][0]["figures"][0]["src"].endswith("00001000.jpg")


def test_steps_go_into_a_note_only_when_asked_and_built(env, monkeypatch):
    service, job, client, _ = env
    assert client.post("/api/link-jobs/j/notes", json={"source": "video", "use_steps": True}).status_code == 409
    assert client.post("/api/link-jobs/j/notes", json={"source": "video", "use_steps": "yes"}).status_code == 422
    from modules import steps
    steps.save(job.root, {"status": "done", "kind": "content", "steps": [{"n": 1, "time": 5, "action": "介绍低机位", "detail": ""}]})
    given = []

    async def build(**inputs):
        given.append(inputs["steps"])
        return note("镜头笔记")

    monkeypatch.setattr("modules.notes.router.build_note", build)
    done = client.post("/api/link-jobs/j/notes", json={"source": "video", "use_steps": True}).json()
    assert given == [[{"n": 1, "time": 5, "action": "介绍低机位", "detail": ""}]]
    assert done["used_steps"] == 1 and "参考了 1 张步骤卡" in done["message"]
