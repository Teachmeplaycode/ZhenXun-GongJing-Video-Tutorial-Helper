import asyncio
import shutil
import subprocess

import pytest

from modules.frames import FrameJob
from modules.video_source import ResolveError
from modules.video_source.local import LocalResolver, resolve_file

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def make_video(path, audio=True, seconds=4):
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=10"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-shortest"]
    subprocess.run(args + [str(path)], check=True)
    return path


def test_resolve_file_reads_duration_and_audio(tmp_path):
    v = asyncio.run(resolve_file(make_video(tmp_path / "clip.mp4"), "我的视频.mp4"))
    assert v.platform == "local" and v.title == "我的视频" and abs(v.duration - 4) < 0.2
    assert v.streams[0].url.endswith("clip.mp4") and v.audio_streams

    silent = asyncio.run(resolve_file(make_video(tmp_path / "silent.mp4", audio=False), "silent.mp4"))
    assert silent.audio_streams == []


def test_rejects_non_video(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(ResolveError) as e:
        asyncio.run(resolve_file(tmp_path / "notes.txt", "notes.txt"))
    assert e.value.code == "not_video"


def test_frames_sampled_from_local_file(tmp_path):
    v = asyncio.run(resolve_file(make_video(tmp_path / "clip.mp4"), "clip.mp4"))
    job = FrameJob("j", v, LocalResolver(), tmp_path / "j", count=4)
    asyncio.run(job.run())
    assert job.coverage()["ok"] == 4 and all(job.frame_path(i).stat().st_size > 0 for i in range(4))
