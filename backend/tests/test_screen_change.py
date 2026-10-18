"""Frames whose picture hasn't changed reuse the text read from the last one; a small new stroke still counts."""
import asyncio

import cv2
import numpy as np

from modules.frames import FrameJob
from modules.screentext import change
from modules.screentext import task as screen
from modules.screentext.task import ScreenText
from modules.video_source import ResolvedVideo, Stream


def frame(tmp_path, name, draw=None, noise=0, seed=0):
    img = np.full((540, 960, 3), 250, np.uint8)
    cv2.putText(img, "lim a_n = a", (80, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (20, 20, 20), 4)
    if draw:
        draw(img)
    if noise:
        img = np.clip(img.astype(int) + np.random.default_rng(seed).integers(-noise, noise + 1, img.shape), 0, 255).astype(np.uint8)
    path = tmp_path / name
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return change.signature(path)


def test_the_same_picture_and_its_compression_noise_are_not_a_change(tmp_path):
    a = frame(tmp_path, "a.jpg")
    assert not change.changed(a, frame(tmp_path, "b.jpg"))
    assert not change.changed(a, frame(tmp_path, "c.jpg", noise=6, seed=1))


def test_a_small_new_stroke_is_a_change(tmp_path):
    # a teacher adds the little 3 of a cube root: a few dozen pixels
    a = frame(tmp_path, "a.jpg")
    b = frame(tmp_path, "b.jpg", draw=lambda img: cv2.putText(img, "3", (60, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2))
    assert change.changed(a, b)


def test_a_new_subtitle_line_is_a_change(tmp_path):
    a = frame(tmp_path, "a.jpg", draw=lambda img: cv2.putText(img, "first line", (300, 500), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2))
    b = frame(tmp_path, "b.jpg", draw=lambda img: cv2.putText(img, "next line!", (300, 500), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2))
    assert change.changed(a, b) and change.changed(None, b)


def test_recognition_runs_once_per_new_picture(tmp_path):
    video = ResolvedVideo("bilibili", "BV1", "u", "t", 6.0, [Stream("https://a/480", {}, "s", 480)])
    job = FrameJob("job1", video, None, tmp_path / "job1", count=2)
    job.screentext = ScreenText()
    stroke = lambda img: cv2.putText(img, "3", (60, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2)  # noqa: E731

    async def read(stream, folder, timeout):
        folder.mkdir(parents=True, exist_ok=True)
        for i, draw in enumerate([None, None, None, stroke, stroke, stroke], start=1):
            frame(folder, f"{i:05d}.jpg", draw=draw)
        return screen.GrabResult(True)

    seen = []

    def recognize(path):
        seen.append(path.rsplit("/", 1)[1])
        return [screen.ocr.Line("lim a_n = a", 0.9, 0.1, 0.3, 0.6, 0.1)]

    asyncio.run(screen.run_screentext(job, read=read, recognize=recognize))
    assert seen == ["00001.jpg", "00004.jpg"] and job.screentext.skipped == 4
    assert job.screentext.status == "done" and job.screentext.segments[0].text == "lim a_n = a"
