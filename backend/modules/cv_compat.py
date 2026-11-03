"""OpenCV imread/imwrite wrappers that tolerate non-ASCII paths on Windows.

cv2.imread and cv2.imwrite use C ``fopen`` internally, which cannot open files whose
path contains characters outside the system code page (e.g. Chinese on a default
Windows install).  The fix is to read/write the raw bytes with Python (which uses
wide-character APIs on Windows) and decode/encode in memory with cv2.

On macOS and Linux ``cv2.imread`` already handles any path the filesystem can store,
so the wrappers fall through to the original functions with no overhead beyond one
function call.

Usage::

    from modules.cv_compat import imread, imwrite
    image = imread("/data/视频/帧.jpg")
    imwrite("/data/视频/out.jpg", image)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_WIN = sys.platform == "win32"


def imread(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """Read an image, working around cv2's lack of Unicode path support on Windows."""
    s = str(path)
    if not _WIN:
        return cv2.imread(s, flags)
    try:
        data = np.fromfile(s, dtype=np.uint8)
    except (OSError, ValueError):
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite(path: str | Path, image: np.ndarray, params: list[int] | None = None) -> bool:
    """Write an image, working around cv2's lack of Unicode path support on Windows."""
    s = str(path)
    if not _WIN:
        return bool(cv2.imwrite(s, image, params or ()))
    ok, buf = cv2.imencode(Path(s).suffix, image, params or ())
    if not ok:
        return False
    try:
        buf.tofile(s)
    except OSError:
        return False
    return True


def imread_gray(path: str | Path) -> np.ndarray | None:
    """Shortcut for grayscale read."""
    return imread(path, cv2.IMREAD_GRAYSCALE)
