"""A screenshot is matched to the frames that look most like it, and the model is told which."""
import asyncio

import cv2
import numpy as np

from modules.agent import locate, run
from modules.screentext import ScreenText
from modules.screentext.merge import Caption


class Slot:
    def __init__(self, index, time):
        self.index, self.time, self.status = index, time, "ok"


def picture(path, seed):
    rng = np.random.default_rng(seed)
    image = cv2.resize(rng.integers(0, 255, (9, 16, 3), dtype=np.uint8), (320, 180), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(path), image)
    return path


def test_words_pair_chinese_and_lower_latin():
    assert locate.words("数据验证 Data > Validation") == {"数据", "据验", "验证", "data", "validation"}


def test_the_frame_sharing_the_screens_rare_words_wins(tmp_path):
    slots = [Slot(i, i * 10.0) for i in range(6)]
    for s in slots:
        picture(tmp_path / f"{s.index}.jpg", s.index)
    captions = [Caption(s.time, s.time + 1, "开始 插入 公式", "top") for s in slots]
    captions.append(Caption(30, 31, "数据验证 允许 序列 来源", "middle"))
    shot = picture(tmp_path / "shot.jpg", 99)
    found = locate.rank("开始 插入 数据验证 序列 来源", shot, slots, lambda i: tmp_path / f"{i}.jpg", captions)
    assert found[0].slot.time == 30.0 and "验证" in found[0].shared
    assert all(abs(a.slot.time - b.slot.time) >= locate.APART for a in found for b in found if a is not b)


def test_without_text_the_picture_decides_and_nothing_close_is_nothing(tmp_path):
    slots = [Slot(i, i * 10.0) for i in range(4)]
    for s in slots:
        picture(tmp_path / f"{s.index}.jpg", s.index)
    path = lambda i: tmp_path / f"{i}.jpg"
    assert locate.rank("", tmp_path / "2.jpg", slots, path, [])[0].slot.index == 2
    assert locate.rank("", picture(tmp_path / "other.jpg", 42), slots, path, []) == []


def test_the_model_sees_the_matched_frames_next_to_the_screenshot(tmp_path, monkeypatch):
    from tests.test_replay import job_for

    job = job_for(tmp_path)
    job.screentext = ScreenText("done", "", [])
    shot = picture(tmp_path / "shot.jpg", 1)
    match = locate.Match(Slot(1, 95.0), 0.8, 0.7, 0.9, ["验证", "序列"])
    monkeypatch.setattr(run, "locate_shots", lambda job, images: asyncio.sleep(0, {str(shot): [match]}))
    parts = run.attached_parts([shot], {str(shot): [match]})
    assert parts[-1]["text"].startswith("按画面文字和画面相似度自动比对，和你的截图 1 最像的视频画面：帧")
    assert "01:35（共同文字：验证、序列）" in parts[-1]["text"]
    assert run.attached_parts([shot])[-1]["type"] == "image_url"
