"""Answers wait briefly only when their requested scope has no usable evidence."""
import asyncio

from modules.agent import run
from modules.screentext import Caption, ScreenText
from modules.transcript import Segment, Transcript
from tests.test_replay import job_for


def collect(job, on_sleep, **kwargs):
    async def sleep(seconds):
        on_sleep(seconds)
    async def go():
        return [e async for e in run.wait_for_material(job, sleep=sleep, **kwargs)]
    return asyncio.run(go())


def ready_frame(job, index=0):
    job.slots[index].status = "ok"
    job.frame_path(index).write_bytes(b"jpeg")


def test_available_frame_does_not_wait_for_speech_or_ocr(tmp_path):
    job = job_for(tmp_path)
    ready_frame(job)
    job.transcript, job.screentext = Transcript("running"), ScreenText("running")
    waits = []
    collect(job, waits.append)
    assert waits == []


def test_available_partial_text_does_not_wait_for_other_inputs(tmp_path):
    job = job_for(tmp_path)
    job.transcript = Transcript("running", segments=[Segment(0, 10, "已经识别的语音")])
    job.screentext = ScreenText("running")
    waits = []
    collect(job, waits.append)
    assert waits == []
    job.transcript.segments = []
    job.screentext.segments = [Caption(0, 10, "已经识别的画面文字", "middle")]
    collect(job, waits.append)
    assert waits == []


def test_no_evidence_waits_at_most_eight_seconds(tmp_path):
    job = job_for(tmp_path)
    job.transcript, job.screentext = Transcript("running"), ScreenText("running")
    waits = []
    events = collect(job, waits.append)
    assert sum(waits) == 8
    out = next(e for e in events if e["type"] == "tool_call.output")
    assert out["data"]["waited"] == 8
    assert "尚无可用" in out["stdout"]


def test_first_frame_ends_wait_without_finishing_the_job(tmp_path):
    job = job_for(tmp_path)
    job.transcript, job.screentext = Transcript("running"), ScreenText("running")
    waits = []
    def arrive(seconds):
        waits.append(seconds)
        ready_frame(job)
    collect(job, arrive)
    assert sum(waits) == 2


def test_unrelated_frame_does_not_satisfy_explicit_selection(tmp_path):
    job = job_for(tmp_path)
    ready_frame(job, 0)
    job.transcript = Transcript("running", segments=[Segment(0, 10, "无关开头")])
    job.screentext = ScreenText("running")
    waits = []
    collect(job, waits.append, requested=[1])
    assert sum(waits) == 8


def test_text_near_requested_frame_and_user_attachment_are_usable(tmp_path):
    job = job_for(tmp_path)
    t = job.slots[1].time
    job.transcript = Transcript("running", segments=[Segment(t - 2, t + 2, "所选帧附近的语音")])
    waits = []
    collect(job, waits.append, requested=[1])
    assert waits == []
    job.transcript.segments = []
    attachment = tmp_path / "user.jpg"
    attachment.write_bytes(b"jpeg")
    collect(job, waits.append, images=[attachment])
    assert waits == []


def test_terminal_empty_sources_do_not_wait(tmp_path):
    job = job_for(tmp_path)
    for slot in job.slots:
        slot.status = "missing"
    job.transcript, job.screentext = Transcript("empty"), ScreenText("empty")
    waits = []
    collect(job, waits.append)
    assert waits == []
