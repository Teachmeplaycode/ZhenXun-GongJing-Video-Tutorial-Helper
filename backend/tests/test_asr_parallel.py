"""Long audio is cut at quiet moments and the parts recognized side by side; each stage is timed."""
import asyncio
import wave

import numpy as np

from modules.transcript import paraformer, timing

RATE = 16000


def tone_with_gaps(seconds: float, gaps: list[float]) -> np.ndarray:
    """A loud tone with half-second silences at `gaps`."""
    t = np.arange(int(seconds * RATE))
    samples = (8000 * np.sin(t * 2 * np.pi * 220 / RATE)).astype(np.int16)
    for g in gaps:
        samples[int(g * RATE):int((g + 0.5) * RATE)] = 0
    return samples


def write(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())
    return path


def test_cuts_fall_in_the_quiet_near_each_boundary():
    samples = tone_with_gaps(600, [152.0, 297.5, 455.0])  # 600 s → 4 parts → cuts near 150, 300, 450
    cuts = paraformer.cut_points(samples, RATE, 600)
    assert all(g <= c <= g + 0.5 for c, g in zip(cuts, [152.0, 297.5, 455.0])) and len(cuts) == 3  # inside each silence
    assert paraformer.cut_points(samples[: 200 * RATE], RATE, 200) == []  # short audio stays whole


def test_parts_are_recognized_together_and_their_times_shifted(tmp_path, monkeypatch):
    wav = write(tmp_path / "a.wav", tone_with_gaps(400, []))
    monkeypatch.setattr(paraformer, "key", lambda: "k")
    monkeypatch.setattr(paraformer, "squeeze", lambda p, out: (out.write_bytes(b"opus"), out)[1])
    running, peak = [0], [0]

    async def upload(client, path):
        return f"oss://{path.stem}"

    async def recognize(client, url):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        await asyncio.sleep(0.05)
        running[0] -= 1
        return {"transcripts": [{"sentences": [{"begin_time": 1000, "end_time": 2000, "text": url}]}]}

    monkeypatch.setattr(paraformer, "_upload", upload)
    monkeypatch.setattr(paraformer, "_transcribe", recognize)
    monkeypatch.setattr(paraformer.spend, "asr", lambda seconds: None)
    stages = {}
    timing.STAGES.set(stages)
    got = asyncio.run(paraformer.transcribe(wav))
    assert peak[0] == len(got) == stages["parts"] == 3  # 400 s → 3 parts, all at once
    starts = [s["start"] for s in got]
    # each part's own offset added: cuts near 133 s and 267 s (± the quiet window; a steady tone has no quiet)
    assert starts[0] == 1.0 and 125 < starts[1] - 1 < 142 and 258 < starts[2] - 1 < 276
    assert [s["text"] for s in got] == ["oss://part00", "oss://part01", "oss://part02"]
    assert {"squeeze_ms", "upload_ms", "recognize_ms"} <= stages.keys()


def test_short_audio_is_sent_whole(tmp_path):
    wav = write(tmp_path / "a.wav", tone_with_gaps(60, []))
    assert paraformer.pieces(wav, tmp_path) == [(0.0, wav)]
