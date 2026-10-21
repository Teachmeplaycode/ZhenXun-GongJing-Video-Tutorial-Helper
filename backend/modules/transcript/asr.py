"""Speech recognition: mlx-whisper on Mac, faster-whisper CPU on Linux, or Model Studio's Paraformer.

  ASR_BACKEND   mlx (Mac default), faster-whisper (Linux default), or paraformer (the cloud API,
                modules/transcript/paraformer.py; falls back to faster-whisper when a call fails)
  ASR_MODEL     mlx-community/whisper-large-v3-turbo on Mac, small on Linux
  ASR_LANGUAGE  default zh; set to `auto` to let Whisper detect the language
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
# Steers Chinese output to simplified characters with punctuation.
ZH_PROMPT = "以下是普通话的句子，使用简体中文。"
# Phrases Whisper is known to invent over music or silence (from subtitle-laden training data).
# "字幕志愿者 李宗盛" / "作词 李宗盛" came up on every silent or music-only video in the eval set (2026-10-16).
HALLUCINATIONS = re.compile(r"请不吝点赞|订阅.{0,4}转发|打赏支持|明镜与点点|字幕由.{0,20}提供|字幕\s*by|Amara\.org|优优独播剧场|以下是普通话的句子"
                            r"|字幕志愿者|^(作词|作曲|词曲|编曲)\s*[:：]?\s*李宗盛$")


def hallucinated(text: str) -> bool:
    return bool(HALLUCINATIONS.search(text.strip()))

_lock = asyncio.Lock()  # serialize recognition to bound memory and CPU usage


@dataclass
class Segment:
    start: float
    end: float
    text: str

    def as_dict(self) -> dict:
        return {"start": round(self.start, 2), "end": round(self.end, 2), "text": self.text}


def backend_name() -> str:
    return os.environ.get("ASR_BACKEND", "mlx" if sys.platform == "darwin" else "faster-whisper")


def available() -> bool:
    if backend_name() == "paraformer":
        from . import paraformer

        return bool(paraformer.key())
    try:
        if backend_name() == "faster-whisper":
            import faster_whisper  # noqa: F401
        else:
            import mlx_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def model_name() -> str:
    return os.environ.get("ASR_MODEL", "small" if backend_name() in ("faster-whisper", "paraformer") else DEFAULT_MODEL)


@lru_cache(maxsize=1)
def _cpu_model(name: str):
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8",
                        cpu_threads=int(os.environ.get("ASR_CPU_THREADS", "4")), num_workers=1)


def clean(raw: list[dict]) -> list[Segment]:
    """Drop likely non-speech and hallucinated segments; merge immediate repeats."""
    out: list[Segment] = []
    for s in raw:
        text = (s.get("text") or "").strip()
        if not text or hallucinated(text):
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
    language = os.environ.get("ASR_LANGUAGE", "zh")
    if backend_name() in ("faster-whisper", "paraformer"):  # paraformer here: its local fallback
        segments, _ = _cpu_model(model_name()).transcribe(
            str(path), language=None if language == "auto" else language,
            initial_prompt=ZH_PROMPT if language == "zh" else None,
            condition_on_previous_text=False, vad_filter=True, beam_size=5,
        )
        return clean([{"start": s.start, "end": s.end, "text": s.text,
                       "no_speech_prob": s.no_speech_prob, "avg_logprob": s.avg_logprob,
                       "compression_ratio": s.compression_ratio} for s in segments])

    import mlx_whisper

    result = mlx_whisper.transcribe(
        str(path), path_or_hf_repo=model_name(),
        language=None if language == "auto" else language,
        initial_prompt=ZH_PROMPT if language == "zh" else None,
        condition_on_previous_text=False,  # keeps one bad segment from derailing the rest
    )
    return clean(result.get("segments") or [])


def _local_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


async def transcribe(path: Path) -> list[Segment]:
    if backend_name() == "paraformer":
        from . import paraformer

        try:  # a cloud call: no need to queue behind the lock
            return clean(await paraformer.transcribe(path))
        except Exception as exc:  # noqa: BLE001 — any failure: the local model, if there is one
            if not _local_whisper():
                raise
            from modules import log

            log.event("asr.fallback", error=str(exc)[:160])
    async with _lock:
        return await asyncio.to_thread(_run, path)
