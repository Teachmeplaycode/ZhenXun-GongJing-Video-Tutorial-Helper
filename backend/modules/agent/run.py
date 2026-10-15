"""One question about a link job's frames → streamed events in the frontend's trace protocol (design_2.md §9.2).

Steps: pick frames (selection or an even spread of the whole video) → pick the matching speech
transcript → send both with the question to the vision model → stream the answer. Each step is
reported as a tool call so the chat shows a trace.
"""
from __future__ import annotations

import base64
import os
import time
from collections.abc import AsyncIterator

from modules.frames import FrameJob
from modules.llm import ChatClient, LLMError, OllamaClient, Usage

HISTORY_MESSAGES = 8      # earlier turns sent back as plain text (frames only go with the current turn)
HISTORY_CHARS = 4000
LINE_SECONDS = 12         # transcript segments are merged into lines of about this length
FRAME_WINDOW = 10         # with selected frames, speech within this many seconds of each is sent

SYSTEM_PROMPT = """你是视频理解助手。用户给你的是从一段视频中按时间抽取的若干关键帧（静态画面），每张图前标注了帧号和时间点；有语音时还会附上带时间点的语音转写。

规则：
- 只依据这些画面、语音转写、视频标题和简介回答。你看不到连续画面，不要编造画面之间发生的事。
- 语音转写是自动识别的，可能有同音错字、漏字或把背景音乐误识别成文字；引用时保留原话，明显不通的地方说明可能识别有误。转写只记录说话内容，不包含语气、音乐和音效。
- 没有提供语音转写时，你不知道视频里说了什么，不要编造台词或口播。
- 引用画面或台词时写出时间点，例如 [01:23]，方便用户回到原视频核对。
- 画面里能看到的文字可以引用；看不清就说看不清。
- 画面之间的间隔是正常的抽样间隔，不要把它们当作缺失逐一列出。只有上下文里明确列出的「没有取到画面的时段」才是缺失，结论不要覆盖这些时段，并在回答中说明。
- 证据不足时直接说明不确定，不要猜测。
- 用简体中文回答，纯文本，可以用编号列表；不要使用 Markdown 标题、加粗或表格，不要使用 emoji。"""


def clock(seconds: float) -> str:
    t = max(0, int(seconds))
    return f"{t // 60:02d}:{t % 60:02d}"


def frame_no(index: int) -> str:
    return f"F{index + 1:03d}"


def spread(items: list, limit: int) -> list:
    """Evenly pick at most `limit` items, keeping order and both ends."""
    if len(items) <= limit:
        return items
    if limit == 1:
        return [items[len(items) // 2]]
    return [items[round(i * (len(items) - 1) / (limit - 1))] for i in range(limit)]


def max_images() -> int:
    # Default 64 = a job's maximum frame count, so every sampled frame is sent (~13k input tokens).
    return max(1, int(os.environ.get("LLM_MAX_IMAGES", "64")))


def pick_frames(job: FrameJob, requested: list[int] | None, limit: int) -> tuple[list, list[str]]:
    """Frames to send and notes about what was left out."""
    available = [s for s in job.slots if s.status == "ok" and job.frame_path(s.index).is_file()]
    notes = []
    if requested:
        wanted = set(requested)
        chosen = [s for s in available if s.index in wanted]
        if len(chosen) < len(wanted):
            notes.append(f"所选的 {len(wanted) - len(chosen)} 帧尚未获取，已跳过")
    else:
        chosen = available
    if len(chosen) > limit:
        notes.append(f"从 {len(chosen)} 帧中均匀选取 {limit} 帧")
        chosen = spread(chosen, limit)
    return chosen, notes


def max_transcript_chars() -> int:
    return max(1000, int(os.environ.get("LLM_MAX_TRANSCRIPT_CHARS", "60000")))


def pick_transcript(job: FrameJob, frames: list | None) -> tuple[list[str], str]:
    """Timed transcript lines for the request, and a note on what they cover or why there are none.

    `frames`: the selected slots, or None for the whole video.
    """
    transcript = job.transcript
    if transcript is None or not transcript.segments:
        status = transcript.status if transcript else "none"
        reasons = {"running": "语音仍在转写中，本次没有语音内容", "pending": "语音尚未开始转写"}
        return [], reasons.get(status) or (transcript.message if transcript and transcript.message else "没有语音转写")
    segments = transcript.segments
    if frames is not None:
        segments = [s for s in segments
                    if any(s.end >= f.time - FRAME_WINDOW and s.start <= f.time + FRAME_WINDOW for f in frames)]
    lines: list[str] = []
    start, texts = None, []
    for seg in segments:
        if start is not None and seg.end - start > LINE_SECONDS:
            lines.append(f"[{clock(start)}] {' '.join(texts)}")
            start, texts = None, []
        if start is None:
            start = seg.start
        texts.append(seg.text)
    if texts:
        lines.append(f"[{clock(start)}] {' '.join(texts)}")
    note = f"{len(segments)} 句" + ("（所选帧前后各 %d 秒）" % FRAME_WINDOW if frames is not None else "")
    budget, kept = max_transcript_chars(), []
    for line in lines:
        budget -= len(line) + 1
        if budget < 0:
            note += f"，过长只保留到 {line[1:6]} 之前"
            break
        kept.append(line)
    return kept, note


def build_messages(job: FrameJob, frames: list, question: str, history: list[dict], scope_all: bool,
                   transcript: tuple[list[str], str] = ([], "")) -> list[dict]:
    video = job.video
    coverage = job.coverage()
    context = [f"视频标题：{video.title}", f"时长：{clock(video.duration)}"]
    if video.description:
        context.append(f"简介：{video.description[:800]}")
    context.append(f"范围：{'整段视频' if scope_all else '用户选中的帧'}，共提供 {len(frames)} 帧画面")
    if coverage["missing_ranges"]:
        gaps = "、".join(f"{clock(a)}–{clock(b)}" for a, b in coverage["missing_ranges"])
        context.append(f"没有取到画面的时段：{gaps}")
    if coverage["pending"]:
        context.append(f"另有 {coverage['pending']} 帧仍在抓取中，未包含在内")

    lines, note = transcript
    if not lines and note:
        context.append(f"语音：{note}")
    content: list[dict] = [{"type": "text", "text": "\n".join(context)}]
    if lines:
        content.append({"type": "text", "text": f"语音转写（{note}）：\n" + "\n".join(lines)})
    for slot in frames:
        data = base64.b64encode(job.frame_path(slot.index).read_bytes()).decode()
        content.append({"type": "text", "text": f"帧 {frame_no(slot.index)} · {clock(slot.time)}"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}})
    content.append({"type": "text", "text": f"问题：{question}"})

    past = [{"role": m["role"], "content": str(m["content"])[:HISTORY_CHARS]}
            for m in history[-HISTORY_MESSAGES:] if m.get("role") in ("user", "assistant") and m.get("content")]
    return [{"role": "system", "content": SYSTEM_PROMPT}, *past, {"role": "user", "content": content}]


async def run_agent(job: FrameJob, client: ChatClient | OllamaClient, question: str, *,
                    frames: list[int] | None = None, history: list[dict] | None = None) -> AsyncIterator[dict]:
    """Yield §9.2 events. Errors end the stream with `run.error` instead of raising."""
    started = time.perf_counter()
    steps = 0

    def tool(call_id: str, kind: str, **payload) -> dict:
        return {"type": f"tool_call.{kind}", "call_id": call_id, **payload}

    yield {"type": "progress.update", "step": "整理画面", "percent": 10}
    steps += 1
    chosen, notes = pick_frames(job, frames, max_images())
    yield tool("frames", "started", tool_name="frames.select")
    yield tool("frames", "input", input={"kind": "params", "params": {
        "scope": f"已选 {len(frames)} 帧" if frames else "整段视频",
        "available": f"{job.coverage()['ok']}/{len(job.slots)}", "limit": max_images()}})
    listing = "\n".join(f"{frame_no(s.index)}  {clock(s.time)}" for s in chosen) or "（没有可用画面）"
    yield tool("frames", "output", stdout="\n".join([listing, *notes]), exit_code=0)
    yield tool("frames", "completed", result_count=len(chosen))

    yield {"type": "progress.update", "step": "读取语音", "percent": 22}
    steps += 1
    selected = chosen if frames else None
    transcript = pick_transcript(job, selected)
    status = job.transcript.status if job.transcript else "none"
    yield tool("speech", "started", tool_name="transcript.read")
    yield tool("speech", "input", input={"kind": "params", "params": {
        "scope": f"所选帧前后 {FRAME_WINDOW}s" if frames else "整段视频", "status": status}})
    lines, note = transcript
    preview = lines[:6] + ([f"… 共 {len(lines)} 行"] if len(lines) > 6 else [])
    yield tool("speech", "output", stdout="\n".join([note, *preview]), exit_code=0)
    yield tool("speech", "completed", result_count=len(lines))

    yield {"type": "progress.update", "step": "模型分析", "percent": 35}
    steps += 1
    model = client.config.model
    yield tool("model", "started", tool_name=f"vision.{model}")
    yield tool("model", "input", input={"kind": "params", "params": {"model": model, "images": len(chosen), "transcript_lines": len(lines), "question": question}})
    usage = Usage()
    answered = False
    try:
        messages = build_messages(job, chosen, question, history or [], scope_all=not frames, transcript=transcript)
        async for delta in client.stream(messages, usage):
            if not answered:
                answered = True
                yield {"type": "progress.update", "step": "生成回答", "percent": 70}
            yield {"type": "assistant.message.delta", "delta": delta}
        if not answered and usage.finish_reason is None:
            # The server closed the stream without a word (a busy DeepSeek does this after ~10 minutes).
            raise LLMError("empty", "模型没有返回任何内容，请稍后重试", True)
    except LLMError as err:
        yield tool("model", "output", stderr=err.message, exit_code=1)
        yield tool("model", "completed", result_count=0)
        yield {"type": "run.error", "code": err.code, "message": err.message, "retryable": err.retryable}
        return

    tokens = f"输入 {usage.prompt_tokens if usage.prompt_tokens is not None else '?'} · 输出 {usage.completion_tokens if usage.completion_tokens is not None else '?'} tokens"
    truncated = usage.finish_reason == "length"
    yield tool("model", "output", stdout=f"{tokens}\nfinish_reason={usage.finish_reason}", exit_code=2 if truncated else 0)
    yield tool("model", "completed", result_count=len(chosen))
    if truncated:
        yield {"type": "assistant.message.delta", "delta": "\n\n（回答达到长度上限，已截断）"}
    yield {"type": "run.completed", "steps": steps, "elapsed_ms": round((time.perf_counter() - started) * 1000),
           "summary": f"分析 {len(chosen)} 帧 · {len(lines)} 行语音 · {model} · {tokens}"}
