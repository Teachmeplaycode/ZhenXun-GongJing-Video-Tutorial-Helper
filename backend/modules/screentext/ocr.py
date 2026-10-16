"""Text recognition with macOS Vision (VNRecognizeTextRequest): on-device, free, good at Chinese.

Measured 2026-10-16 (M-series Mac): ~35 ms per 960×540 frame. Plain subtitles come back at
confidence 1.0; stylized captions ("失败 X5") at 0.3–0.5, sometimes with a wrong character.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

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


def available() -> bool:
    if sys.platform != "darwin" or settings().get("SCREENTEXT", "on").lower() in ("off", "0", "false"):
        return False
    try:
        import Vision  # noqa: F401
        import Quartz  # noqa: F401
    except ImportError:
        return False
    return True


def recognize(path: str) -> list[Line]:
    """Lines of text in one image. Runs synchronously; call it in a thread."""
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
