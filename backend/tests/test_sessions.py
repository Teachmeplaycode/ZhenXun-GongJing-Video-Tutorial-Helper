from modules.frames import FrameJob
from modules.store import SessionStore
from modules.video_source import Part, ResolvedVideo, Stream


def make_job(root, statuses):
    v = ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "标题", 60.0, [Stream("https://a", {}, "s")],
                      part=2, parts=[Part(1, "P1", 30), Part(2, "P2", 60)], author="UP", extra={"bvid": "BV1", "cid": 7})
    job = FrameJob("s1", v, None, root, count=len(statuses))
    for slot, status in zip(job.slots, statuses):
        slot.status = status
        if status == "ok":
            job.frame_path(slot.index).write_bytes(b"jpg")
    return job


def test_create_list_and_restore(tmp_path):
    store = SessionStore(tmp_path / "db.sqlite3")
    job = make_job(tmp_path / "jobs" / "s1", ["ok", "pending", "missing", "ok"])
    job.slots[2].reason = "timeout"
    store.create(job, "BV1 分享文本", "讲了什么")
    store.save_slots(job)

    [item] = store.list()
    assert item["title"] == "标题" and item["frames_ok"] == 2 and item["frames_total"] == 4 and item["questions"] == 0

    job.frame_path(3).unlink()  # a frame file lost on disk
    restored = store.restore("s1", None, tmp_path / "jobs" / "s1")
    assert restored.restored and restored.video.streams == []
    assert restored.video.extra == {"bvid": "BV1", "cid": 7} and restored.video.parts[1].title == "P2"
    assert [(s.status, s.reason) for s in restored.slots] == [
        ("ok", ""), ("missing", "interrupted"), ("missing", "timeout"), ("missing", "interrupted")]
    assert store.get("s1")["task"] == "讲了什么"
    assert store.restore("nope", None, tmp_path / "x") is None


def test_messages_and_history(tmp_path):
    store = SessionStore(tmp_path / "db.sqlite3")
    store.create(make_job(tmp_path / "s1", ["ok"]), "BV1")
    for i in range(6):
        store.add_message("s1", "user", f"问{i}", data={"frames": [0]})
        status = "error" if i == 5 else "done"
        store.add_message("s1", "assistant", f"答{i}", status=status, data={"events": [{"type": "run.completed"}]})
    store.add_message("s1", "user", "没有回答的问题")

    messages = store.messages("s1")
    assert len(messages) == 13 and messages[0]["frames"] == [0] and messages[1]["events"][0]["type"] == "run.completed"
    history = store.history("s1", turns=2)
    assert [m["content"] for m in history] == ["问3", "答3", "问4", "答4"]  # failed answer 5 skipped
    assert store.list()[0]["questions"] == 7 and store.list()[0]["last_question"] == "没有回答的问题"

    store.delete("s1")
    assert store.messages("s1") == [] and store.list() == []
