"""Image posts (图集, screenshots): a set of pictures instead of a video.

No time axis, no sound, no shots: each picture is one "frame" (slot i, time i + 0.5 so it keeps the
usual ordering), downloaded whole instead of seeked in a stream, and its text is read once. Speech,
shot changes and chapters are marked as not applying. A video's sampling, transcription and cut
detection never run for these.

The pictures come from alcedo (image posts on 小红书, 抖音图文, 微博, X …: `extra["images"]` holds
each address and the headers its CDN wants) or from an upload (`extra["images"]` holds local paths).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import httpx
import numpy as np

from ..screentext.merge import build
from . import FrameJob, cuts

KIND = "images"
MAX_IMAGES = 60
MAX_BYTES = 25 << 20       # per picture
MAX_WIDTH = 1600           # wider pictures are shrunk to this; long screenshots keep their height
PARALLEL = 4


def is_images(video) -> bool:
    return (getattr(video, "extra", None) or {}).get("kind") == KIND


def image_label(index: int, total: int | None = None) -> str:
    return f"第 {index + 1} 张" + (f"（共 {total} 张）" if total else "")


def normalise(data: bytes, out: Path) -> bool:
    """Decode any picture OpenCV reads (JPEG, PNG, WebP, BMP …) and save it as a JPEG frame."""
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return False
    h, w = image.shape[:2]
    if w > MAX_WIDTH:
        image = cv2.resize(image, (MAX_WIDTH, round(h * MAX_WIDTH / w)), interpolation=cv2.INTER_AREA)
    out.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(out), image, [cv2.IMWRITE_JPEG_QUALITY, 90]))


async def _download(client: httpx.AsyncClient, item: dict) -> bytes | None:
    if item.get("path"):
        path = Path(item["path"])
        return path.read_bytes() if path.is_file() and path.stat().st_size <= MAX_BYTES else None
    try:
        async with client.stream("GET", item["url"], headers=item.get("headers") or {}) as r:
            if r.status_code != 200:
                return None
            chunks, size = [], 0
            async for chunk in r.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError:
        return None


async def fetch(job: FrameJob, indexes: list[int] | None = None) -> None:
    """Every picture (or just `indexes`) into its frame file, announced like sampled frames."""
    items = job.video.extra.get("images") or []
    targets = [s for s in job.slots if indexes is None or s.index in indexes]
    job.running = True
    job.emit({"type": "started", "indexes": [s.index for s in targets]})
    gate = asyncio.Semaphore(PARALLEL)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async def one(slot):
                async with gate:
                    item = items[slot.index] if slot.index < len(items) else {}
                    data = await _download(client, item) if item else None
                    ok = bool(data) and await asyncio.to_thread(normalise, data, job.frame_path(slot.index))
                    job._finish(slot, "ok" if ok else "missing", "" if ok else "error")
            await asyncio.gather(*(one(s) for s in targets))
    finally:
        job.running = False
        job.emit({"type": "done", "coverage": job.coverage()})


async def read_text(job: FrameJob, recognize=None) -> None:
    """The text on each picture, read once, as captions keyed to the picture (start = its index)."""
    from ..screentext import ocr
    state = job.screentext
    recognize = recognize or (ocr.recognize if ocr.available() else None)
    if recognize is None:
        state.status, state.message = "unavailable", "本机不支持图片文字识别"
        job.emit({"type": "screentext", **state.summary()})
        return
    state.status = "running"
    job.emit({"type": "screentext", **state.summary(), "message": "正在识别图片里的文字"})
    try:
        ok = [s for s in job.in_time_order() if s.status == "ok" and job.frame_path(s.index).is_file()]
        lines = await asyncio.to_thread(lambda: [recognize(str(job.frame_path(s.index))) for s in ok])
        state.segments = build([(float(s.index), found) for s, found in zip(ok, lines)], 1.0)
        state.status = "done" if state.segments else "empty"
        state.message = f"识别到 {len(state.segments)} 段图片文字" if state.segments else "图片上没有识别到文字"
    except Exception as exc:  # noqa: BLE001 — reported, not raised
        state.status, state.message = "failed", f"图片文字识别失败：{type(exc).__name__}"
    job.emit({"type": "screentext", **state.summary()})


async def process(job: FrameJob) -> None:
    """The whole import of an image post: pictures, their text; speech and shots don't apply."""
    job.transcript.status, job.transcript.message = "none", "图集没有语音"
    job.emit({"type": "transcript", **job.transcript.summary()})
    cuts.save(job.root, "unavailable", message="图集没有镜头切换")
    await fetch(job)
    await read_text(job)
