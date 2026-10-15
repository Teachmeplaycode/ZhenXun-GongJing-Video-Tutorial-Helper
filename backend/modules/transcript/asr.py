"""Local speech recognition with mlx-whisper (Apple Silicon).

  ASR_MODEL     default mlx-community/whisper-large-v3-turbo (downloaded on first use, ~1.5 GB)
  ASR_LANGUAGE  default zh; set to `auto` to let Whisper detect the language
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
# Steers Chinese output to simplified characters with punctuation.
ZH_PROMPT = "以下是普通话的句子，使用简体中文。"
# Phrases Whisper is known to invent over music or silence (from subtitle-laden training data).
HALLUCINATIONS = re.compile(r"请不吝点赞|订阅.{0,4}转发|打赏支持|明镜与点点|字幕由.{0,20}提供|字幕\s*by|Amara\.org|优优独播剧场|以下是普通话的句子")

_lock = asyncio.Lock()  # one model run at a time: it holds several GB of unified memory


@dataclass
class Segment:
    start: float
    end: float
    text: str

    def as_dict(self) -> dict:
        return {"start": round(self.start, 2), "end": round(self.end, 2), "text": self.text}


def available() -> bool:
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def model_name() -> str:
    return os.environ.get("ASR_MODEL", DEFAULT_MODEL)


def clean(raw: list[dict]) -> list[Segment]:
    """Drop likely non-speech and hallucinated segments; merge immediate repeats."""
    out: list[Segment] = []
    for s in raw:
        text = (s.get("text") or "").strip()
        if not text or HALLUCINATIONS.search(text):
            continue
        if s.get("no_speech_prob", 0) > 0.6 and s.get("avg_logprob", 0) < -1.0:
            continue
        if s.get("compression_ratio", 0) > 2.4:  # a phrase looping on itself
            continue
        if out and out[-1].text == text and s["start"] - out[-1].end < 1.0:
            out[-1].end = s["end"]
            continue
        out.append(Segment(float(s["start"]), float(s["end"]), text))
    return out


def _run(path: Path) -> list[Segment]:
    import mlx_whisper

    language = os.environ.get("ASR_LANGUAGE", "zh")
    result = mlx_whisper.transcribe(
        str(path), path_or_hf_repo=model_name(),
        language=None if language == "auto" else language,
        initial_prompt=ZH_PROMPT if language == "zh" else None,
        condition_on_previous_text=False,  # keeps one bad segment from derailing the rest
    )
    return clean(result.get("segments") or [])


async def transcribe(path: Path) -> list[Segment]:
    async with _lock:
        return await asyncio.to_thread(_run, path)
