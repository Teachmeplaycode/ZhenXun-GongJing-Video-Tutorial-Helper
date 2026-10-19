"""Every conclusion names its evidence, and every citation is checked before the answer is final.

The answer cites with typed markers (SYSTEM_PROMPT in run.py):

  [画面 01:19]            the original picture at that moment
  [原声 01:13-01:24]      what is said then (speech recognition)
  [画面文字 01:26]         text on screen then (on-screen text recognition)
  [资料 https://…]         an outside source this run actually opened or found
  [推断]                   the model's own reasoning, no direct evidence
  [01:23]                 an untyped moment (older answers): any of the first three will do

When the answer is complete, `check` tests each one against what this video and this run hold:
the moment lies inside the video and outside its unreadable stretches; a picture citation has a
frame near it (or the run looked at that stretch again with view_frames / replay); speech and
on-screen text citations have recognised text overlapping it; a source is a link the run's tools
returned or the user gave. A citation that fails is reported with the reason, and the page shows
it as "缺少可回看的证据" instead of a link, so an invented citation never looks like evidence.
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator

from ..frames import FrameJob
from .tools import parse_time

STAMP = r"\d{1,2}:\d{2}(?::\d{2})?"
MARKER = re.compile(rf"\[(?:(画面文字|画面|原声|资料|推断)(?:\s*([^\[\]]*))?|({STAMP}))\]")
SPAN = re.compile(rf"({STAMP})(?:\s*[-–—~至到]\s*({STAMP}))?")
URL = re.compile(r"https?://[^\s<>()（）\[\]，。；、\"'“”]+")
KINDS = {"画面": "frame", "原声": "speech", "画面文字": "screentext", "资料": "source", "推断": "inference"}
NAMES = {v: k for k, v in KINDS.items()} | {"moment": "时间点"}
LOOKED = {"frames.view", "frames.replay", "frames.motion"}  # tools that look at a stretch again
SLACK = 1.5          # seconds a text citation may sit outside the recognised segment
MIN_FRAME_SLACK = 2.0


def seconds(stamp: str) -> float:
    total = 0.0
    for part in stamp.split(":"):
        total = total * 60 + int(part)
    return total


def parse(text: str) -> list[dict]:
    """The citations in an answer, in order: {marker, kind, start, end, url}."""
    out = []
    for m in MARKER.finditer(text or ""):
        word, rest, bare = m.group(1), (m.group(2) or "").strip(), m.group(3)
        item = {"marker": m.group(0), "kind": KINDS.get(word, "moment"), "start": None, "end": None, "url": ""}
        if bare:
            item["start"] = item["end"] = seconds(bare)
        elif item["kind"] == "source":
            found = URL.search(rest)
            item["url"] = found.group(0).rstrip(".,;:") if found else ""
        elif item["kind"] != "inference":
            span = SPAN.search(rest)
            if span:
                item["start"] = seconds(span.group(1))
                item["end"] = seconds(span.group(2)) if span.group(2) else item["start"]
                if item["end"] < item["start"]:
                    item["start"], item["end"] = item["end"], item["start"]
        out.append(item)
    return out


def _overlaps(segments, start: float, end: float, slack: float) -> bool:
    return any(getattr(s, "start", 0) <= end + slack and getattr(s, "end", 0) >= start - slack for s in segments or [])


def _frame_slack(times: list[float]) -> float:
    """How far from a keyframe a picture citation may be: about half the usual gap between them."""
    if len(times) < 2:
        return MIN_FRAME_SLACK
    gaps = sorted(b - a for a, b in zip(times, times[1:]))
    return max(MIN_FRAME_SLACK, gaps[len(gaps) // 2] * 0.6)


def check(job: FrameJob, items: list[dict], looked: list[tuple[float, float]], urls: set[str]) -> list[dict]:
    """Each citation with ok and, when not, the reason (in the user's words)."""
    duration = float(job.video.duration or 0)
    frames = sorted(s.time for s in job.slots if s.status == "ok")
    slack = _frame_slack(frames)
    gaps = job.coverage().get("missing_ranges") or []
    speech = job.transcript.segments if job.transcript else []
    screen = job.screentext.segments if job.screentext else []
    known = {u.rstrip("/") for u in urls}
    out = []
    for item in items:
        reason = ""
        kind, start, end = item["kind"], item["start"], item["end"]
        if kind == "inference":
            pass
        elif kind == "source":
            if not item["url"]:
                reason = "没有给出资料链接"
            elif item["url"].rstrip("/") not in known:
                reason = "这个链接不是本次检索或打开过的资料"
        elif start is None:
            reason = "没有写明时间点"
        elif start < 0 or end > duration + 1:
            reason = f"超出视频时长（{int(duration // 60):02d}:{int(duration % 60):02d}）"
        else:
            second_look = any(a - 1 <= start and end <= b + 1 for a, b in looked)
            in_gap = any(a <= start and end <= b for a, b in gaps) and not second_look
            near_frame = second_look or (not in_gap and any(abs(t - start) <= slack or start <= t <= end for t in frames))
            said = _overlaps(speech, start, end, SLACK)
            shown = _overlaps(screen, start, end, SLACK)
            if in_gap and kind in ("frame", "moment"):
                reason = "这段视频没有取到画面"
            elif kind == "frame" and not near_frame:
                reason = "这个时间附近没有取到画面"
            elif kind == "speech" and not said:
                reason = "这个时间没有识别到说话内容"
            elif kind == "screentext" and not shown:
                reason = "这个时间没有识别到画面文字"
            elif kind == "moment" and not (near_frame or said or shown):
                reason = "这个时间附近没有画面、语音或文字"
        out.append({**item, "ok": not reason, "reason": reason})
    return out


def summary(checked: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for item in checked:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {"counts": counts, "failed": sum(not i["ok"] for i in checked), "total": len(checked)}


async def with_evidence(events: AsyncIterator[dict], job: FrameJob, question: str = "") -> AsyncIterator[dict]:
    """Pass an answer's events through; just before it completes, check its citations and say how
    they fared (an `evidence.checked` event: {items, summary})."""
    text: list[str] = []
    started: dict[str, str] = {}
    looked: list[tuple[float, float]] = []
    urls: set[str] = {m.group(0).rstrip(".,;:") for m in URL.finditer(question or "")}
    urls.add(job.video.canonical_url)
    async for event in events:
        kind = event.get("type")
        if kind == "assistant.message.delta":
            text.append(event.get("delta", ""))
        elif kind == "tool_call.started":
            started[event.get("call_id", "")] = event.get("tool_name", "")
        elif kind == "tool_call.input" and started.get(event.get("call_id", "")) in LOOKED:
            params = (event.get("input") or {}).get("params") or {}
            a, b = parse_time(params.get("start")), parse_time(params.get("end"))
            if a is not None:
                looked.append((a, b if b is not None and b >= a else a))
        elif kind == "tool_call.output":
            urls |= {m.group(0).rstrip(".,;:") for m in URL.finditer(event.get("stdout") or "")}
        if kind == "run.completed":
            items = check(job, parse("".join(text)), looked, urls)
            if items:
                yield {"type": "evidence.checked", "items": items, "summary": summary(items)}
        yield event
