"""Tell whether a frame shows anything new since the last frame whose text was recognised.

Slides, handwriting tablets and talking heads hold the same picture for many seconds; reading its text
once is enough. A frame counts as changed when more than MIN_PIXELS pixels differ by more than
LEVEL grey levels from the last recognised frame, compared near full size (up to 960 px wide).

Pixel counts rather than averages: a teacher adding a small stroke to a formula (√3 → ∛3, 77 pixels
of a 960×540 frame) must count as a change, while JPEG noise, which rarely moves a pixel by 40 grey
levels, must not. Measured on 10 minutes of a screen-recorded maths lecture (BV1oo3i6FEsf).
"""
from __future__ import annotations

from modules import cv_compat as cv_io

from pathlib import Path

import cv2
import numpy as np

MAX_WIDTH = 960      # frames are read at 540p; wider ones are shrunk to this first
LEVEL = 40           # grey levels a pixel must move to count as changed
MIN_PIXELS = 24      # changed pixels that make a frame new (a short stroke is a few dozen)


def signature(path: str | Path) -> np.ndarray | None:
    """A frame in grey, or None if it can't be read (then it is always recognised)."""
    image = cv_io.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    h, w = image.shape
    if w > MAX_WIDTH:
        image = cv2.resize(image, (MAX_WIDTH, round(h * MAX_WIDTH / w)), interpolation=cv2.INTER_AREA)
    return image


def changed(a: np.ndarray | None, b: np.ndarray | None, level: int = LEVEL, min_pixels: int = MIN_PIXELS) -> bool:
    if a is None or b is None or a.shape != b.shape:
        return True
    return int(np.count_nonzero(cv2.absdiff(a, b) > level)) > min_pixels
