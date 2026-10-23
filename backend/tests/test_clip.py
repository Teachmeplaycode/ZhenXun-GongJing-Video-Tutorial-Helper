import asyncio
import shutil
import subprocess

import pytest

from modules import archive, clip
from modules.frames import FrameJob
from modules.video_source import ResolvedVideo, Stream
from modules.video_source.local import PLATFORM as LOCAL


def test_span_clamps_to_the_video_and_the_format_limit():
    assert clip.span(5, 50, 100, "gif") == (5, 35)  # a GIF is at most 30 s
    assert clip.span(5, 30, 100, "mp4") == (5, 30)
    assert clip.span(95, 120, 100, "mp4") == (95, 100)  # not past the end
    assert clip.span(20, 10, 100, "mp4") == (10, 20)  # either order
    with pytest.raises(clip.ClipError):
        clip.span(3, 3.1, 100, "gif")  # too short
    with pytest.raises(clip.ClipError):
        clip.span(1, 4, 100, "webm")


def test_names_carry_the_title_and_the_stretch():
    assert clip._name("VLOOKUP 函数/详解", 63.2, 70.9, "gif") == "帧寻_VLOOKUP_函数_详解_0103-0110.gif"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_cuts_a_local_upload_into_gif_and_mp4_and_reuses_them(tmp_path):
    src = tmp_path / "upload.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
    video = ResolvedVideo(LOCAL, "u1", "file", "测试 视频", 6.0, [Stream(str(src), {}, "原文件", 360)])
    job = FrameJob("job1", video, None, tmp_path / "job1", count=2)

    gif = asyncio.run(clip.make(job, 1, 3, "gif"))
    assert gif.path.read_bytes()[:6] in (b"GIF89a", b"GIF87a")
    assert gif.filename == "帧寻_测试_视频_0001-0003.gif"
    mp4 = asyncio.run(clip.make(job, 1, 4, "mp4"))
    assert mp4.media_type == "video/mp4" and mp4.path.stat().st_size > 1000
    before = mp4.path.stat().st_mtime
    assert asyncio.run(clip.make(job, 1, 4, "mp4")).path.stat().st_mtime == before  # the same stretch is not cut again


def test_a_deleted_upload_says_so(tmp_path):
    video = ResolvedVideo(LOCAL, "u1", "file", "t", 6.0, [Stream(str(tmp_path / "gone.mp4"), {}, "原文件", 360)])
    job = FrameJob("job1", video, None, tmp_path / "job1", count=2)
    with pytest.raises(clip.ClipError) as e:
        asyncio.run(clip.make(job, 1, 3, "gif"))
    assert e.value.status == 404


def test_a_look_is_kept_within_bounds():
    look = clip.Look.of(fps=60, width=2000, speed=5, dither="none", max_mb=1)
    assert (look.fps, look.width, look.speed, look.dither, look.max_mb) == (30, 960, 2.0, "none", 1)
    assert clip.Look.of(fps=1, width=99, speed=0.1).fps == 5
    with pytest.raises(clip.ClipError):
        clip.Look.of(dither="atkinson")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_a_size_cap_brings_the_frame_rate_and_width_down(tmp_path):
    src = tmp_path / "upload.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "mandelbrot=size=640x360:rate=25", "-t", "4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], check=True)
    video = ResolvedVideo(LOCAL, "u1", "file", "t", 4.0, [Stream(str(src), {}, "原文件", 360)])
    job = FrameJob("job1", video, None, tmp_path / "job1", count=2)
    big = asyncio.run(clip.make(job, 0, 4, "gif", clip.Look.of(fps=25, width=640, dither="sierra")))
    capped = asyncio.run(clip.make(job, 0, 4, "gif", clip.Look.of(fps=25, width=640, dither="sierra", max_mb=0.3)))
    assert capped.path.stat().st_size < big.path.stat().st_size
    assert capped.fps < 25 and capped.width < 640 and capped.notes
    again = asyncio.run(clip.make(job, 0, 4, "gif", clip.Look.of(fps=25, width=640, dither="sierra", max_mb=0.3)))
    assert (again.fps, again.width) == (capped.fps, capped.width)  # kept, with what it ended up as


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_old_cuts_are_dropped_beyond_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(clip, "KEEP_FILES", 3)
    src = tmp_path / "upload.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10", "-t", "4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], check=True)
    video = ResolvedVideo(LOCAL, "u1", "file", "t", 4.0, [Stream(str(src), {}, "原文件", 180)])
    job = FrameJob("job1", video, None, tmp_path / "job1", count=2)
    for fps in (6, 8, 10):
        last = asyncio.run(clip.make(job, 0, 2, "gif", clip.Look.of(fps=fps, width=160)))
    kept = sorted(p.name for p in (tmp_path / "job1" / "clips").iterdir() if p.suffix in (".gif", ".mp4"))
    assert len(kept) == 3 and last.path.name in kept and any(n.endswith(".mp4") for n in kept)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_cuts_go_to_the_bucket_and_leave_with_it(tmp_path, monkeypatch):
    bucket = tmp_path / "bucket"
    monkeypatch.setenv("ARCHIVE_DIR", str(bucket))
    monkeypatch.setattr(clip, "KEEP_FILES", 2)
    src = tmp_path / "upload.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10", "-t", "4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], check=True)
    video = ResolvedVideo(LOCAL, "u1", "file", "t", 4.0, [Stream(str(src), {}, "原文件", 180)])
    job = FrameJob("job1", video, None, tmp_path / "job1", count=2)

    gif = asyncio.run(clip.make(job, 0, 2, "gif", clip.Look.of(fps=6, width=160)))
    assert gif.path.is_symlink() and gif.path.resolve().parent == bucket / "job1" / "clips"
    assert gif.path.read_bytes()[:3] == b"GIF"  # served through the symlink
    again = asyncio.run(clip.make(job, 0, 2, "gif", clip.Look.of(fps=6, width=160)))
    assert again.path == gif.path  # cached

    asyncio.run(clip.make(job, 0, 2, "gif", clip.Look.of(fps=8, width=160)))  # a third file: the oldest goes, from the bucket too
    in_bucket = sorted(p.name for p in (bucket / "job1" / "clips").iterdir())
    assert len(in_bucket) == 2 and gif.path.name not in in_bucket

    archive.remove_job(tmp_path / "job1", "clips/*")  # deleting the session empties its part of the bucket
    assert not (bucket / "job1" / "clips").exists() or not any((bucket / "job1" / "clips").iterdir())
