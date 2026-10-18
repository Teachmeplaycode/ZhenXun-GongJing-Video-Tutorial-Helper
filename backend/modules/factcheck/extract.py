"""说法抽取：从转写 + 画面文字里抽出可核实的说法（带时间点）。

只抽"有明确命题、可查证"的说法（如"柚子和降压药一起吃会血压骤降"），跳过寒暄、
提问、纯描述性旁白。抽取由 LLM 完成：把带时间点的转写和画面文字喂给模型，要求
返回 JSON 数组。解析容错：去掉 markdown 代码块围栏，取第一个 JSON 数组。
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable

# ask(messages, max_tokens) -> 完整文本（由 run.py 提供真实 LLM 调用，测试可传 mock）
Ask = Callable[[list[dict], int], Awaitable[str]]

SYSTEM = """你是科普内容核查助手。从视频的语音转写和画面文字里，抽出"可核实的事实性说法"。

可核实的说法：有明确命题、能用权威资料查证真伪的陈述，例如功效、因果关系、剂量、
禁忌、营养成分、医学结论。不要抽：寒暄、提问、纯描述("画面里有一个柚子")、
个人感受、广告语、无法证伪的主观表达。

每条说法返回：
- claim：把原话标准化成简洁命题（去掉语气词，补全主语），用于检索核实
- original_text：视频里的原话（保留原措辞，用于标夸大用语）
- start / end：这句话的时间点（秒）
- source：transcript（语音）或 screentext（画面文字）
- segment_index：在对应来源里的段序号

只返回 JSON 数组，不要解释。没有可核实说法时返回 []。"""

EXAMPLE = '[{"claim":"西柚会与某些降压药发生相互作用","original_text":"柚子千万别和降压药一起吃","start":12.5,"end":15.0,"source":"transcript","segment_index":3}]'


def transcript_text(segments: list[dict]) -> str:
    """把转写段拼成带时间点的文本，供抽取用。"""
    lines = []
    for i, s in enumerate(segments):
        start, end = s.get("start", 0), s.get("end", 0)
        lines.append(f"[{i:02d} {start:.1f}-{end:.1f}] {s.get('text', '').strip()}")
    return "\n".join(lines)


def screentext_text(segments: list[dict]) -> str:
    """把画面文字段拼成带时间点的文本。"""
    lines = []
    for i, s in enumerate(segments):
        start, end = s.get("start", 0), s.get("end", 0)
        lines.append(f"[{i:02d} {start:.1f}-{end:.1f}] {s.get('text', '').strip()}")
    return "\n".join(lines)


def _parse(raw: str) -> list[dict]:
    """从模型输出里提取 JSON 数组，容错处理代码块围栏和多余文本。"""
    if not raw:
        return []
    text = raw.strip()
    # 去掉 markdown 代码块围栏
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    # 直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("claims"), list):
            return data["claims"]
    except json.JSONDecodeError:
        pass
    # 取第一个 [ 到最后一个 ]
    start, end = text.find("["), text.rfind("]")
    if 0 <= start < end:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return []


def _clean(item: dict) -> dict | None:
    """校验并清洗一条抽取结果，不合法返回 None。"""
    if not isinstance(item, dict):
        return None
    claim = item.get("claim") or ""
    original = item.get("original_text") or item.get("original") or ""
    if not isinstance(claim, str) or not isinstance(original, str):
        return None
    claim, original = claim.strip(), original.strip()
    if not claim and not original:
        return None
    if not claim:
        claim = original
    src = item.get("source", "transcript")
    if src not in ("transcript", "screentext"):
        src = "transcript"
    try:
        start = float(item.get("start", 0))
        end = float(item.get("end", start))
        index = int(item.get("segment_index", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(start) or not math.isfinite(end) or index < 0:
        return None
    if end < start:
        start, end = end, start
    return {
        "claim": claim[:200],
        "original_text": original[:300],
        "start": max(0.0, start),
        "end": max(0.0, end),
        "source": src,
        "segment_index": index,
    }


def _anchor(item: dict, claim: dict, transcript: list[dict], screentext: list[dict]) -> dict | None:
    """Resolve the cited source/index against input, never trust generated quotes or timestamps."""
    source, index = item.get("source"), item.get("segment_index")
    if source not in ("transcript", "screentext") or type(index) is not int:
        return None
    segments = transcript if source == "transcript" else screentext
    if not 0 <= index < len(segments):
        return None
    segment = segments[index]
    text = segment.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    # A generated quote must occur in the cited input; reject an unrelated or invented quote.
    quote = "".join(claim["original_text"].split())
    if not quote or quote not in "".join(text.split()):
        return None
    try:
        start, end = float(segment["start"]), float(segment["end"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
        return None
    # The generated normalization may invent or invert a proposition even when its quote is real.
    # Use the actual cited segment as the proposition as well as the displayed original evidence.
    return {**claim, "source": source, "segment_index": index, "claim": text.strip(),
            "original_text": text, "start": start, "end": end}


async def extract_claims(
    ask: Ask,
    transcript_segments: list[dict],
    screentext_segments: list[dict],
) -> list[dict]:
    """抽取可核实的说法。返回清洗后的列表。"""
    t_text = transcript_text(transcript_segments)
    s_text = screentext_text(screentext_segments)
    if not t_text and not s_text:
        return []
    parts = []
    if t_text:
        parts.append("【语音转写】\n" + t_text)
    if s_text:
        parts.append("【画面文字】\n" + s_text)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "\n\n".join(parts) + f"\n\n示例输出：{EXAMPLE}"},
    ]
    raw = await ask(messages, 2048)
    items = _parse(raw)
    cleaned = []
    for item in items:
        c = _clean(item)
        if c is not None:
            anchored = _anchor(item, c, transcript_segments, screentext_segments)
            if anchored is not None:
                cleaned.append(anchored)
    return cleaned
