"""Stage-04 (b7e6abc) 联网检索工具的行为诊断。

组 1（mock）：模块入口 AgentTools/web 的成功与失败路径——正文提取+UNTRUSTED 前缀、offset 续读、
             HTTP 404、连接错误、内网拒绝、搜索空结果（无 error）、引擎全被拦（error=True）。
组 2（mock）：run_agent 全链路——WebError 优雅降级不断流（模型收到错误文本后继续作答）；
             意外异常（非 WebError）冒泡断流（复验阶段 02 结论在本版 except 链下是否仍在）。
组 3（真实联网）：真实调用 web.search / web.fetch，成功保留实际结果，失败保留实际错误。
             与 mock 组分开记录，不用 mock 结果冒充联网验证。

运行：/workspace/repro-stage-04/backend/.venv/bin/python diag_web_tools.py
"""
import asyncio
import ipaddress
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/workspace/repro-stage-04/backend")

import httpx

from modules.agent import tools as tools_module
from modules.agent import web
from modules.agent.run import run_agent
from modules.agent.tools import AgentTools
from modules.frames import FrameJob, GrabResult
from modules.llm import ChatClient, LLMConfig
from modules.transcript import Segment, Transcript
from modules.video_source import ResolveError, ResolvedVideo, Stream

OUT = []
_ORIG = {}


def snapshot_orig():
    _ORIG["search"] = web.search
    _ORIG["fetch"] = web.fetch
    _ORIG["resolve"] = web.resolve


def restore_orig():
    web.search, web.fetch, web.resolve = _ORIG["search"], _ORIG["fetch"], _ORIG["resolve"]


def log(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def video(streams=("https://v",)):
    return ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "标题", 600.0,
                         [Stream(u, {}, f"s{i}") for i, u in enumerate(streams)])


class Resolver:
    def __init__(self):
        self.calls = 0

    async def refresh(self, v):
        self.calls += 1
        return video(("https://fresh",))


def make_job(tmp):
    tmp = Path(tmp)
    job = FrameJob("j", video(), Resolver(), tmp / "j", count=4)
    for slot in job.slots:
        slot.status = "ok"
        job.frame_path(slot.index).write_bytes(b"jpg")
    job.transcript = Transcript("done", "", [Segment(10, 14, "今天聊体重")])
    return job


# 项目测试同款：DNS 替换，避免 mock 组依赖真实解析
def fake_dns(table):
    async def resolve(host, port):
        if host not in table:
            raise web.WebError(f"找不到网站 {host}")
        return [ipaddress.ip_address(ip) for ip in table[host]]
    return resolve


ARTICLE = ("<html><head><title>柚子与药物</title></head><body><article>"
           + "<p>西柚中的呋喃香豆素会抑制 CYP3A4。</p>" * 30 + "</article></html>")


def show_result(tag, r):
    log(f"  [{tag}] error={r.error} · summary={r.summary!r}")
    head = r.text[:110].replace("\n", "⏎")
    log(f"  文本开头: {head}{'…' if len(r.text) > 110 else ''}")
    return r


# ---------------------------------------------------------------- 组 1：模块入口（mock）
def group1(tmp):
    log("\n===== 组 1：模块入口 mock（AgentTools + web，httpx.MockTransport / 替换 DNS）=====")
    web.resolve = fake_dns({"example.com": ["93.184.216.34"]})
    job = make_job(tmp)
    tools = AgentTools(job)

    def handler(request):
        if request.url.path == "/missing":
            return httpx.Response(404)
        if request.url.path == "/slow":
            raise httpx.ConnectError("连接被拒绝")
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=ARTICLE)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    orig_fetch, orig_search = web.fetch, web.search

    async def fetch_with_client(url):
        return await orig_fetch(url, client=client)
    web.fetch = fetch_with_client

    async def go():
        r1 = await tools.run("fetch_page", {"url": "https://example.com/a"})
        r2 = await tools.run("fetch_page", {"url": "https://example.com/a", "offset": 100})  # 缓存命中，不重新抓
        r3 = await tools.run("fetch_page", {"url": "https://example.com/missing"})
        r4 = await tools.run("fetch_page", {"url": "https://example.com/slow"})
        r5 = await tools.run("fetch_page", {"url": "http://127.0.0.1:8000/api"})
        return [r1, r2, r3, r4, r5]
    r1, r2, r3, r4, r5 = asyncio.run(go())

    show_result("1a fetch_page 成功", r1)
    log(f"  UNTRUSTED 前缀存在: {r1.text.startswith('以下是外部网页/数据库返回的内容')}")
    log(f"  正文提取成功（含'呋喃香豆素'）: {'呋喃香豆素' in r1.text} · 提示续读 offset: {'offset=' in r1.text}")
    show_result("1b fetch_page offset=100 续读", r2)
    log(f"  续读从缓存取同一页（不重新抓取，标注第 101 字起）: {'第 101–' in r2.text}")
    show_result("1c fetch_page HTTP 404", r3)
    show_result("1d fetch_page 连接错误", r4)
    show_result("1e fetch_page 内网地址", r5)

    async def go2():
        web.search = orig_search
        web.search = lambda *a, **k: asyncio.sleep(0, result=[])  # 空结果：正常返回
        e1 = await tools.run("web_search", {"query": "不存在的词"})
        async def blocked(*a, **k):
            raise web.WebError("搜索引擎都没有返回结果（可能被拦截），换个关键词或稍后再试")
        web.search = blocked
        e2 = await tools.run("web_search", {"query": "anything"})
        return e1, e2
    e1, e2 = asyncio.run(go2())
    show_result("1f web_search 空结果", e1)
    log(f"  空结果 error=False（当正常结果告知模型）: {not e1.error}")
    show_result("1g web_search 引擎全被拦", e2)
    log(f"  被拦 error=True（WebError→ToolResult）: {e2.error}")
    web.search, web.fetch = orig_search, orig_fetch


# ---------------------------------------------------------------- 组 2：run_agent 全链路（mock 模型）
def sse(*chunks):
    return "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def tool_call_chunk(cid, name, args):
    return {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": cid,
                "function": {"name": name, "arguments": args}}]}}]}


def content_chunk(text):
    return {"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]}


def kinds(events):
    return [e["type"].replace("tool_call.", "tc.") for e in events if e["type"] != "progress.update"]


def group2a(tmp):
    log("\n===== 组 2a：run_agent · WebError 优雅降级（问题带「查一下」触发 must_research）=====")
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, text=sse(
                tool_call_chunk("c1", "fetch_page", '{"url": "https://example.com/missing"}')))
        return httpx.Response(200, text=sse(content_chunk("网页打不开，但根据视频画面：她在 [00:10] 提到了体重话题。")))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))
    web.resolve = fake_dns({"example.com": ["93.184.216.34"]})
    job = make_job(tmp)

    async def fetch404(url, **kw):
        raise web.WebError("网页返回 HTTP 404")
    web.fetch = fetch404

    async def collect():
        events = []
        async for e in run_agent(job, client, "帮我查一下这个说法对不对"):
            events.append(e)
        return events
    events = asyncio.run(collect())
    deltas = "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta")
    terminal = events[-1]["type"]
    # 找发给模型的 tool 消息内容（第 2 次请求里 role=tool）
    tool_texts = [m for r in requests for m in r["messages"] if m["role"] == "tool"]
    log(f"  模型请求数: {len(requests)} · 事件尾部: {kinds(events)[-6:]}")
    log(f"  终态: {terminal} · 回答文本: {deltas!r}")
    log(f"  tool 消息数: {len(tool_texts)} · 错误文本发回模型: {'失败：网页返回 HTTP 404' in str(tool_texts)}")
    log(f"  判定（不断流，模型消化错误后作答）: {'PASS' if terminal == 'run.completed' and deltas else 'FAIL'}")
    return terminal, deltas


def group2b(tmp):
    log("\n===== 组 2b：run_agent · 意外异常（非 WebError）冒泡复验 =====")
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text=sse(
            tool_call_chunk("c1", "web_search", '{"query": "x"}')))

    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))

    async def boom(*a, **k):
        raise RuntimeError("模拟联网库内部崩溃")
    web.search = boom
    job = make_job(tmp)
    events, exc = [], None

    async def collect():
        """异常时保留已收到的事件（列表在协程外创建，随异常一起返回）。"""
        ev = []
        try:
            async for e in run_agent(job, client, "随便问点什么"):
                ev.append(e)
        except Exception as e:  # noqa: BLE001
            return ev, e
        return ev, None
    events, exc = asyncio.run(collect())
    log(f"  冒泡异常: {type(exc).__name__ if exc else None}: {exc}")
    log(f"  事件数: {len(events)} · 事件序列: {[e['type'] for e in events]}")
    log(f"  停在哪一步: {events[-1]['type'] if events else '(模型请求前就炸)'}"
        f"{' · ' + events[-1].get('step', '') if events and events[-1].get('step') else ''}")
    log(f"  含 run.error 终态: {any(e['type'] == 'run.error' for e in events)}")
    log(f"  判定（意外异常仍断流——except 链只覆盖 TypeError/WebError）: "
        f"{'PASS(复验成立)' if exc and not any(e['type'] == 'run.error' for e in events) else 'FAIL'}")


# ---------------------------------------------------------------- 组 3：真实联网
def group3():
    log("\n===== 组 3：真实联网（成功保留实际结果，失败保留实际错误）=====")

    async def go():
        out = {}
        try:
            rs = await web.search("ffmpeg extract frame jpeg", 3)
            out["search"] = ("ok", [(r.title[:40], r.url[:60]) for r in rs[:3]])
        except Exception as e:  # noqa: BLE001
            out["search"] = (type(e).__name__, str(e)[:160])
        try:
            p = await web.fetch("https://example.com/")
            out["fetch"] = ("ok", p.title, f"正文 {len(p.text)} 字", p.text[:80].replace("\n", " "))
        except Exception as e:  # noqa: BLE001
            out["fetch"] = (type(e).__name__, str(e)[:160])
        try:
            await web.fetch("http://127.0.0.1:8000/")
            out["lan"] = ("未拒绝",)
        except Exception as e:  # noqa: BLE001
            out["lan"] = (type(e).__name__, str(e)[:80])
        return out
    out = asyncio.run(go())
    for k, v in out.items():
        log(f"  真实 {k}: {v}")


if __name__ == "__main__":
    log("诊断对象: b7e6abc 联网检索（web.py / papers.py / tools.py WebError 路径 / run.py must_research）")
    snapshot_orig()
    with tempfile.TemporaryDirectory() as tmp:
        group1(tmp)
    restore_orig()
    with tempfile.TemporaryDirectory() as tmp:
        group2a(tmp)
    restore_orig()
    with tempfile.TemporaryDirectory() as tmp:
        group2b(tmp)
    restore_orig()
    group3()
    log("\n（组 3 为真实联网结果；组 1/2 为 mock，二者分开记录）")
