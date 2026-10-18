"""Sample frames from a resolved link, one independent seek per frame.

Partial results are a normal outcome: every slot ends either `ok` or `missing` (with a reason),
and the job reports coverage plus the missing time ranges instead of failing as a whole.
"""
from __future__ import annotations

import asyncio
import bisect
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from ..video_source import ResolveError, ResolvedVideo, Resolver, Stream
from .grabber import GrabResult, grab_frame

Grab = Callable[[Stream, float, Path], Awaitable[GrabResult]]

# Platforms round durations up (B 站: 21 s for a 20.33 s stream), so the last sample can land
# past the end of the stream. Near the end, a decode error steps back and tries again.
TAIL_WINDOW = 2.0
TAIL_STEP = 1.0
TAIL_RETRIES = 2

REASONS = {
    "trial": "试看限制，无法读取",
    "unreachable": "播放地址均无法读取",
    "timeout": "读取超时",
    "error": "解码失败",
    "interrupted": "抓取被中断（后端重启）",
}


def frame_count(duration: float) -> int:
    """Same density as the in-browser sampler: one frame per ~2 s, 48–64 frames."""
    return min(64, max(48, round(duration / 2))) if duration > 0 else 48


MAX_FRAMES = 128   # keyframes a video may have once shots are filled in (the uniform pass stays 48–64)
MIN_SHOT = 1.5     # seconds; a shorter "shot" is a flash or a fast cut and gets no frame of its own


def shot_fill(cuts: list[float], duration: float, times: list[float], cap: int = MAX_FRAMES,
              min_shot: float = MIN_SHOT) -> list[float]:
    """Moments to add so that every shot has a keyframe: the middle of each shot (between two shot
    changes) that no existing frame falls in. With more such shots than room under `cap`, the longest
    ones get frames first. Returned in time order."""
    if duration <= 0:
        return []
    bounds = [0.0, *sorted(c for c in cuts if 0 < c < duration), duration]
    taken = sorted(times)
    empty = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < min_shot:
            continue
        lo = bisect.bisect_left(taken, a)
        if lo < len(taken) and taken[lo] < b:
            continue  # this shot already has a frame
        empty.append((b - a, round((a + b) / 2, 3)))
    room = max(0, cap - len(times))
    return sorted(t for _, t in sorted(empty, reverse=True)[:room])


def coarse_first(n: int, first: int = 16) -> list[int]:
    """Order slot indices so the first `first` done are spread evenly, then halve the gaps."""
    step = 1 << max(0, math.floor(math.log2(max(1, n / first))))
    order, seen = [], set()
    while step >= 1:
        for i in range(0, n, step):
            if i not in seen:
                seen.add(i)
                order.append(i)
        step //= 2
    return order


@dataclass
class Slot:
    index: int
    time: float
    status: str = "pending"  # pending | ok | missing
    reason: str = ""
    attempts: int = 0


class FrameJob:
    def __init__(self, job_id: str, video: ResolvedVideo, resolver: Resolver, root: Path, *,
                 count: int | None = None, concurrency: int = 6, grab: Grab = grab_frame,
                 max_refreshes: int = 2) -> None:
        self.id = job_id
        self.video = video
        self.resolver = resolver
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.grab = grab
        self.concurrency = concurrency
        n = count or frame_count(video.duration)
        self.slots = [Slot(i, round((i + 0.5) / n * video.duration, 3)) for i in range(n)]
        self.events: list[dict] = []
        self._waiters: set[asyncio.Event] = set()
        self._refresh_lock = asyncio.Lock()
        self._refreshes = 0
        self._max_refreshes = max_refreshes
        self._fallback_added = False
        self._generation = 0  # bumps whenever the address list changes
        self._refused: set[str] = set()  # addresses the CDN refused; skipped by every slot
        self.running = False
        self.filling = False  # keyframes for shots the uniform pass missed are still to come
        self.restored = False  # rebuilt from a saved session: no stream addresses yet
        self.audience: dict = {}  # comments and danmaku read for this video, kept while the job is in memory
        self.transcript = None  # modules.transcript.Transcript, attached by the app
        self.screentext = None  # modules.screentext.ScreenText, attached by the app
        self.created = time.time()

    # ---- events -------------------------------------------------------------------------
    def emit(self, event: dict) -> None:
        event = {"seq": len(self.events), **event}
        self.events.append(event)
        for waiter in list(self._waiters):
            waiter.set()

    async def wait_events(self, since: int, timeout: float = 15) -> list[dict]:
        """Events from `since`; waits briefly when there are none yet (empty list = keep-alive)."""
        if since < len(self.events):
            return self.events[since:]
        waiter = asyncio.Event()
        self._waiters.add(waiter)
        try:
            await asyncio.wait_for(waiter.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            self._waiters.discard(waiter)
        return self.events[since:]

    # ---- state --------------------------------------------------------------------------
    def frame_path(self, index: int) -> Path:
        return self.root / f"{index:03d}.jpg"

    def add_slots(self, times: list[float]) -> list[int]:
        """New pending slots at these moments (indexes continue after the existing ones, so frames
        already taken keep their index); announced with a `slots` event."""
        start = len(self.slots)
        self.slots += [Slot(start + k, round(t, 3)) for k, t in enumerate(times)]
        added = self.slots[start:]
        if added:
            self.emit({"type": "slots", "slots": [{"index": s.index, "time": s.time, "status": s.status, "reason": s.reason}
                                                  for s in added]})
        return [s.index for s in added]

    def in_time_order(self) -> list[Slot]:
        return sorted(self.slots, key=lambda s: s.time)

    def coverage(self) -> dict:
        ok = [s for s in self.slots if s.status == "ok"]
        missing = [s for s in self.slots if s.status == "missing"]
        ordered = self.in_time_order()
        ranges: list[list[float]] = []
        for k, s in enumerate(ordered):
            if s.status != "missing":
                continue
            # the stretch this frame stands for: halfway to its neighbours in time
            start = (ordered[k - 1].time + s.time) / 2 if k else 0.0
            end = (s.time + ordered[k + 1].time) / 2 if k + 1 < len(ordered) else self.video.duration
            if ranges and abs(ranges[-1][1] - start) < 1e-6:
                ranges[-1][1] = end
            else:
                ranges.append([round(start, 2), round(end, 2)])
        reasons: dict[str, int] = {}
        for s in missing:
            reasons[s.reason] = reasons.get(s.reason, 0) + 1
        return {"ok": len(ok), "missing": len(missing), "total": len(self.slots),
                "pending": len(self.slots) - len(ok) - len(missing),
                "missing_ranges": ranges, "reasons": reasons}

    def snapshot(self) -> dict:
        return {
            "job_id": self.id,
            "video": self.video.public(),
            "running": self.running,
            "slots": [{"index": s.index, "time": s.time, "status": s.status, "reason": s.reason} for s in self.slots],
            "coverage": self.coverage(),
            "seq": len(self.events),
        }

    # ---- sampling -----------------------------------------------------------------------
    async def run(self, indexes: list[int] | None = None) -> None:
        targets = set(indexes) if indexes is not None else {s.index for s in self.slots}
        order = [i for i in coarse_first(len(self.slots)) if i in targets]
        self.running = True
        self.emit({"type": "started", "indexes": order})
        sem = asyncio.Semaphore(self.concurrency)

        async def one(i: int) -> None:
            async with sem:
                await self._sample(self.slots[i])

        try:
            await asyncio.gather(*(one(i) for i in order))
        finally:
            self.running = False
            self.emit({"type": "done", "coverage": self.coverage()})

    async def retry_missing(self) -> list[int]:
        indexes = [s.index for s in self.slots if s.status == "missing" and s.reason != "trial"]
        for i in indexes:
            self.slots[i].status, self.slots[i].reason = "pending", ""
        self._refreshes = 0
        return indexes

    async def _sample(self, slot: Slot) -> None:
        playable = self.video.playable_duration
        if playable is not None and slot.time > playable - 0.5:
            return self._finish(slot, "missing", "trial")
        last_kind = "error"
        tried: set[str] = set()
        generation = self._generation
        backoffs = 0
        while True:
            if generation != self._generation:
                # Another slot already refreshed the addresses; try the new ones first.
                generation, tried = self._generation, set()
            candidates = [s for s in self.video.streams
                          if s.url not in tried and s.url not in self._refused and not s.expired()]
            if not candidates:
                if any(s.url in self._refused for s in self.video.streams):
                    last_kind = "forbidden"  # skipped addresses other slots saw refused
                # A decode error at one timestamp is not an address problem.
                if last_kind in ("forbidden", "timeout") and await self._recover(generation):
                    generation, tried = self._generation, set()
                    continue
                return self._finish(slot, "missing", "unreachable" if last_kind == "forbidden" else last_kind)
            stream = candidates[0]
            tried.add(stream.url)
            slot.attempts += 1
            result = await self.grab(stream, slot.time, self.frame_path(slot.index))
            if result.ok:
                return self._finish(slot, "ok")
            if result.kind == "forbidden":
                self._refused.add(stream.url)
            elif (result.kind == "error" and backoffs < TAIL_RETRIES
                  and slot.time > self.video.duration - TAIL_WINDOW and slot.time > TAIL_STEP):
                # Past the real end of the stream: read a little earlier, same address.
                backoffs += 1
                slot.time = round(slot.time - TAIL_STEP, 3)
                tried.discard(stream.url)
                continue
            last_kind = result.kind

    async def _recover(self, seen_generation: int) -> bool:
        """All known addresses failed: re-acquire them, then fall back to permissive ones."""
        async with self._refresh_lock:
            if self._generation != seen_generation:
                return True  # refreshed while we waited for the lock
            if self._refreshes < self._max_refreshes:
                self._refreshes += 1
                try:
                    self.video = await self.resolver.refresh(self.video)
                    self._fallback_added = False
                    self._generation += 1
                    self.emit({"type": "status", "message": "播放地址已重新获取"})
                    return True
                except ResolveError as exc:
                    self.emit({"type": "status", "message": f"重新获取地址失败：{exc.message}"})
            if not self._fallback_added:
                self._fallback_added = True
                extra = await self.resolver.fallback_streams(self.video)
                if extra:
                    self.video.streams = self.video.streams + extra
                    self._generation += 1
                    self.emit({"type": "status", "message": "已切换到备用播放地址"})
                    return True
            return False

    def _finish(self, slot: Slot, status: str, reason: str = "") -> None:
        slot.status, slot.reason = status, reason
        if status == "ok":
            self.emit({"type": "frame", "index": slot.index, "time": slot.time})
        else:
            self.emit({"type": "missing", "index": slot.index, "time": slot.time,
                       "reason": reason, "message": REASONS.get(reason, reason)})
