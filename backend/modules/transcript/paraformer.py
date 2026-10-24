"""Speech recognition through Alibaba Cloud Model Studio (百炼): paraformer-v2 file transcription.

For the web demo (ASR_BACKEND=paraformer, DASHSCOPE_API_KEY): the job's audio is squeezed to a
small mono Opus file, uploaded to Model Studio's free temporary storage (an oss:// URL that lasts
48 hours, no bucket of our own needed), transcribed as an async task, and the sentences come back
with millisecond times. Sentences longer than MAX_SECONDS are cut at punctuation using the
per-word times, so a citation points at the right few seconds.

  DASHSCOPE_API_KEY   the key (百炼 → API-KEY)
  DASHSCOPE_BASE      default https://dashscope.aliyuncs.com
  PARAFORMER_MODEL    default paraformer-v2
"""
from __future__ import annotations

import asyncio
import math
import os
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import httpx

from .. import spend
from . import timing

MODEL = "paraformer-v2"
MAX_SECONDS = 12.0   # longer sentences are cut at punctuation
POLL_SECONDS = 2.0
TIMEOUT_SECONDS = 900
BREAK = re.compile(r"[，。！？；,.!?;]$")


class ParaformerError(RuntimeError):
    pass


def key() -> str:
    """DASHSCOPE_API_KEY, or the same key saved under the model's name (Paraformer=…)."""
    return (os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("Paraformer") or os.environ.get("PARAFORMER_API_KEY") or "").strip()


def base() -> str:
    return os.environ.get("DASHSCOPE_BASE", "https://dashscope.aliyuncs.com").rstrip("/")


def model() -> str:
    return os.environ.get("PARAFORMER_MODEL", MODEL)


def squeeze(wav: Path, out: Path) -> Path:
    """Mono 16 kHz Opus at 24 kb/s: a 10-minute video is under 2 MB to upload."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-ar", "16000",
                    "-c:a", "libopus", "-b:a", "24k", str(out)], check=True, timeout=300)
    return out


def split(sentence: dict) -> list[tuple[float, float, str]]:
    """One sentence as (start, end, text) pieces of at most about MAX_SECONDS, cut after punctuation."""
    start, end = sentence["begin_time"] / 1000, sentence["end_time"] / 1000
    text = (sentence.get("text") or "").strip()
    words = sentence.get("words") or []
    if end - start <= MAX_SECONDS or not words:
        return [(start, end, text)] if text else []
    pieces, current, begun = [], "", None
    for w in words:
        if begun is None:
            begun = w["begin_time"] / 1000
        current += (w.get("text") or "") + (w.get("punctuation") or "")
        long_enough = w["end_time"] / 1000 - begun >= MAX_SECONDS / 2
        if BREAK.search(current) and long_enough or w["end_time"] / 1000 - begun >= MAX_SECONDS:
            pieces.append((begun, w["end_time"] / 1000, current.strip()))
            current, begun = "", None
    if current.strip():
        pieces.append((begun, words[-1]["end_time"] / 1000, current.strip()))
    return pieces


def segments(result: dict) -> list[dict]:
    out = []
    for transcript in result.get("transcripts") or []:
        for sentence in transcript.get("sentences") or []:
            out += [{"start": s, "end": e, "text": t} for s, e, t in split(sentence)]
    out.sort(key=lambda s: s["start"])
    return out


async def _upload(client: httpx.AsyncClient, path: Path) -> str:
    r = await client.get(f"{base()}/api/v1/uploads", params={"action": "getPolicy", "model": model()})
    if r.status_code != 200:
        raise ParaformerError(f"上传凭证获取失败（HTTP {r.status_code}）：{r.text[:200]}")
    policy = r.json()["data"]
    object_key = f"{policy['upload_dir']}/{path.name}"
    form = {"OSSAccessKeyId": policy["oss_access_key_id"], "Signature": policy["signature"], "policy": policy["policy"],
            "key": object_key, "x-oss-object-acl": policy["x_oss_object_acl"],
            "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"], "success_action_status": "200"}
    async with httpx.AsyncClient(timeout=300) as oss:  # the signed form is the credential here, not our key
        with path.open("rb") as f:
            up = await oss.post(policy["upload_host"], data=form, files={"file": (path.name, f, "audio/ogg")})
    if up.status_code not in (200, 204):
        raise ParaformerError(f"音频上传失败（HTTP {up.status_code}）")
    return f"oss://{object_key}"


async def _transcribe(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.post(f"{base()}/api/v1/services/audio/asr/transcription",
                          headers={"X-DashScope-Async": "enable", "X-DashScope-OssResourceResolve": "enable"},
                          json={"model": model(), "input": {"file_urls": [url]},
                                "parameters": {"language_hints": ["zh", "en"]}})
    if r.status_code != 200:
        raise ParaformerError(f"识别任务提交失败（HTTP {r.status_code}）：{r.text[:200]}")
    task = r.json()["output"]["task_id"]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_SECONDS)
        q = await client.post(f"{base()}/api/v1/tasks/{task}")
        output = q.json().get("output") or {}
        status = output.get("task_status")
        if status in ("PENDING", "RUNNING"):
            continue
        result = next((x for x in output.get("results") or [] if x.get("subtask_status") == "SUCCEEDED"), None)
        if status != "SUCCEEDED" or result is None:
            failed = next(iter(output.get("results") or []), {})
            raise ParaformerError(f"识别失败：{failed.get('code') or status} {failed.get('message') or output.get('message') or ''}".strip())
        async with httpx.AsyncClient(timeout=60) as plain:  # a pre-signed link
            return (await plain.get(result["transcription_url"])).json()
    raise ParaformerError("识别超时")


PART_SECONDS = 180.0   # audio longer than SPLIT_OVER is cut into pieces of about this length,
SPLIT_OVER = 300.0     # recognized side by side (one task each) instead of one after the other
MAX_PARTS = 8
QUIET_WINDOW = 8.0     # seconds either side of each cut to look for the quietest moment
QUIET_STEP = 0.2


def cut_points(samples, rate: int, duration: float) -> list[float]:
    """Where to cut: near every PART_SECONDS, at the quietest QUIET_STEP within QUIET_WINDOW,
    so a cut falls between words."""
    import numpy as np

    if duration <= SPLIT_OVER:
        return []
    parts = min(MAX_PARTS, math.ceil(duration / PART_SECONDS))
    step = int(rate * QUIET_STEP)
    cuts = []
    for k in range(1, parts):
        target = duration * k / parts
        a, b = max(0.0, target - QUIET_WINDOW), min(duration, target + QUIET_WINDOW)
        piece = samples[int(a * rate):int(b * rate)].astype(np.float32)
        n = len(piece) // step
        if n < 2:
            cuts.append(round(target, 2))
            continue
        loud = np.sqrt((piece[:n * step].reshape(n, step) ** 2).mean(axis=1))
        cuts.append(round(a + (int(loud.argmin()) + 0.5) * QUIET_STEP, 2))
    return cuts


def pieces(wav: Path, folder: Path) -> list[tuple[float, Path]]:
    """(start second, wav) for each part of `wav`; the whole file when it is short."""
    import numpy as np

    with wave.open(str(wav)) as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    if width != 2 or channels != 1:
        return [(0.0, wav)]
    samples = np.frombuffer(raw, dtype=np.int16)
    duration = len(samples) / rate
    bounds = [0.0, *cut_points(samples, rate, duration), duration]
    if len(bounds) == 2:
        return [(0.0, wav)]
    out = []
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        path = folder / f"part{i:02d}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(samples[int(a * rate):int(b * rate)].tobytes())
        out.append((a, path))
    return out


async def transcribe(wav: Path) -> list[dict]:
    """[{start, end, text}] for the audio in `wav`, seconds; raises ParaformerError.
    Long audio is cut at quiet moments and the parts recognized at the same time."""
    if not key():
        raise ParaformerError("没有配置 DASHSCOPE_API_KEY")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        parts = await asyncio.to_thread(pieces, wav, folder)
        timing.note(parts=len(parts))
        with timing.stage("squeeze"):
            small = await asyncio.gather(*(asyncio.to_thread(squeeze, p, folder / f"{p.stem}.opus") for _, p in parts))
        async with httpx.AsyncClient(timeout=60, headers={"Authorization": f"Bearer {key()}"}) as client:
            with timing.stage("upload"):
                urls = await asyncio.gather(*(_upload(client, f) for f in small))
            with timing.stage("recognize"):
                results = await asyncio.gather(*(_transcribe(client, u) for u in urls))
    out = []
    for (start, _), result in zip(parts, results):
        out += [{**s, "start": round(s["start"] + start, 3), "end": round(s["end"] + start, 3)} for s in segments(result)]
    out.sort(key=lambda s: s["start"])
    spend.asr(_seconds(wav))  # priced against the day's budget
    return out


def _seconds(wav: Path) -> float:
    """The length of a WAV (0 when it can't be read: then nothing is priced)."""
    try:
        with wave.open(str(wav)) as w:
            return w.getnframes() / float(w.getframerate())
    except (OSError, wave.Error, ZeroDivisionError):
        return 0.0
