"""Tools the model can call while answering: search or read the transcript, or look closer at a time range.

Each tool returns text for the model, optional images (sent in a following user message, since tool
results are text-only), and a short summary for the trace card.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

from modules.frames import FrameJob
from modules.frames.grabber import grab_frame
from modules.video_source import ResolveError

MAX_VIEW = 6          # frames per view_frames call
MAX_READ_CHARS = 4000
MAX_HITS = 12


def clock(seconds: float) -> str:
    t = max(0, int(seconds))
    return f"{t // 60:02d}:{t % 60:02d}"


def parse_time(value) -> float | None:
    """Seconds from a number or "mm:ss" / "hh:mm:ss" (models use both)."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        parts = value.strip().split(":")
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            return None
        seconds = 0.0
        for n in numbers:
            seconds = seconds * 60 + n
        return seconds
    return None


DEFINITIONS = [
    {"type": "function", "function": {
        "name": "search_transcript",
        "description": "在视频的语音转写里搜索关键词，返回包含这些词的句子和时间点。用来找某个话题、某句话在什么时候说的。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "关键词，多个词用空格分开"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_transcript",
        "description": "读取某个时间段内完整的语音转写。",
        "parameters": {"type": "object", "properties": {
            "start": {"type": "string", "description": "开始时间，秒数或 mm:ss"},
            "end": {"type": "string", "description": "结束时间，秒数或 mm:ss"}}, "required": ["start", "end"]}}},
    {"type": "function", "function": {
        "name": "view_frames",
        "description": f"在某个时间段内均匀截取更多画面来看细节（最多 {MAX_VIEW} 张）。已有的关键帧间隔太大、看不清某段发生了什么时使用。",
        "parameters": {"type": "object", "properties": {
            "start": {"type": "string", "description": "开始时间，秒数或 mm:ss"},
            "end": {"type": "string", "description": "结束时间，秒数或 mm:ss"},
            "count": {"type": "integer", "description": f"截取几张，1 到 {MAX_VIEW}"}}, "required": ["start", "end"]}}},
]

TRACE_NAMES = {"search_transcript": "transcript.search", "read_transcript": "transcript.read_range", "view_frames": "frames.view"}


@dataclass
class ToolResult:
    text: str
    summary: str
    count: int = 0
    images: list[tuple[str, Path]] = field(default_factory=list)  # (label, jpg)
    error: bool = False


class AgentTools:
    def __init__(self, job: FrameJob, grab=None):
        self.job = job
        self.grab = grab or grab_frame
        self.refreshed = False

    async def run(self, name: str, args: dict) -> ToolResult:
        handler = {"search_transcript": self.search_transcript, "read_transcript": self.read_transcript,
                   "view_frames": self.view_frames}.get(name)
        if handler is None:
            return ToolResult(f"没有名为 {name} 的工具", "未知工具", error=True)
        try:
            return await handler(**{k: v for k, v in args.items() if k in ("query", "start", "end", "count")})
        except TypeError as exc:
            return ToolResult(f"参数不正确：{exc}", "参数错误", error=True)

    # ---- transcript -----------------------------------------------------------------------
    def _segments(self):
        t = self.job.transcript
        return t.segments if t is not None else []

    async def search_transcript(self, query: str = "") -> ToolResult:
        segments = self._segments()
        if not segments:
            return ToolResult("这个视频没有语音转写。", "没有转写")
        terms = [t for t in re.split(r"[\s,，、。;；]+", query.strip()) if t]
        if not terms:
            return ToolResult("请给出要搜索的关键词。", "没有关键词", error=True)
        scored = [(sum(t.lower() in s.text.lower() for t in terms), s) for s in segments]
        hits = sorted((s for score, s in scored if score), key=lambda s: -sum(t.lower() in s.text.lower() for t in terms))[:MAX_HITS]
        if not hits:
            return ToolResult(f"转写里没有找到「{' '.join(terms)}」。注意转写可能有同音错字，可以换个说法再搜。", "0 处")
        hits.sort(key=lambda s: s.start)
        lines = [f"[{clock(s.start)}] {s.text}" for s in hits]
        return ToolResult("\n".join(lines), f"{len(hits)} 处", len(hits))

    async def read_transcript(self, start=0, end=None) -> ToolResult:
        segments = self._segments()
        if not segments:
            return ToolResult("这个视频没有语音转写。", "没有转写")
        a, b = self._range(start, end)
        picked = [s for s in segments if s.end >= a and s.start <= b]
        text, used = [], 0
        for s in picked:
            line = f"[{clock(s.start)}] {s.text}"
            if used + len(line) > MAX_READ_CHARS:
                text.append(f"（过长，只读到 {clock(s.start)} 之前）")
                break
            text.append(line)
            used += len(line)
        return ToolResult("\n".join(text) or f"{clock(a)}–{clock(b)} 之间没有语音。", f"{clock(a)}–{clock(b)} · {len(picked)} 句", len(picked))

    # ---- frames ---------------------------------------------------------------------------
    def _range(self, start, end) -> tuple[float, float]:
        duration = self.job.video.duration
        a = parse_time(start) or 0.0
        b = parse_time(end)
        b = duration if b is None else b
        a, b = max(0.0, min(a, duration)), max(0.0, min(b, duration))
        return (a, b) if a <= b else (b, a)

    async def _grab_at(self, t: float, out: Path) -> bool:
        for stream in [s for s in self.job.video.streams if not s.expired()]:
            result = await self.grab(stream, t, out)
            if result.ok:
                return True
            if result.kind != "forbidden":
                return False
        return False

    async def _refresh(self) -> bool:
        """Re-acquire stream addresses once per answer (expired, or a session restored without them)."""
        if self.refreshed or self.job.resolver is None:
            return False
        self.refreshed = True
        try:
            self.job.video = await self.job.resolver.refresh(self.job.video)
            self.job.restored = False
            return True
        except ResolveError:
            return False

    async def view_frames(self, start=0, end=None, count=4) -> ToolResult:
        a, b = self._range(start, end)
        try:
            n = max(1, min(MAX_VIEW, int(count)))
        except (TypeError, ValueError):
            n = 4
        times = [round(a + (b - a) * (i + 0.5) / n, 2) for i in range(n)] if b > a else [a]
        folder = self.job.root / "extra"
        folder.mkdir(parents=True, exist_ok=True)
        paths = [folder / f"{int(t * 100):08d}.jpg" for t in times]

        async def fetch(t: float, p: Path) -> bool:
            return p.is_file() or await self._grab_at(t, p)  # earlier calls may have the frame already

        ok = await asyncio.gather(*(fetch(t, p) for t, p in zip(times, paths)))
        if not all(ok) and await self._refresh():
            ok = await asyncio.gather(*(fetch(t, p) for t, p in zip(times, paths)))
        images = [(f"画面 · {clock(t)}", p) for t, p, good in zip(times, paths, ok) if good]
        note = ""
        if not images:
            # The source is gone (an upload already deleted) or unreachable: use the sampled frames in range.
            nearby = [s for s in self.job.slots if s.status == "ok" and a - 1 <= s.time <= b + 1
                      and self.job.frame_path(s.index).is_file()][:MAX_VIEW]
            images = [(f"画面 · {clock(s.time)}", self.job.frame_path(s.index)) for s in nearby]
            note = "无法重新读取视频，以下是这一段已有的关键帧" if images else "无法读取这一段的画面"
        stamps = "、".join(label.split(" · ")[1] for label, _ in images)
        text = f"{note + '：' if note else ''}{clock(a)}–{clock(b)} 共 {len(images)} 张画面（{stamps}），见下一条消息。" if images else note
        return ToolResult(text, f"{clock(a)}–{clock(b)} · {len(images)} 张", len(images), images, error=not images)
