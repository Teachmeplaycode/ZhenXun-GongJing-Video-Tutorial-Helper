"""Build a chapter list (titles + one-line summaries) for a link job, cached as chapters.json.

Splitting is pure (split.py); titles and summaries come from the chat model when one is
available, otherwise from each chapter's transcript text. Cached like cuts.json:
{"status": "done"|"failed"|"running"|"empty"|"unavailable", "chapters": [{start, end, title,
summary}], "message": "..."}.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from . import split

FILE = "chapters.json"
MAX_TITLE = 20
MAX_SUMMARY = 60
# pending · running · done · empty (nothing to split) · unavailable · failed
FINISHED = {"done", "empty", "unavailable"}


@dataclass
class Chapter:
    start: float
    end: float
    title: str
    summary: str

    def as_dict(self) -> dict:
        return {"start": round(self.start, 2), "end": round(self.end, 2),
                "title": self.title, "summary": self.summary}


@dataclass
class Chapters:
    status: str = "pending"
    message: str = ""
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.status == "running"

    def summary(self) -> dict:
        return {"status": self.status, "message": self.message, "count": len(self.chapters)}

    def as_dict(self) -> dict:
        return {**self.summary(), "chapters": [c.as_dict() for c in self.chapters]}


def load(root: Path) -> dict | None:
    try:
        return json.loads((root / FILE).read_text())
    except (OSError, ValueError):
        return None


def save(root: Path, status: str, chapters: list[Chapter] | None = None, message: str = "", *, summary: str = "") -> dict:
    record = {"status": status, "chapters": [c.as_dict() for c in (chapters or [])], "message": message, "summary": summary}
    return write_record(root, record)


def write_record(root: Path, record: dict) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / FILE).write_text(json.dumps(record, ensure_ascii=False))
    return record


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


def fallback_title(i: int, text: str) -> str:
    return _clip(text, MAX_TITLE) or f"第 {i + 1} 章"


def fallback_summary(text: str) -> str:
    return _clip(text, MAX_SUMMARY) or "（这一段没有语音和画面文字）"


def _rows(items: Iterable | None) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for s in items or ():
        if isinstance(s, tuple | list):
            start, end = float(s[0]), float(s[1])
            text = str(s[2]) if len(s) > 2 else ""
        else:
            start, end = float(s.start), float(s.end)
            text = str(getattr(s, "text", ""))
        out.append((start, end, text))
    return out


def _chapter_text(transcript, screen, start: float, end: float) -> str:
    parts: list[str] = []
    for s_start, s_end, s_text in _rows(transcript):
        if s_end > start and s_start < end:
            parts.append(s_text)
    for s_start, s_end, s_text in _rows(screen):
        if s_end > start and s_start < end:
            parts.append(s_text)
    return " ".join(parts)


# A model call that returns the full text (deltas joined). Injected so tests can stub it.
Completer = Callable[[list[dict]], Awaitable[str]]


def _messages(chunks: list[tuple[int, float, float, str]]) -> list[dict]:
    """Ask the model for a title and one-line summary per chapter, one `title|summary` line each."""
    body = "\n".join(f"{i + 1}. [{round(a, 1)}–{round(b, 1)}s] {txt[:200]}"
                     for i, a, b, txt in chunks)
    return [
        {"role": "system",
         "content": "你给视频章节起标题和摘要。每章一行，格式：标题|摘要。标题不超过 20 字，摘要是一句话不超过 60 字。章节行之后追加一行：总摘要|一段话概括整段视频，不超过300字。不要多余的话。"},
        {"role": "user",
         "content": f"以下是视频各章节的起止时间和文字内容，给每章起标题和摘要：\n{body}"},
    ]


def _parse(lines: str, n: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in (lines or "").splitlines():
        line = line.strip()
        if not line:
            continue
        title, sep, summary = line.partition("|")
        out.append((title.strip(), summary.strip() if sep else ""))
    while len(out) < n:
        out.append(("", ""))
    return out[:n]


async def run_chapters(root: Path, transcript, screen, cuts_record: dict | None,
                       duration: float, *, complete: Completer | None = None, cache: bool = True) -> dict:
    """Split, title and summarise; cache to chapters.json. Never raises."""
    cuts = (cuts_record or {}).get("cuts") or []
    spans = split.segment(duration, cuts, transcript or [], screen or [])
    if not spans:
        record = {"status": "empty", "chapters": [], "message": "视频时长未知，无法切分章节", "summary": ""}
        return write_record(root, record) if cache else record
    chunks = [(i, start, end, _chapter_text(transcript, screen, start, end))
              for i, (start, end) in enumerate(spans)]
    titles: list[tuple[str, str]] = [("", "")] * len(chunks)
    summary = ""
    if complete is not None:
        try:
            output = await complete(_messages(chunks))
            rows = output.splitlines()
            summary_rows = [line.partition("|")[2].strip() for line in rows if line.strip().startswith("总摘要|")]
            summary = _clip(" ".join(summary_rows), 300)
            titles = _parse("\n".join(line for line in rows if not line.strip().startswith("总摘要|")), len(chunks))
        except Exception:  # noqa: BLE001 — a model failure falls back to text-derived titles
            titles = [("", "")] * len(chunks)
    chapters = [Chapter(start, end, title or fallback_title(i, text), summary or fallback_summary(text))
                for (i, start, end, text), (title, summary) in zip(chunks, titles)]
    record = {"status": "done", "chapters": [c.as_dict() for c in chapters],
              "message": f"已生成 {len(chapters)} 个章节",
              "summary": summary or _clip(" ".join(c.summary for c in chapters), 300)}
    return write_record(root, record) if cache else record
