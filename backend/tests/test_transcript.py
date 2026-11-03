import asyncio
import json
import sqlite3

from modules.agent.run import build_messages, pick_transcript
from modules.frames import FrameJob, GrabResult
from modules.store import SessionStore
from modules.transcript import Segment, Transcript, run_transcript
from modules.transcript.asr import clean
from modules.video_source import ResolvedVideo, Stream


def video(audio=("https://a1", "https://a2")):
    return ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "标题", 60.0, [Stream("https://v", {}, "v")],
                         audio_streams=[Stream(u, {}, f"a{i}") for i, u in enumerate(audio)])


class FakeResolver:
    def __init__(self):
        self.refreshes = 0

    async def refresh(self, v):
        self.refreshes += 1
        return video(("https://fresh",))


def make_job(tmp_path, v=None, statuses=("ok", "ok", "ok", "ok")):
    job = FrameJob("s1", v or video(), FakeResolver(), tmp_path / "s1", count=len(statuses))
    for slot, status in zip(job.slots, statuses):
        slot.status = status
        if status == "ok":
            job.frame_path(slot.index).write_bytes(b"jpg")
    job.transcript = Transcript()
    return job


def reader(rule):
    async def read(stream, out, timeout):
        result = rule(stream.url)
        if result.ok:
            out.write_bytes(b"RIFF" + b"\0" * 100)
        return result
    return read


async def fake_asr(path):
    assert path.is_file()
    return [Segment(1.0, 3.0, "大家好"), Segment(3.0, 5.0, "今天讲剪辑")]


def test_clean_drops_hallucinations_and_repeats():
    raw = [
        {"start": 0, "end": 2, "text": " 大家好 "},
        {"start": 2, "end": 3, "text": "大家好"},  # immediate repeat → merged
        {"start": 5, "end": 8, "text": "请不吝点赞 订阅 转发 打赏支持明镜与点点栏目"},
        {"start": 9, "end": 10, "text": "嗯", "no_speech_prob": 0.9, "avg_logprob": -1.5},
        {"start": 11, "end": 12, "text": "啊啊啊啊啊啊", "compression_ratio": 3.1},
        {"start": 12, "end": 14, "text": "结束"},
        {"start": 20, "end": 22, "text": "字幕志愿者 李宗盛"},
        {"start": 23, "end": 24, "text": "作词 李宗盛"},
    ]
    assert [(s.start, s.end, s.text) for s in clean(raw)] == [(0.0, 3, "大家好"), (12.0, 14.0, "结束")]


def test_saved_transcripts_lose_hallucinations_on_load():
    t = Transcript.from_dict({"status": "done", "segments": [{"start": 0, "end": 1, "text": "字幕志愿者 李宗盛"},
                                                              {"start": 2, "end": 3, "text": "李宗盛的歌很好听"}]})
    assert [s.text for s in t.segments] == ["李宗盛的歌很好听"]


def test_transcript_success_removes_audio(tmp_path):
    job = make_job(tmp_path)
    asyncio.run(run_transcript(job, read=reader(lambda u: GrabResult(True)), transcribe=fake_asr))
    assert job.transcript.status == "done" and len(job.transcript.segments) == 2
    assert not (job.root / "audio.wav").exists()
    assert [e["status"] for e in job.events if e["type"] == "transcript"] == ["running", "running", "done"]


def test_transcript_refreshes_refused_addresses_once(tmp_path):
    job = make_job(tmp_path)
    asyncio.run(run_transcript(job, read=reader(lambda u: GrabResult(u == "https://fresh", "forbidden")), transcribe=fake_asr))
    assert job.transcript.status == "done" and job.resolver.refreshes == 1


def test_transcript_without_audio_or_speech(tmp_path):
    job = make_job(tmp_path, video(audio=()))
    asyncio.run(run_transcript(job, transcribe=fake_asr))
    assert job.transcript.status == "none"

    async def silent(path):
        return []
    job = make_job(tmp_path)
    asyncio.run(run_transcript(job, read=reader(lambda u: GrabResult(True)), transcribe=silent))
    assert job.transcript.status == "empty"

    async def broken(path):
        raise RuntimeError("model")
    job = make_job(tmp_path)
    asyncio.run(run_transcript(job, read=reader(lambda u: GrabResult(True)), transcribe=broken))
    assert job.transcript.status == "failed" and "RuntimeError" in job.transcript.message


def test_pick_transcript_whole_video_and_selection(tmp_path):
    job = make_job(tmp_path)  # 4 frames at 7.5, 22.5, 37.5, 52.5 s
    job.transcript = Transcript("done", "", [Segment(0, 4, "开场"), Segment(4, 9, "第一段"), Segment(20, 24, "中间"),
                                             Segment(40, 44, "后面"), Segment(55, 58, "结尾")])
    lines, note = pick_transcript(job, None)
    assert lines[0] == "[00:00] 开场 第一段" and len(lines) == 4 and note == "5 句"

    lines, note = pick_transcript(job, [job.slots[1]])  # 22.5 s ± 10 s
    assert lines == ["[00:20] 中间"] and "所选帧前后" in note

    job.transcript = Transcript("running")
    lines, note = pick_transcript(job, None)
    assert lines == [] and "转写中" in note
    content = build_messages(job, job.slots, "q", [], True, transcript=(lines, note))[1]["content"]
    assert "语音：语音仍在转写中" in content[0]["text"]


def test_transcript_goes_into_the_request(tmp_path):
    job = make_job(tmp_path)
    content = build_messages(job, job.slots[:1], "讲了什么", [], True, transcript=(["[00:01] 大家好"], "1 句"))[1]["content"]
    assert content[1]["text"] == "语音转写（1 句）：\n[00:01] 大家好" and content[2]["type"] == "text"


def test_store_saves_restores_and_migrates(tmp_path):
    db = tmp_path / "db.sqlite3"
    legacy = sqlite3.connect(db)  # a database from before the transcript column
    legacy.executescript("CREATE TABLE sessions (id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL, "
                         "source TEXT NOT NULL, task TEXT NOT NULL DEFAULT '', video TEXT NOT NULL, slots TEXT NOT NULL);")
    legacy.close()
    store = SessionStore(db)
    job = make_job(tmp_path)
    store.create(job, "BV1")
    assert store.restore("s1", None, job.root).transcript.status == "failed"  # never transcribed

    job.transcript = Transcript("done", "已转写 1 句", [Segment(1, 2, "你好")])
    store.save_transcript(job)
    restored = store.restore("s1", None, job.root).transcript
    assert restored.status == "done" and restored.segments[0].text == "你好"
    assert store.list()[0]["transcript"] == "done"

    job.transcript = Transcript("running")
    store.save_transcript(job)
    assert store.restore("s1", None, job.root).transcript.status == "failed"  # cut off by a restart
    assert json.loads(store.get("s1")["transcript"])["status"] == "running"


def test_no_audio_never_imports_recognition_engine(tmp_path, monkeypatch):
    from modules.transcript import asr
    def unavailable_import():
        raise AssertionError('A silent video must not import the recognition stack')
    monkeypatch.setattr(asr, 'available', unavailable_import)
    job = make_job(tmp_path, video(audio=()))
    asyncio.run(run_transcript(job))
    assert job.transcript.status == 'none'
