"""Whole-video reads that the server cuts off part-way are carried on from where they stopped.

ffmpeg treats a dropped connection as the end of the file and exits 0, so a 42-minute lecture was
transcribed to 8:24 and read for on-screen text to 1:33, both reported as done. These fakes stand in
for ffmpeg: the first pass stops early, the next ones (an input seek to where it stopped) go on.
"""
import asyncio
import wave

from modules.frames import cuts, resume
from modules.screentext import task as screen
from modules.transcript import audio
from modules.video_source import Stream

STREAM = Stream("https://cdn.example/a.m4s", {"Referer": "x"}, "s")
HEADER = "Input #0, mov,mp4 from 'x':\n  Duration: 00:10:00.00, start: 0.000000, bitrate: 64 kb/s\n"


def test_reading_the_header_and_the_progress():
    assert resume.input_duration(HEADER) == 600
    assert resume.reached("frame=1 time=00:01:00.00 ...\nframe=2 time=00:08:24.50 bitrate") == 504.5
    assert resume.short(504, 600) and not resume.short(598.5, 600) and not resume.short(10, None)
    assert resume.seek_args(STREAM, 504.04)[-4:] == ["-ss", "504.040", "-i", "https://cdn.example/a.m4s"]
    assert resume.seek_args(STREAM, 0)[-2:] == ["-i", "https://cdn.example/a.m4s"]


def write_wav(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(audio.RATE)
        w.writeframes(b"\x00\x00" * int(seconds * audio.RATE))


def test_audio_cut_off_is_read_on_and_joined(tmp_path, monkeypatch):
    calls = []

    async def ffmpeg(stream, offset, out, timeout):
        calls.append(offset)
        write_wav(out, {0.0: 504, 504.0: 60}.get(offset, 600 - offset))  # stops at 8:24, then 9:24, then the rest
        return 0, HEADER if offset == 0 else ""

    monkeypatch.setattr(audio, "_ffmpeg", ffmpeg)
    out = tmp_path / "audio.wav"
    result = asyncio.run(audio.read_audio(STREAM, out, 60))
    assert result.ok and result.kind == "" and calls == [0.0, 504.0, 564.0]
    assert audio.wav_seconds(out) == 600


def test_audio_that_stops_making_progress_is_kept_and_marked_partial(tmp_path, monkeypatch):
    async def ffmpeg(stream, offset, out, timeout):
        write_wav(out, 504 if offset == 0 else 0)
        return 0, HEADER

    monkeypatch.setattr(audio, "_ffmpeg", ffmpeg)
    result = asyncio.run(audio.read_audio(STREAM, tmp_path / "audio.wav", 60))
    assert result.ok and result.kind == "partial" and "08:24" in result.detail and "10:00" in result.detail


def test_screen_frames_cut_off_continue_their_numbering(tmp_path, monkeypatch):
    calls = []

    async def frames_from(stream, folder, offset, timeout):
        calls.append(offset)
        first = round(offset) + 1
        n = 93 if offset == 0 else 600 - round(offset)
        for i in range(first, first + n):
            (folder / f"{i:05d}.jpg").write_bytes(b"jpg")
        return 0, HEADER if offset == 0 else ""

    monkeypatch.setattr(screen, "_frames_from", frames_from)
    result = asyncio.run(screen.read_frames(STREAM, tmp_path / "f", 60))
    files = sorted(p.name for p in (tmp_path / "f").glob("*.jpg"))
    assert result.ok and result.kind == "" and calls == [0.0, 93.0]
    assert len(files) == 600 and files[0] == "00001.jpg" and files[-1] == "00600.jpg"


def test_shot_changes_after_a_cut_off_are_shifted_by_where_the_pass_began(tmp_path, monkeypatch):
    async def one_pass(stream, folder, offset, timeout):
        if offset == 0:
            return 0, HEADER + "time=00:01:33.00", "pts_time:0\npts_time:30.5\n"
        return 0, "time=00:08:27.00", "pts_time:0\npts_time:100\n"  # 0 is where the pass began: no cut

    monkeypatch.setattr(cuts, "_pass", one_pass)
    found, why = asyncio.run(cuts.detect(STREAM, tmp_path, 60))
    assert why == "" and found == [30.5, 193.0]
