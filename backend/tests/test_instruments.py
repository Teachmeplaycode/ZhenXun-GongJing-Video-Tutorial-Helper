"""Perception instruments on synthetic frames whose motion is known."""
import math

import cv2
import numpy as np

from modules.frames import instruments


def texture(h=240, w=640, seed=0):
    rng = np.random.default_rng(seed)
    img = cv2.resize(rng.integers(0, 255, (h // 8, w // 8, 3), dtype=np.uint8), (w, h), interpolation=cv2.INTER_CUBIC)
    return cv2.GaussianBlur(img, (3, 3), 0)


def write(frames, folder):
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, f in enumerate(frames, 1):
        p = folder / f"{i:04d}.jpg"
        cv2.imwrite(str(p), f)
        paths.append(p)
    return paths


def test_a_steady_pan_is_read_as_a_pan(tmp_path):
    wide = texture(w=1200)
    frames = [wide[:, 400 + 6 * i: 400 + 6 * i + 320] for i in range(40)]  # the view slides right: content moves left
    r = instruments.analyze(write(frames, tmp_path / "f"), 0.0, 10.0, tmp_path / "out")
    assert r.camera.startswith("镜头向右平移")


def test_a_still_camera_with_one_moving_thing(tmp_path):
    back = texture(w=320)
    frames = []
    for i in range(60):  # a square swings left and right in the lower right, period 1 s at 10 fps
        f = back.copy()
        x = int(220 + 40 * math.sin(2 * math.pi * i / 10))
        cv2.rectangle(f, (x, 150), (x + 30, 190), (255, 255, 255), -1)
        frames.append(f)
    r = instruments.analyze(write(frames, tmp_path / "f"), 2.0, 10.0, tmp_path / "out")
    assert r.camera.startswith("基本静止") or r.camera.startswith("轻微晃动")
    assert "右" in r.region and "局部" in r.region
    assert r.period is not None and 0.4 <= r.period <= 1.1  # one swing, or half of one (two peaks per cycle)
    assert [label.split("（")[0] for label, _ in r.images] == ["运动热力图", "运动轨迹叠影"]
    assert (tmp_path / "out" / "heat.jpg").is_file()


def test_cuts_are_skipped_not_taken_for_camera_motion(tmp_path):
    a, b = texture(seed=1, w=320), texture(seed=2, w=320)
    frames = [a] * 15 + [b] * 15
    r = instruments.analyze(write(frames, tmp_path / "f"), 0.0, 10.0, tmp_path / "out")
    assert "切镜" in r.camera and "平移" not in r.camera


def test_bar_shows_levels():
    assert instruments.bar([0, 0.5, 1]) == "▁▄█"
