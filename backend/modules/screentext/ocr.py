"""On-device text recognition with macOS Vision or RapidOCR ONNX on Linux.

Measured 2026-10-16 (M-series Mac): ~35 ms per 960×540 frame. Plain subtitles come back at
confidence 1.0; stylized captions ("失败 X5") at 0.3–0.5, sometimes with a wrong character.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache

from modules.settings import settings


@dataclass
class Line:
    text: str
    confidence: float
    x: float  # box, normalized 0–1, origin top-left (Vision's origin is bottom-left; flipped here)
    y: float
    w: float
    h: float

    @property
    def center_y(self) -> float:
        return self.y + self.h / 2


def backend_name() -> str:
    return settings().get("OCR_BACKEND", "vision" if sys.platform == "darwin" else "rapidocr")


def available() -> bool:
    if settings().get("SCREENTEXT", "on").lower() in ("off", "0", "false"):
        return False
    try:
        if backend_name() == "rapidocr":
            import rapidocr_onnxruntime  # noqa: F401
        else:
            import Vision  # noqa: F401
            import Quartz  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _rapid_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)


def _rapid_recognize(path: str) -> list[Line]:
    import cv2

    image = cv2.imread(path)
    if image is None:
        return []
    height, width = image.shape[:2]
    result, _ = _rapid_engine()(image)
    lines = []
    for points, text, confidence in result or []:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        lines.append(Line(str(text), float(confidence), x0 / width, y0 / height,
                          (x1 - x0) / width, (y1 - y0) / height))
    return lines


def recognize(path: str) -> list[Line]:
    """Lines of text in one image. Runs synchronously; call it in a thread."""
    if backend_name() == "rapidocr":
        return _rapid_recognize(path)

    import Quartz
    import Vision
    from Foundation import NSURL

    source = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None)
    if source is None:
        return []
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if image is None:
        return []
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en-US"])
    request.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, _ = handler.performRequests_error_([request], None)
    if not ok:
        return []
    lines = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        best = candidates[0]
        box = observation.boundingBox()
        lines.append(Line(str(best.string()), float(best.confidence()), float(box.origin.x),
                          float(1 - box.origin.y - box.size.height), float(box.size.width), float(box.size.height)))
    return lines
