"""Stage-02 (9c38a51) 工具循环收尾的两个边界诊断。

边界 A：末轮请求不带 tools，模型仍返回 tool_calls —— 观察终态与是否作答。
边界 B：工具执行直接抛异常（非 ToolResult(error=True)）—— 观察事件流如何终止。
对照 C：工具返回 error=True（未知工具名路径）—— 展示被优雅处理的对照组。

不改原始版本：MockTransport 模拟模型响应；AgentTools.view_frames 仅在运行时替换类属性。
运行：/workspace/gongjing-git-main/backend/.venv/bin/python diag_tool_loop.py
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/workspace/gongjing-git-main/backend")
os.environ["LLM_MAX_TOOL_ROUNDS"] = "1"  # 共 rounds+1 = 2 轮请求，第 2 轮不带 tools

import httpx

from modules.agent import tools as tools_module
from modules.agent.run import run_agent
from modules.agent.tools import AgentTools
from modules.frames import FrameJob, GrabResult
from modules.llm import ChatClient, LLMConfig
from modules.transcript import Segment, Transcript
from modules.video_source import ResolveError, ResolvedVideo, Stream


def video(streams=("https://v",)):
    return ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "标题", 600.0,
                         [Stream(u, {}, f"s{i}") for i, u in enumerate(streams)])


class Resolver:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    async def refresh(self, v):
        self.calls += 1
        if self.fail:
            raise ResolveError("local_file", "已删除")
        return video(("https://fresh",))


def make_job(tmp_path):
    tmp_path = Path(tmp_path)
    job = FrameJob("j", video(), Resolver(), tmp_path / "j", count=4)
    for slot in job.slots:
        slot.status = "ok"
        job.frame_path(slot.index).write_bytes(b"jpg")
    job.transcript = Transcript("done", "", [Segment(10, 14, "今天聊体重")])
    return job


def grabber(ok_urls):
    async def grab(stream, t, out):
        if stream.url in ok_urls:
            out.write_bytes(b"jpg")
            return GrabResult(True)
        return GrabResult(False, "forbidden")
    return grab


def sse(*chunks):
    return "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def tool_call_chunk(cid, name, args):
    return {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": cid,
                "function": {"name": name, "arguments": args}}]}}]}


def content_chunk(text):
    return {"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]}


def event_kinds(events):
    kinds = []
    for e in events:
        k = e["type"]
        if k == "progress.update":
            k += f"[{e.get('step')}]"
        elif k == "tool_call.completed":
            k += f"[{e.get('result_count')}]"
        kinds.append(k)
    return kinds


def summarize(tag, events, requests=None, exc=None):
    deltas = "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta")
    terminal = events[-1]["type"] if events else "(无事件)"
    has_run_error = any(e["type"] == "run.error" for e in events)
    has_completed = any(e["type"] == "run.completed" for e in events)
    print(f"\n===== {tag} =====")
    if requests is not None:
        print(f"模型请求数: {len(requests)}")
        for i, r in enumerate(requests):
            print(f"  第{i+1}次请求携带 tools 定义: {'tools' in r}")
            roles = [m["role"] for m in r["messages"]]
            print(f"  第{i+1}次请求消息角色序列: {roles}")
    print(f"事件序列: {event_kinds(events)}")
    print(f"回答文本: {deltas!r}")
    print(f"终态事件: {terminal}")
    print(f"含 run.error: {has_run_error} · 含 run.completed: {has_completed}")
    if exc is not None:
        print(f"冒泡异常: {type(exc).__name__}: {exc}")
    answered = bool(deltas)
    verdict_a = "存在问题：未作答即以 run.completed 正常收尾" if (has_completed and not answered) else "正常"
    verdict_b = "存在问题：异常冒泡，事件流无 run.error 终态" if (exc is not None and not has_run_error) else "正常"
    if exc is None:
        print(f"判定: {verdict_a}")
    else:
        print(f"判定: {verdict_b}")
    return {"answered": answered, "terminal": terminal, "run_error": has_run_error, "exc": repr(exc)}


async def collect(job, client):
    """收集事件；run_agent 中途抛异常时保留已产出的事件与异常，不让协程栈吞掉它们。"""
    events = []
    try:
        async for e in run_agent(job, client, QUESTION):
            events.append(e)
    except Exception as e:  # noqa: BLE001 —— 诊断目的就是捕获一切
        return events, e
    return events, None


QUESTION = "02:00 到 03:00 之间她在做什么"
QUESTION_NO_RANGE = "她当时到底在做什么动作"  # 不带时间段：不触发 zoom 预注入


async def collect_norange(job, client):
    events = []
    try:
        async for e in run_agent(job, client, QUESTION_NO_RANGE):
            events.append(e)
    except Exception as e:  # noqa: BLE001
        return events, e
    return events, None


def case_a(tmp):
    """末轮（不带 tools）模型仍返回 tool_calls。"""
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text=sse(
            tool_call_chunk(f"c{len(requests)}", "view_frames", '{"start": "02:00", "end": "03:00", "count": 2}')))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"),
                        transport=httpx.MockTransport(handler))
    job = make_job(tmp)
    tools_module.grab_frame = grabber({"https://v"})
    events, exc = asyncio.run(collect(job, client))
    assert exc is None, f"边界 A 不应抛异常: {exc!r}"
    return summarize("边界 A：末轮无 tools，模型仍请求工具调用", events, requests)


def case_b(tmp):
    """工具执行直接抛异常（模拟内部崩溃），而非返回 ToolResult(error=True)。

    b1: 问题带时间段 → 异常炸在 zoom 预注入阶段（第一次模型请求之前）。
    b2: 问题不带时间段 → 异常炸在工具循环阶段（模型至少请求过一次）。
    """
    requests = []
    boom_hits = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text=sse(
            tool_call_chunk("c1", "view_frames", '{"start": "02:00", "end": "03:00", "count": 2}')))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"),
                        transport=httpx.MockTransport(handler))
    tools_module.grab_frame = grabber({"https://v"})
    original = AgentTools.view_frames

    async def boom(self, *args, **kwargs):
        boom_hits.append((args, kwargs))
        raise RuntimeError("模拟工具内部崩溃（如 ffmpeg 输出解析失败）")

    AgentTools.view_frames = boom
    results = []
    try:
        job = make_job(tmp)
        events, exc = asyncio.run(collect(job, client))
        results.append(summarize("边界 B1：工具抛异常（zoom 预注入阶段，问题带时间段）", events, requests, exc=exc))
        requests.clear()
        job = make_job(tmp)
        events, exc = asyncio.run(collect_norange(job, client))
        results.append(summarize("边界 B2：工具抛异常（工具循环阶段，问题不带时间段）", events, requests, exc=exc))
    finally:
        AgentTools.view_frames = original
    print(f"\nboom 被调用次数: {len(boom_hits)}")
    return results


def case_c(tmp):
    """对照组：工具返回 ToolResult(error=True)（未知工具名）。"""
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, text=sse(
                tool_call_chunk("c1", "nope", '{"query": "x"}')))
        return httpx.Response(200, text=sse(content_chunk("好的，这里是没有语音内容的说明。")))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"),
                        transport=httpx.MockTransport(handler))
    job = make_job(tmp)
    tools_module.grab_frame = grabber({"https://v"})
    events, exc = asyncio.run(collect(job, client))
    assert exc is None, f"对照 C 不应抛异常: {exc!r}"
    return summarize("对照 C：工具返回 error=True（未知工具）", events, requests)


if __name__ == "__main__":
    print("诊断对象: 9c38a51 backend/modules/agent/run.py 工具循环（LLM_MAX_TOOL_ROUNDS=1）")
    with tempfile.TemporaryDirectory() as tmp:
        ra = case_a(tmp)
    with tempfile.TemporaryDirectory() as tmp:
        rb1, rb2 = case_b(tmp)
    with tempfile.TemporaryDirectory() as tmp:
        rc = case_c(tmp)
    print("\n===== 总结论 =====")
    print(f"A 未作答即收尾: {ra['terminal'] == 'run.completed' and not ra['answered']}")
    print(f"B1 zoom 阶段异常冒泡无 run.error 终态: {rb1['exc'] != 'None' and not rb1['run_error']}")
    print(f"B2 工具循环阶段异常冒泡无 run.error 终态: {rb2['exc'] != 'None' and not rb2['run_error']}")
    print(f"C error=True 被优雅处理并作答: {rc['answered'] and rc['terminal'] == 'run.completed'}")
