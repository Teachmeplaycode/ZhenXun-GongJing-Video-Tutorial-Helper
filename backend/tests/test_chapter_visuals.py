"""Chapter summaries use real frame evidence when speech and OCR do not cover a chapter."""
import asyncio
import base64
import re

import cv2
import numpy as np
import pytest

from modules.chapters import run_chapters


def picture(tmp_path, name="frame.jpg", width=640, height=360):
    path = tmp_path / name
    assert cv2.imwrite(str(path), np.full((height, width, 3), 90, np.uint8))
    return path


def images(messages):
    content = messages[1]["content"]
    if isinstance(content, str):
        return []
    return [part for part in content if part["type"] == "image_url"]


def test_visual_only_chapter_sends_a_timed_frame_to_the_model(tmp_path):
    frame = picture(tmp_path)
    seen = []

    async def complete(messages):
        seen.append(messages)
        return "连接节点|画面显示两个节点通过连线连接。\n总摘要|展示节点连接操作。"

    result = asyncio.run(run_chapters(tmp_path, [], [], None, 30,
                                     pictures=[(12.5, frame)], complete=complete))
    content = seen[0][1]["content"]
    assert isinstance(content, list)
    assert len(images(seen[0])) == 1
    assert any("第 1 章" in part.get("text", "") and "12.50 秒" in part.get("text", "")
               for part in content)
    encoded = images(seen[0])[0]["image_url"]["url"]
    assert encoded.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(encoded.split(",", 1)[1]) == frame.read_bytes()
    assert result["chapters"][0]["summary"] == "画面显示两个节点通过连线连接。"
    assert result["generated_chapters"] == [0]


def test_long_video_sends_at_most_two_representative_frames_per_chapter(tmp_path):
    frame = picture(tmp_path)
    seen = []
    # Dense frames across an hour-long video, including exact chapter boundaries.
    pictures = [(float(t), frame) for t in range(0, 3601, 10)]

    async def complete(messages):
        seen.append(messages)
        return "\n".join(f"章节{i}|画面摘要{i}" for i in range(1, 16))

    result = asyncio.run(run_chapters(tmp_path, [], [], None, 3600,
                                     pictures=pictures, complete=complete))
    content = seen[0][1]["content"]
    assert len(images(seen[0])) == 30
    selected = {}
    for i, part in enumerate(content):
        if part["type"] != "image_url":
            continue
        label = content[i - 1]["text"]
        match = re.search(r"第 (\d+) 章.*?([\d.]+) 秒", label)
        assert match, "Every picture needs a chapter number and real timestamp."
        chapter_index, timestamp = int(match[1]) - 1, float(match[2])
        chapter = result["chapters"][chapter_index]
        assert chapter["start"] <= timestamp < chapter["end"] or timestamp == 3600
        selected.setdefault(chapter_index, []).append(timestamp)
    assert len(selected) == 15
    for chapter_index, timestamps in selected.items():
        chapter = result["chapters"][chapter_index]
        assert len(set(timestamps)) == 2
        # Dense evidence should represent separate parts, not two neighboring frames.
        assert max(timestamps) - min(timestamps) >= (chapter["end"] - chapter["start"]) / 4


def test_visual_payload_limits_width_without_upscaling_small_frames(tmp_path):
    large = picture(tmp_path, "large.jpg", 1920, 1080)
    small = picture(tmp_path, "small.jpg", 320, 180)
    seen = []

    async def complete(messages):
        seen.append(messages)
        return ""

    asyncio.run(run_chapters(tmp_path, [], [], None, 60,
                             pictures=[(10, large), (40, small)], complete=complete))
    sizes = []
    for part in images(seen[0]):
        raw = base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
        sizes.append(cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR).shape[:2])
    assert sizes == [(360, 640), (180, 320)]


@pytest.mark.parametrize("failure", ["exception", "missing_rows"])
def test_model_failure_distinguishes_visual_evidence_from_missing_content(tmp_path, failure):
    frame = picture(tmp_path)

    async def complete(messages):
        if failure == "exception":
            raise RuntimeError("model unavailable")
        return "第一章|已有摘要"

    result = asyncio.run(run_chapters(tmp_path, [(0, 29, "可用语音文字")], [], None, 90,
                                     pictures=[(45, frame)], complete=complete))
    assert result["chapters"][0]["summary"] == ("可用语音文字" if failure == "exception" else "已有摘要")
    assert result["chapters"][1]["summary"] == "画面摘要暂未生成"
    assert result["chapters"][2]["summary"] == "当前内容不足，待补充"
    assert all("没有语音和画面文字" not in chapter["summary"] for chapter in result["chapters"])
    assert result["needs_retry"] is True
    assert result["incomplete_chapters"] == ([0, 1] if failure == "exception" else [1])
    assert result["generated_chapters"] == ([] if failure == "exception" else [0])
    assert "暂未" in result["message"]


def test_missing_evidence_cannot_be_filled_with_an_invented_model_summary(tmp_path):
    calls = []

    async def complete(messages):
        calls.append(messages)
        return "操作演示|展示了节点连接。\n总摘要|展示节点连接。"

    result = asyncio.run(run_chapters(tmp_path, [], [], None, 30, complete=complete))
    assert result["chapters"][0]["title"] == "第 1 章"
    assert result["chapters"][0]["summary"] == "当前内容不足，待补充"
    assert "节点连接" not in result["summary"]
    assert calls == []
    assert result["needs_retry"] is False
    assert result["incomplete_chapters"] == []
    assert result["generated_chapters"] == []


def test_missing_and_corrupt_frames_keep_the_text_only_message_contract(tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"not an image")

    async def complete(messages):
        assert isinstance(messages[1]["content"], str)
        return "文字说明|根据语音生成的摘要"

    result = asyncio.run(run_chapters(tmp_path, [(0, 25, "有效语音")], [], None, 30,
                                     pictures=[(10, tmp_path / "missing.jpg"), (20, broken)], complete=complete))
    assert result["chapters"][0]["summary"] == "根据语音生成的摘要"


@pytest.mark.parametrize("output", ["仅有标题", "|仅有摘要", ""])
def test_incomplete_model_output_can_recover_with_the_same_evidence(tmp_path, output):
    frame = picture(tmp_path)
    responses = iter([output, "完整标题|完整画面摘要"])

    async def complete(messages):
        return next(responses)

    first = asyncio.run(run_chapters(tmp_path, [], [], None, 30,
                                    pictures=[(10, frame)], complete=complete))
    assert first["status"] == "done" and first["chapters"]
    assert first["needs_retry"] is True and first["incomplete_chapters"] == [0]
    second = asyncio.run(run_chapters(tmp_path, [], [], None, 30,
                                     pictures=[(10, frame)], complete=complete))
    assert second["needs_retry"] is False and second["incomplete_chapters"] == []
    assert second["generated_chapters"] == [0]
    assert second["chapters"][0]["summary"] == "完整画面摘要"


def test_missing_model_configuration_does_not_request_automatic_retry(tmp_path):
    frame = picture(tmp_path)
    result = asyncio.run(run_chapters(tmp_path, [], [], None, 30, pictures=[(10, frame)]))
    assert result["chapters"][0]["summary"] == "画面摘要暂未生成"
    assert result["needs_retry"] is False
    assert result["incomplete_chapters"] == [0]
    assert result["generated_chapters"] == []
