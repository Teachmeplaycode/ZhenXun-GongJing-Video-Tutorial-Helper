"""A question asked mid-import waits in the answer for the keyframes and the speech, briefly for OCR."""
import asyncio

from modules.agent import run
from modules.screentext import ScreenText
from modules.transcript import Transcript
from tests.test_replay import job_for


def collect(job, on_sleep):
    async def sleep(_):
        on_sleep()

    async def go():
        return [e async for e in run.wait_for_material(job, sleep=sleep)]
    return asyncio.run(go())


def test_nothing_happens_when_everything_is_in(tmp_path):
    job = job_for(tmp_path)
    job.transcript, job.screentext = Transcript("done"), ScreenText("done")
    for s in job.slots:
        s.status = "ok"
    assert collect(job, lambda: None) == []


def test_waits_for_the_speech_then_stops_waiting_for_slow_screen_text(tmp_path):
    job = job_for(tmp_path)
    for s in job.slots:
        s.status = "ok"
    job.transcript, job.screentext = Transcript("running"), ScreenText("running")
    ticks = [0]

    def tick():
        ticks[0] += 1
        if ticks[0] == 3:
            job.transcript.status = "done"  # the speech arrives after 6 s; OCR never does

    events = collect(job, tick)
    steps = [e["step"] for e in events if e["type"] == "progress.update"]
    assert steps[0] == "等待语音转写、画面文字（已等 0 秒）" and steps[-1].startswith("等待画面文字")
    out = next(e for e in events if e["type"] == "tool_call.output")
    assert out["data"]["left"] == ["画面文字"] and "先用已有的部分回答" in out["stdout"]
    assert out["data"]["waited"] == 6 + int(run.SCREEN_WAIT)  # then SCREEN_WAIT more for OCR, not longer


def test_gives_up_after_the_longest_wait(tmp_path):
    job = job_for(tmp_path)
    job.transcript, job.screentext = Transcript("running"), ScreenText("done")
    for s in job.slots:
        s.status = "ok"
    events = collect(job, lambda: None)
    assert next(e for e in events if e["type"] == "tool_call.output")["data"]["waited"] == int(run.WAIT_MAX)
