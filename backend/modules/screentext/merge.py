"""Turn per-second OCR results into timed captions: drop watermarks, join a line across the seconds it stays.

A subtitle shown for 3 s is read 3 times (sometimes with a character wrong); it becomes one Caption
from its first to its last second. The area of text that sits in the same place in a large share of
frames (a channel logo, a watermark) is found once and everything inside it is dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .ocr import Line

MIN_CONFIDENCE = 0.3   # stylized captions come back at 0.3; below that it's mostly noise
DENSE = 6              # a frame with this many lines is a screen or a page (screen recordings, menus):
DENSE_CONFIDENCE = 0.9  # there, only confident lines are kept — the rest is mostly misread small print
WATERMARK_SHARE = 0.4   # in at least this share of frames at the same spot,
WATERMARK_SPAN = 0.7    # from near the start to near the end → a watermark (a subtitle held a few seconds never is)
WATERMARK_MIN = 20      # frames needed before judging; shorter videos keep everything
GAP = 2.5              # seconds a caption may vanish (an OCR miss) and still continue
SAME = 0.75            # similarity at which two readings count as the same caption
CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z0-9]{3,}")


@dataclass
class Caption:
    start: float
    end: float
    text: str
    pos: str  # bottom | middle | top: where it sat on screen (subtitles are usually at the bottom)

    def as_dict(self) -> dict:
        return {"start": round(self.start, 1), "end": round(self.end, 1), "text": self.text, "pos": self.pos}


def meaningful(line: Line) -> bool:
    """Two or more Chinese characters, or a Latin/number word read with some confidence.
    Drops single characters and the gibberish OCR makes of textures and packaging."""
    if len(CJK.findall(line.text)) >= 2:
        return True
    return bool(WORD.search(line.text)) and line.confidence >= 0.5


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def place(line: Line) -> str:
    y = line.center_y
    return "bottom" if y > 0.67 else "top" if y < 0.2 else "middle"


def spot(line: Line) -> tuple:
    """Where a box starts, coarse enough that a logo read slightly differently each time still matches.
    Width is left out: OCR reads the same logo at different lengths ("滇西小哥 biiLi", "漢西小哥。")."""
    return round(line.x / 0.05), round(line.y / 0.05)


def similar(a: str, b: str, share: float = 0.6) -> bool:
    """Most of the shorter text appears in the longer one: a logo read with junk appended
    ("漢西小哥 Lillbl" vs "滇西小哥") still matches, two different subtitles don't."""
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return False
    matched = sum(block.size for block in SequenceMatcher(None, a, b).get_matching_blocks())
    return matched / min(len(a), len(b)) >= share


def watermarks(frames: list[tuple[float, list[Line]]]) -> list[tuple[float, float, float, float]]:
    """Screen areas (x0, y0, x1, y1) holding a watermark or logo: text at one spot in a large share
    of frames, most of whose readings resemble each other.

    Once found, everything inside the area is dropped, however OCR read it that time ("淇西小岢",
    or "bilibili" split off as its own fragment). Subtitles that happen to start at the same spot
    (different words each time) never pass the resemblance test, so they are never taken for one.
    """
    if len(frames) < WATERMARK_MIN:
        return []
    at: dict[tuple, list[Line]] = {}
    when: dict[tuple, list[float]] = {}
    for t, lines in frames:
        here: dict[tuple, Line] = {}
        for line in lines:
            here.setdefault(spot(line), line)
        for s, line in here.items():
            at.setdefault(s, []).append(line)
            when.setdefault(s, []).append(t)
    span = (frames[-1][0] - frames[0][0]) or 1
    areas = []
    for s, lines in at.items():
        if len(lines) / len(frames) < WATERMARK_SHARE or (when[s][-1] - when[s][0]) / span < WATERMARK_SPAN:
            continue
        texts = [line.text for line in lines]
        # The reading most like the others (not the most frequent one: ties made that depend on set order,
        # so the same video could get its watermark removed in one run and kept in the next).
        sample_texts = texts[:: max(1, len(texts) // 40)]
        typical = max(sample_texts, key=lambda t: sum(similar(t, o) for o in sample_texts))
        alike = [line for line in lines if similar(line.text, typical)]
        if len(alike) / len(lines) >= 0.6:
            areas.append((min(l.x for l in alike) - 0.01, min(l.y for l in alike) - 0.01,
                          max(l.x + l.w for l in alike) + 0.01, max(l.y + l.h for l in alike) + 0.01))
    return areas


def inside(line: Line, areas: list[tuple[float, float, float, float]]) -> bool:
    cx, cy = line.x + line.w / 2, line.center_y
    return any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in areas)


def build(frames: list[tuple[float, list[Line]]], step: float = 1.0) -> list[Caption]:
    """`frames`: (time in seconds, OCR lines), in time order."""
    marks = watermarks(frames)
    open_: list[dict] = []   # captions still on screen: {cap, readings: {text: score}, last}
    done: list[dict] = []

    def close(item: dict) -> None:
        cap = item["cap"]
        cap.text = max(item["readings"].items(), key=lambda kv: kv[1])[0]  # the most confident, most frequent reading
        done.append(item)

    for t, lines in frames:
        seen = set()
        floor = DENSE_CONFIDENCE if len(lines) >= DENSE else MIN_CONFIDENCE
        for line in sorted(lines, key=lambda line: line.y):
            text = line.text.strip()
            if line.confidence < floor or inside(line, marks) or not meaningful(line):
                continue
            key = normalize(text)
            match = next((item for item in open_ if id(item) not in seen and item["cap"].pos == place(line)
                          and SequenceMatcher(None, normalize(item["cap"].text), key).ratio() >= SAME), None)
            if match is None:
                match = {"cap": Caption(t, t + step, text, place(line)), "readings": {}, "last": t}
                open_.append(match)
            match["cap"].end, match["last"] = t + step, t
            match["readings"][text] = match["readings"].get(text, 0) + line.confidence
            seen.add(id(match))
        for item in [i for i in open_ if t - i["last"] > GAP]:
            open_.remove(item)
            close(item)
    for item in open_:
        close(item)
    return sorted((item["cap"] for item in done), key=lambda c: (c.start, c.pos != "bottom"))
