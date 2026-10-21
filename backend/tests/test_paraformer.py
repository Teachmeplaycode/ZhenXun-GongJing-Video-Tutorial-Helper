"""Paraformer results become transcript segments; a failed call falls back to the local model."""
import asyncio

from modules.transcript import asr, paraformer


def word(text, begin, end, punctuation=""):
    return {"text": text, "begin_time": begin, "end_time": end, "punctuation": punctuation}


def test_short_sentences_stay_whole_and_long_ones_are_cut_at_punctuation():
    result = {"transcripts": [{"sentences": [
        {"begin_time": 1000, "end_time": 3000, "text": "先点右键。", "words": [word("先点右键", 1000, 3000, "。")]},
        {"begin_time": 4000, "end_time": 30000, "text": "…", "words": [
            word("选中音频", 4000, 8000, "，"), word("点识别字幕", 8000, 12000, "，"),
            word("等它识别完", 12000, 20000, "。"), word("再改错别字", 20000, 30000, "。")]},
    ]}]}
    got = paraformer.segments(result)
    assert got[0] == {"start": 1.0, "end": 3.0, "text": "先点右键。"}
    assert [(s["start"], s["end"]) for s in got[1:]] == [(4.0, 12.0), (12.0, 20.0), (20.0, 30.0)]
    assert got[1]["text"] == "选中音频，点识别字幕，"
    assert all(s["end"] - s["start"] <= paraformer.MAX_SECONDS for s in got)


def test_a_failed_cloud_call_falls_back_to_the_local_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "paraformer")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k")

    async def boom(path):
        raise paraformer.ParaformerError("识别失败")

    monkeypatch.setattr(paraformer, "transcribe", boom)
    monkeypatch.setattr(asr, "_local_whisper", lambda: True)
    monkeypatch.setattr(asr, "_run", lambda path: [asr.Segment(0, 1, "本地")])
    assert asyncio.run(asr.transcribe(tmp_path / "a.wav"))[0].text == "本地"
    assert asr.available()


def test_the_cloud_result_is_cleaned_like_the_local_one(tmp_path, monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "paraformer")

    async def fine(path):
        return [{"start": 0, "end": 1, "text": " 你好 "}, {"start": 1, "end": 2, "text": ""}]

    monkeypatch.setattr(paraformer, "transcribe", fine)
    got = asyncio.run(asr.transcribe(tmp_path / "a.wav"))
    assert [s.text for s in got] == ["你好"]
