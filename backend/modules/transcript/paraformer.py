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
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

MODEL = "paraformer-v2"
MAX_SECONDS = 12.0   # longer sentences are cut at punctuation
POLL_SECONDS = 2.0
TIMEOUT_SECONDS = 900
BREAK = re.compile(r"[，。！？；,.!?;]$")


class ParaformerError(RuntimeError):
    pass


def key() -> str:
    return os.environ.get("DASHSCOPE_API_KEY", "").strip()


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


async def transcribe(wav: Path) -> list[dict]:
    """[{start, end, text}] for the audio in `wav`, seconds; raises ParaformerError."""
    if not key():
        raise ParaformerError("没有配置 DASHSCOPE_API_KEY")
    with tempfile.TemporaryDirectory() as tmp:
        small = await asyncio.to_thread(squeeze, wav, Path(tmp) / "audio.opus")
        async with httpx.AsyncClient(timeout=60, headers={"Authorization": f"Bearer {key()}"}) as client:
            url = await _upload(client, small)
            return segments(await _transcribe(client, url))
