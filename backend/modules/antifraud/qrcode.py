"""二维码检测与解码：从视频帧图像里检测并解码二维码，把引流链接/微信号等带回证据链。

用 OpenCV 的 QRCodeDetector（opencv-python-headless 已是项目依赖，无需额外安装）。
解码出的内容通常是网址，也可能是微信号、手机号——再交给 extract.py 二次提取。
"""
from __future__ import annotations

from modules import cv_compat as cv_io

from dataclasses import dataclass
from pathlib import Path

try:
    import cv2
    _HAS_CV2 = True
except ImportError:  # opencv is a hard dependency of the project, but stay safe in unit tests
    cv2 = None
    _HAS_CV2 = False


@dataclass
class QrcodeHit:
    """A QR code decoded from one frame."""
    frame_index: int
    time: float          # seconds
    content: str         # decoded text (often a URL)
    source_path: str     # Internal decoding provenance; never part of the public report.

    def as_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "time": round(self.time, 2),
            "content": self.content,
        }


def decode_qrcode_image(path: Path | str) -> list[str]:
    """Decode every QR code in one image file; return the non-empty decoded strings.

    Returns [] if OpenCV is unavailable, the file is missing, or no QR code is found.
    Never raises — QR decoding is best-effort evidence, not a critical path.
    """
    if not _HAS_CV2:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        img = cv_io.imread(str(p))
        if img is None:
            return []
        detector = cv2.QRCodeDetector()
        ok, data, _points, _straight = detector.detectAndDecodeMulti(img)
        if ok:
            return list(dict.fromkeys(d for d in data if d))
        data, _points, _straight = detector.detectAndDecode(img)
        return [data] if data else []
    except Exception:
        return []


def decode_qrcodes(frames: list[tuple[int, float, Path | str]]) -> list[QrcodeHit]:
    """Decode QR codes across many frames.

    `frames` is a list of (frame_index, time_seconds, image_path). Only frames whose path
    exists are read; missing frames are silently skipped (the sampler may not have every frame).
    """
    hits: list[QrcodeHit] = []
    seen: set[str] = set()
    for index, time, path in frames:
        for content in decode_qrcode_image(path):
            if content in seen:
                continue
            seen.add(content)
            hits.append(QrcodeHit(
                frame_index=index, time=time, content=content, source_path=str(path),
            ))
    return hits
