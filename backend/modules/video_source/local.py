"""Uploaded files as a video source: the same ResolvedVideo contract, with the file path as the stream.

The upload is kept only while frames and speech are being read, then deleted, so a local session
cannot re-acquire its source: `refresh` refuses instead of resolving again.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .base import ResolveError, ResolvedVideo, Resolver, Stream

PLATFORM = "local"


async def probe_file(path: Path, timeout: float = 30) -> dict:
    args = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)]
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except FileNotFoundError:
        raise ResolveError("upstream", "未安装 ffmpeg（ffprobe），无法读取视频") from None
    except asyncio.TimeoutError:
        raise ResolveError("upstream", "读取视频信息超时") from None
    try:
        return json.loads(out or b"{}")
    except ValueError:
        return {}


async def resolve_file(path: Path, name: str) -> ResolvedVideo:
    info = await probe_file(path)
    kinds = {s.get("codec_type") for s in info.get("streams") or []}
    duration = float((info.get("format") or {}).get("duration") or 0)
    if "video" not in kinds:
        raise ResolveError("not_video", "无法识别这个文件里的视频画面，请换一个视频文件")
    if duration <= 0:
        raise ResolveError("not_video", "无法读取视频时长，文件可能已损坏")
    stream = Stream(str(path), {}, "local-file")
    return ResolvedVideo(
        platform=PLATFORM, video_id=name, canonical_url=f"local://{name}", title=Path(name).stem or name,
        duration=duration, streams=[stream], audio_streams=[stream] if "audio" in kinds else [],
    )


class LocalResolver(Resolver):
    """Not matched by URL; attached to upload jobs so sampling's recovery path has a resolver."""

    platform = PLATFORM

    def matches(self, url: str) -> bool:
        return False

    async def refresh(self, video: ResolvedVideo) -> ResolvedVideo:
        raise ResolveError("local_file", "本地上传的视频处理完已删除，不能再次读取，请重新上传")
