"""On-device text recognition with macOS Vision or RapidOCR ONNX on Linux.

Measured 2026-10-16 (M-series Mac): ~35 ms per 960×540 frame. Plain subtitles come back at
confidence 1.0; stylized captions ("失败 X5") at 0.3–0.5, sometimes with a wrong character.
"""
from __future__ import annotations

import os

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

    threads = int(os.environ.get("OCR_THREADS", "3"))
    return RapidOCR(intra_op_num_threads=threads, inter_op_num_threads=1)


SAME_BOX = 4      # px (in the detector's image): a box this close to one in the frame before is "the same place"
SAME_PIXELS = 6   # pixels of a box's crop that may differ by more than LEVEL grey levels and still be "unchanged"
LEVEL = 40


class _RapidReader:
    """RapidOCR for one video, frame after frame: boxes that sit where they sat in the frame before
    and whose pixels haven't changed (menus, toolbars, a caption that stays up) keep their text
    instead of being recognised again. Recognition is about two thirds of the time on a screen
    recording; detection still runs on every frame, so new and moved text is always found."""

    def __init__(self):
        self.engine = _rapid_engine()
        self.last: list[tuple] = []  # (box corners, grey crop, text, score) of the frame before
        self.reused = self.read = 0

    def _same(self, box, grey):
        for old_box, old_grey, text, score in self.last:
            if old_grey.shape == grey.shape and abs(old_box - box).max() <= SAME_BOX:
                import cv2
                import numpy as np

                if int(np.count_nonzero(cv2.absdiff(old_grey, grey) > LEVEL)) <= SAME_PIXELS:
                    return text, score
        return None

    def __call__(self, path: str) -> list[Line]:
        import cv2

        e = self.engine
        image = cv2.imread(path)
        if image is None:
            return []
        raw_h, raw_w = image.shape[:2]
        img, ratio_h, ratio_w = e.preprocess(image)
        record = {"preprocess": {"ratio_h": ratio_h, "ratio_w": ratio_w}}
        img, record = e.maybe_add_letterbox(img, record)
        boxes, _ = e.auto_text_det(img)
        if boxes is None or len(boxes) == 0:
            self.last = []
            return []
        crops = e.get_crop_img_list(img, boxes)
        greys = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) for c in crops]
        results: list = [self._same(b, g) for b, g in zip(boxes, greys)]
        todo = [i for i, r in enumerate(results) if r is None]
        if todo:
            fresh, _ = e.text_rec([crops[i] for i in todo])
            for i, (text, score, *_rest) in zip(todo, fresh):
                results[i] = (text, score)
        self.reused += len(boxes) - len(todo)
        self.read += len(todo)
        self.last = [(b, g, t, s) for b, g, (t, s) in zip(boxes, greys, results)]
        points = e._get_origin_points(boxes, record, raw_h, raw_w)
        lines = []
        for corners, (text, score) in zip(points, results):
            if not text or score < e.text_score:
                continue
            xs, ys = [p[0] for p in corners], [p[1] for p in corners]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            lines.append(Line(str(text), float(score), x0 / raw_w, y0 / raw_h, (x1 - x0) / raw_w, (y1 - y0) / raw_h))
        return lines


def recognizer():
    """A reader for one video's frames in order: RapidOCR with its box cache, or Vision as is."""
    if backend_name() == "rapidocr":
        engine = _rapid_engine()
        if all(hasattr(engine, n) for n in ("preprocess", "maybe_add_letterbox", "auto_text_det",
                                             "get_crop_img_list", "text_rec", "_get_origin_points")):
            return _RapidReader()
    return recognize


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
