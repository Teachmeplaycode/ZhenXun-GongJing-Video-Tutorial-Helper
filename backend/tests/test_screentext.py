"""On-screen text: merging per-second OCR into captions, the job task, storage, and what the model gets."""
import asyncio
import shutil
from pathlib import Path

import pytest

from modules.agent.run import pick_screentext, speech_warning
from modules.agent.tools import AgentTools
from modules.frames import FrameJob, GrabResult
from modules.screentext import Caption, ScreenText, run_screentext
from modules.screentext.merge import build
from modules.screentext.ocr import Line
from modules.store import SessionStore
from modules.transcript import Segment, Transcript
from modules.video_source import ResolvedVideo, Stream


def sub(text, conf=1.0, y=0.85, x=None, w=0.3):
    return Line(text, conf, 0.5 - w / 2 if x is None else x, y, w, 0.05)


def logo(text):  # top-right corner, read differently each time
    return Line(text, 0.3, 0.816, 0.035, 0.17, 0.06)


def test_a_subtitle_held_for_seconds_is_one_caption_and_watermarks_go():
    readings = ["滇西小哥 biiLi", "漢西小哥。", "漠西小哥 Libi", "淇西小岢", "滇西小哥"]
    frames = []
    for t in range(20):
        lines = [logo(readings[t % len(readings)])]
        if 2 <= t <= 4:
            lines.append(sub("火龙果难摘得很" if t != 3 else "火龙果难摘得根"))  # one misread second
        if t == 6:
            lines.append(sub("失败X5", conf=0.3, y=0.45))
        if t in (8, 11):  # gone for two seconds: still the same caption (an OCR miss)
            lines.append(sub("你看下面"))
        if t == 15:
            lines += [sub("怨", y=0.45), Line("Eingbe Pscbrked", 0.3, 0.4, 0.5, 0.2, 0.04)]  # noise
        frames.append((float(t), lines))
    caps = build(frames)
    assert [(c.start, c.end, c.text, c.pos) for c in caps] == [
        (2.0, 5.0, "火龙果难摘得很", "bottom"), (6.0, 7.0, "失败X5", "middle"), (8.0, 12.0, "你看下面", "bottom")]


REAL = ["哇这些火龙果全被鸟吃完了", "你瞧就是鸟吃一半", "人吃一半", "这个只能吃一半", "我不在家都没有人摘了吃",
        "一背篓啊", "摘不到啊", "阿叔你要吃一点吗", "还记得那四个火龙果吗", "哎呀我害怕得很"]


def test_subtitles_starting_at_the_same_spot_are_not_a_watermark():
    # A new line every 3 s, all starting at the same x: different words, so never taken for a logo.
    frames = [(float(t), [sub(REAL[t // 3], x=0.3)]) for t in range(30)]
    assert [c.text for c in build(frames)] == REAL


def test_a_title_that_never_leaves_counts_as_a_watermark():
    frames = [(float(t), [Line("第三集 云南的火龙果", 1.0, 0.05, 0.05, 0.3, 0.05), sub(REAL[t // 3])]) for t in range(30)]
    assert [c.text for c in build(frames)] == REAL


def make_job(tmp_path, duration=10.0):
    v = ResolvedVideo("bilibili", "BV1", "u", "t", duration,
                      [Stream("https://a/720", {}, "s720", 720), Stream("https://a/480", {}, "s480", 480)])
    job = FrameJob("j", v, None, tmp_path / "j", count=2)
    job.screentext = ScreenText()
    job.transcript = Transcript("done", "", [Segment(0, 1, "你好")])
    return job


def test_task_reads_the_480p_stream_and_cleans_up(tmp_path):
    job = make_job(tmp_path)
    used = []

    async def read(stream, folder, timeout):
        used.append(stream.label)
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, 4):
            (folder / f"{i:05d}.jpg").write_bytes(b"jpg")
        return GrabResult(True)

    def recognize(path):
        return [sub("这个是邻居家给的")] if Path(path).stem in ("00002", "00003") else []

    asyncio.run(run_screentext(job, read=read, recognize=recognize))
    assert used == ["s480"] and job.screentext.status == "done"
    assert [(c.start, c.end, c.text) for c in job.screentext.segments] == [(1.0, 3.0, "这个是邻居家给的")]
    assert not (job.root / "screentext").exists()
    assert [e["type"] for e in job.events].count("screentext") >= 3


def test_task_reports_unavailable_and_failures(tmp_path):
    job = make_job(tmp_path)

    async def refused(stream, folder, timeout):
        return GrabResult(False, "error", "x")

    asyncio.run(run_screentext(job, read=refused, recognize=lambda p: []))
    assert job.screentext.status == "failed" and "读取画面失败" in job.screentext.message
    with pytest.MonkeyPatch.context() as m:
        m.setattr("modules.screentext.ocr.available", lambda: False)
        job.screentext = ScreenText()
        asyncio.run(run_screentext(job, read=refused))
    assert job.screentext.status == "unavailable"


def test_saved_and_restored_with_the_session(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite3")
    job = make_job(tmp_path)
    store.create(job, "u")
    job.screentext = ScreenText("done", "识别到 1 段", [Caption(1, 3, "这个是邻居家给的", "bottom")])
    store.save_screentext(job)
    shutil.rmtree(job.root)
    back = store.restore("j", None, tmp_path / "j")
    assert back.screentext.segments == job.screentext.segments and back.screentext.status == "done"
    store.db.execute("UPDATE sessions SET screentext = NULL")
    assert store.restore("j", None, tmp_path / "j").screentext.status == "failed"  # older sessions: retry fills it in


def test_the_model_gets_captions_and_a_warning_when_speech_is_garbage(tmp_path):
    job = make_job(tmp_path, duration=600)
    job.screentext = ScreenText("done", "", [Caption(t, t + 2, f"字幕第{t}句", "bottom") for t in range(0, 300, 10)]
                                + [Caption(5, 6, "失败X5", "middle")])
    lines, note = pick_screentext(job, None)
    assert lines[0] == "[00:00] 字幕第0句" and "[00:05] （画面中的字）失败X5" in lines and note == "31 段"
    job.transcript = Transcript("done", "", [Segment(0, 1, "лох"), Segment(2, 3, "high çalış Camera"), Segment(4, 5, "好")])
    warning = speech_warning(job)
    assert "乱码" in warning and "只识别出 3 句" in warning and "以画面字幕为准" in warning
    job.transcript = Transcript("done", "", [Segment(t, t + 1, "正常的话") for t in range(40)])
    assert speech_warning(job) == ""


def test_search_and_read_cover_both_sources(tmp_path):
    job = make_job(tmp_path, duration=100)
    job.screentext = ScreenText("done", "", [Caption(30, 32, "这个是邻居家给的", "bottom")])
    tools = AgentTools(job)
    r = asyncio.run(tools.run("search_transcript", {"query": "邻居"}))
    assert "[00:30] 〔字幕〕这个是邻居家给的" in r.text and r.data["hits"][0]["source"] == "screen"
    r = asyncio.run(tools.run("read_transcript", {"start": "0", "end": "40"}))
    assert r.text.splitlines()[:2] == ["[00:00] 你好", "[00:30] 〔字幕〕这个是邻居家给的"]


def test_subtitles_repeating_good_speech_are_left_out_of_the_context(tmp_path):
    job = make_job(tmp_path, duration=600)
    job.transcript = Transcript("done", "", [Segment(t, t + 2, f"今天我们聊第{t}个话题") for t in range(0, 400, 10)])
    job.screentext = ScreenText("done", "", [Caption(t, t + 2, f"今天我们聊第{t}个话题", "bottom") for t in range(0, 400, 10)]
                                + [Caption(55, 58, "失败X5", "middle"), Caption(200, 202, "关注我领取资料", "bottom")])
    lines, note = pick_screentext(job, None)
    assert lines == ["[00:55] （画面中的字）失败X5", "[03:20] 关注我领取资料"]
    assert "另有 40 段字幕和语音转写重复" in note


def test_misread_small_print_on_busy_screens_is_dropped():
    menu = [Line(t, c, 0.1, 0.1 + i * 0.08, 0.5, 0.04) for i, (t, c) in enumerate(
        [("显示和亮度", 1.0), ("注说猴幕不媳阴", 0.5), ("色彰调节与色滥", 0.3), ("护眼模式", 1.0), ("督德分辦率", 0.5), ("字体大小", 1.0)])]
    frames = [(0.0, menu), (1.0, [sub("失败X5", conf=0.3, y=0.45)])]
    assert [c.text for c in build(frames)] == ["显示和亮度", "护眼模式", "字体大小", "失败X5"]
