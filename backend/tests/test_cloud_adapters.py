"""Cross-platform adapters: timestamp/filter contract and OCR coordinate conversion."""
import sys
from types import SimpleNamespace

import numpy as np

from modules.transcript import asr
from modules.screentext import ocr


def test_cpu_asr_preserves_timestamps_and_filters_hallucinations(monkeypatch, tmp_path):
    def segment(text, start, end):
        return SimpleNamespace(text=text, start=start, end=end, no_speech_prob=0,
                               avg_logprob=0, compression_ratio=1)

    def transcribe(path, **options):
        assert options["vad_filter"] and not options["condition_on_previous_text"]
        assert options["language"] == "zh"
        return iter([segment("你好", 1.2, 2.3), segment("字幕志愿者 李宗盛", 3, 4)]), None

    monkeypatch.setenv("ASR_BACKEND", "faster-whisper")
    monkeypatch.setenv("ASR_LANGUAGE", "zh")
    monkeypatch.setattr(asr, "_cpu_model", lambda name: SimpleNamespace(transcribe=transcribe))
    assert asr._run(tmp_path / "audio.wav") == [asr.Segment(1.2, 2.3, "你好")]


def test_rapidocr_normalizes_top_left_boxes(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(imread=lambda _: np.zeros((100, 200, 3))))
    monkeypatch.setattr(ocr, "_rapid_engine", lambda: lambda _: (
        [[[[20, 30], [100, 30], [100, 50], [20, 50]], "字幕", 0.9]], None))
    assert ocr._rapid_recognize("frame.jpg") == [ocr.Line("字幕", 0.9, 0.1, 0.3, 0.4, 0.2)]
