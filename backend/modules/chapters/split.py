"""Split a video into chapters using shot changes, speech pauses and on-screen text shifts.

Pure functions over the transcript, on-screen text, shot changes and duration — no I/O, no
model — so the splitting logic is easy to unit-test. The result is a list of (start, end)
pairs covering [0, duration]; task.run_chapters turns them into titled chapters.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

MIN_CHAPTERS = 5
MAX_CHAPTERS = 15
MIN_SPAN = 30.0        # seconds; a chapter shorter than this merges into its neighbour
SILENCE_GAP = 4.0      # seconds between transcript segments that counts as a topic break
ALIGN_WINDOW = 15.0    # snap a split to the nearest shot change / pause within this many seconds
LONG_VIDEO = 30 * 60   # 30 minutes; longer videos aim for more chapters


def _rows(items: Iterable | None) -> list[tuple[float, float, str]]:
    """(start, end, text) from tuples or objects with .start/.end/.text."""
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


def pauses(transcript: Iterable | None = (), screen: Iterable | None = ()) -> list[float]:
    """Times where speech goes quiet for a while, plus on-screen text title cards appearing."""
    bounds: list[float] = []
    rows = _rows(transcript)
    for i in range(1, len(rows)):
        if rows[i][0] - rows[i - 1][1] >= SILENCE_GAP:
            bounds.append(rows[i - 1][1])
    had_text = False
    for start, _end, text in _rows(screen):
        if text and not had_text:
            bounds.append(start)
        had_text = bool(text)
    return bounds


def candidate_bounds(cuts: Iterable | None = (), transcript: Iterable | None = (),
                     screen: Iterable | None = (), duration: float = 0.0) -> list[float]:
    """Shot changes + pauses + text resets, deduped, sorted, away from the very ends."""
    pts: set[float] = set()
    for c in cuts or ():
        try:
            pts.add(float(c))
        except (TypeError, ValueError):
            pass
    pts.update(pauses(transcript, screen))
    return sorted(t for t in pts if 1.0 <= t <= max(1.0, duration - 1.0))


def _align(target: float, candidates: Sequence[float], window: float) -> float:
    if not candidates:
        return target
    best = min(candidates, key=lambda c: abs(c - target))
    return best if abs(best - target) <= window else target


def _target_count(duration: float, min_chapters: int, max_chapters: int) -> int:
    """5 chapters for short videos, scaling up to 15 at 30 min and beyond."""
    if duration >= LONG_VIDEO:
        count = max_chapters
    else:
        count = round(min_chapters + (duration / LONG_VIDEO) * (max_chapters - min_chapters))
        count = max(min_chapters, count)
    cap = max(2, int(duration // MIN_SPAN))
    return max(2, min(count, cap))


def segment(duration: float, cuts: Iterable | None = (), transcript: Iterable | None = (),
            screen: Iterable | None = (), *, min_chapters: int = MIN_CHAPTERS,
            max_chapters: int = MAX_CHAPTERS) -> list[tuple[float, float]]:
    """Chapter boundaries (start, end) covering [0, duration].

    Each even split point snaps to the nearest shot change or pause within 15 s so the
    boundaries land where a person would cut, then chapters shorter than 30 s merge.
    """
    if duration <= 0:
        return []
    candidates = candidate_bounds(cuts, transcript, screen, duration)
    count = _target_count(duration, min_chapters, max_chapters)
    # Long chapters can snap further: a third of a chapter's length, at least ALIGN_WINDOW.
    window = max(ALIGN_WINDOW, duration / count / 3)
    raw = [round(i * duration / count, 2) for i in range(1, count)]
    splits = sorted({_align(t, candidates, window) for t in raw})
    kept: list[float] = []
    for t in splits:
        if not kept or t - kept[-1] >= MIN_SPAN:
            kept.append(t)
    bounds = [0.0, *kept, duration]
    chapters = [(round(bounds[i], 2), round(bounds[i + 1], 2)) for i in range(len(bounds) - 1)]
    while len(chapters) > 1 and chapters[-1][1] - chapters[-1][0] < MIN_SPAN:
        chapters[-2] = (chapters[-2][0], chapters[-1][1])
        chapters.pop()
    return chapters
