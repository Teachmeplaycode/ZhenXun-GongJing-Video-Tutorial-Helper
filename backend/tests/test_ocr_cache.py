"""The RapidOCR reader recognises a box again only when it moved or its pixels changed."""
import numpy as np

from modules.screentext import ocr


class Engine:
    """Stands in for RapidOCR: two boxes per frame; recognition names a crop by its brightness."""
    text_score = 0.5

    def __init__(self):
        self.recognised = []

    def preprocess(self, img):
        return img, 1.0, 1.0

    def maybe_add_letterbox(self, img, record):
        return img, record

    def auto_text_det(self, img):
        return np.array([[[0, 0], [40, 0], [40, 10], [0, 10]], [[0, 20], [40, 20], [40, 30], [0, 30]]], dtype=np.float32), 0.0

    def get_crop_img_list(self, img, boxes):
        return [img[int(b[0][1]):int(b[2][1]), int(b[0][0]):int(b[2][0])] for b in boxes]

    def text_rec(self, crops):
        self.recognised.append(len(crops))
        return [(f"亮度{int(c.mean())}", 0.9) for c in crops], 0.0

    def _get_origin_points(self, boxes, record, h, w):
        return boxes


def test_unchanged_boxes_keep_their_text(tmp_path, monkeypatch):
    import cv2

    engine = Engine()
    monkeypatch.setattr(ocr, "_rapid_engine", lambda: engine)
    monkeypatch.setattr(ocr, "backend_name", lambda: "rapidocr")
    frame = np.full((40, 60, 3), 100, np.uint8)
    paths = []
    for i, bottom in enumerate([100, 100, 200]):  # the lower box changes in the third frame
        img = frame.copy()
        img[20:30, 0:40] = bottom
        path = tmp_path / f"{i}.jpg"
        cv2.imwrite(str(path), img)
        paths.append(str(path))

    read = ocr.recognizer()
    texts = [[line.text for line in read(p)] for p in paths]
    assert engine.recognised == [2, 1]  # both; then nothing to recognise; then only the one that changed
    assert texts[1] == texts[0] and texts[2][0] == texts[0][0] and texts[2][1] != texts[0][1]
    assert (read.reused, read.read) == (3, 3)
