"""Which of the video's frames look most like the person's screenshot — "which step am I on?".

Two signals, both cheap. The screenshot's text is read once (the same on-device OCR as the
video's screen text) and compared with the screen text read around each frame: a menu, a dialog
title or a button label shared with the tutorial says more than the picture. The pictures are
compared too (small greyscale thumbnails, correlation), which carries a screenshot without text
and breaks ties. Words shared by most frames (the app's own menu bar) count for little.

The model still decides: the matches go to it as a hint next to the screenshot, with their times.
"""
from __future__ import annotations

from modules import cv_compat as cv_io

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

CJK = re.compile(r"[一-鿿]+")
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9]+|\d{2,}")
AROUND = 2.0       # seconds of screen text either side of a frame
TOP = 3            # matches reported per screenshot
APART = 6.0        # seconds between two reported matches (neighbours of one moment look alike)
MIN_WORDS = 3      # fewer words on the screenshot: compare the pictures only
TEXT_WEIGHT = 0.75
GOOD_TEXT = 0.12   # below these the best match is no match at all
GOOD_PICTURE = 0.7 
THUMB = (48, 27)


def words(text: str) -> set[str]:
    """Chinese as character pairs (OCR splits and misreads whole words), Latin as lower-case words."""
    out = set()
    for run in CJK.findall(text):
        out.update(run[i:i + 2] for i in range(len(run) - 1)) if len(run) > 1 else out.add(run)
    out.update(w.lower() for w in LATIN.findall(text))
    return out


def thumb(path) -> np.ndarray | None:
    image = cv_io.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    small = cv2.resize(image, THUMB, interpolation=cv2.INTER_AREA).astype(np.float32)
    small -= small.mean()
    norm = float(np.linalg.norm(small))
    return small / norm if norm > 1e-6 else small


def picture_score(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Correlation of two thumbnails mapped to 0–1 (0.5: unrelated)."""
    if a is None or b is None:
        return 0.0
    return max(0.0, min(1.0, (float((a * b).sum()) + 1) / 2))


@dataclass
class Match:
    slot: object
    score: float
    text: float
    picture: float
    shared: list[str] = field(default_factory=list)


def frame_texts(slots: list, captions: list) -> list[str]:
    """The screen text read within AROUND seconds of each frame."""
    return [" ".join(c.text for c in captions if c.start - AROUND <= s.time <= c.end + AROUND) for s in slots]


def rank(shot_text: str, shot_path, slots: list, frame_path, captions: list) -> list[Match]:
    """Frames best first, at most TOP and APART seconds from each other; [] when nothing is close."""
    if not slots:
        return []
    mine = words(shot_text)
    theirs = [words(t) for t in frame_texts(slots, captions)]
    use_text = len(mine) >= MIN_WORDS and any(theirs)
    weight = {}
    if use_text:
        n = len(slots)
        for w in mine:
            df = sum(1 for t in theirs if w in t)
            weight[w] = math.log((n + 1) / (df + 1)) + 0.1  # a word on every frame barely counts
    mine_total = math.sqrt(sum(weight.values())) if weight else 0
    shot = thumb(shot_path)
    found = []
    for slot, their in zip(slots, theirs):
        text = 0.0
        shared = []
        if use_text and their:
            shared = sorted(mine & their, key=lambda w: -weight[w])
            text = sum(weight[w] for w in shared) / (mine_total * math.sqrt(sum(weight.get(w, 0.1) for w in their)) or 1)
            text = min(1.0, text * 2)  # two different screens of one app rarely share more than half
        picture = picture_score(shot, thumb(frame_path(slot.index)))
        score = TEXT_WEIGHT * text + (1 - TEXT_WEIGHT) * picture if use_text else picture
        found.append(Match(slot, score, text, picture, shared[:6]))
    found.sort(key=lambda m: -m.score)
    best = found[0]
    if (best.text if use_text else 0) < GOOD_TEXT and best.picture < GOOD_PICTURE:
        return []
    picked = []
    for m in found:
        if m.score < best.score * 0.6 or len(picked) == TOP:
            break
        if all(abs(m.slot.time - p.slot.time) >= APART for p in picked):
            picked.append(m)
    return picked


def read_text(path) -> str:
    """The screenshot's text, or "" where there is no OCR here."""
    from modules.screentext import ocr

    if not ocr.available() or not Path(path).is_file():
        return ""
    try:
        return " ".join(line.text for line in ocr.recognize(str(path)) if line.confidence >= 0.5)
    except Exception:
        return ""
