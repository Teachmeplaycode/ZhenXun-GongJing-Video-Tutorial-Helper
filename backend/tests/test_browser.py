"""browse: a real headless Chromium against a local test site, driven by a scripted model."""
import asyncio
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from modules.agent import browser, web
from modules.agent.tools import AgentTools, ToolResult, definitions
from modules.llm import ToolCall

PAGES = {
    "/": """<html><head><title>首页</title></head><body>
        <input id="q" placeholder="搜索">
        <input type="password" placeholder="密码">
        <a href="/next">下一页</a></body></html>""",
    "/next": "<html><head><title>第二页</title></head><body><p>答案是 42</p></body></html>",
}


class Site(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path.split("?")[0], "not found").encode()
        self.send_response(200 if self.path.split("?")[0] in PAGES else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def site(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    async def only_test_site(url):  # the real check rejects 127.0.0.1; everything else stays blocked
        if not url.startswith(base):
            raise web.WebError("不能访问本机或内网地址")

    monkeypatch.setattr(web, "check_public", only_test_site)
    yield base
    server.shutdown()


class Script:
    """A model that plays back steps; each step sees the messages and returns (name, args) or text."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.seen = []

    async def stream(self, messages, usage, max_tokens=2048, tools=None):
        self.seen.append(messages)
        step = self.steps.pop(0)(messages) if self.steps else "没有更多步骤"
        if isinstance(step, tuple):
            usage.tool_calls = [ToolCall(f"c{len(self.seen)}", step[0], step[1])]
        else:
            yield step


def ref_of(messages, label):
    text = next(m["content"] for m in reversed(messages) if isinstance(m["content"], str) and "可操作元素" in m["content"])
    return int(re.search(r"\[(\d+)\] [^\n]*" + label, text).group(1))


def run(gen):
    async def go():
        try:
            return [item async for item in gen]
        finally:
            await browser.shutdown()
    return asyncio.run(go())


def needs_chromium():
    async def probe():
        try:
            await browser.browser()
            return True
        except web.WebError:
            return False
        finally:
            await browser.shutdown()
    if not asyncio.run(probe()):
        pytest.skip("headless Chromium not installed")


def test_host_check_blocks_private_addresses():
    checks = browser.HostCheck()
    assert not asyncio.run(checks.allowed("http://127.0.0.1:8000/api"))
    assert not asyncio.run(checks.allowed("http://10.0.0.5/"))
    assert not asyncio.run(checks.allowed("http://router.lan/"))
    assert asyncio.run(checks.allowed("data:image/png;base64,AAAA"))


def test_browse_is_offered_with_web_switch_only(monkeypatch):
    names = lambda d: {x["function"]["name"] for x in d}  # noqa: E731
    assert "browse" in names(definitions(web=True))
    assert "browse" not in names(definitions(web=False))
    monkeypatch.setattr(browser, "available", lambda: False)
    assert "browse" not in names(definitions(web=True))


def test_browse_clicks_through_and_reports(site):
    needs_chromium()
    model = Script([
        lambda m: ("click", {"ref": ref_of(m, "下一页")}),
        lambda m: ("done", {"answer": "第二页写着答案是 42"}),
    ])
    tools = AgentTools(job=None, llm=model)
    items = run(tools.stream("browse", {"task": "找答案", "url": site + "/"}))
    events, result = items[:-1], items[-1]
    assert isinstance(result, ToolResult) and not result.error
    assert "答案是 42" in result.text and result.text.startswith(browser.UNTRUSTED)
    assert [e["type"] for e in events][:3] == ["browser.open", "browser.action", "browser.frame"]
    click = next(e for e in events if e.get("action") == "click")
    assert "下一页" in click["detail"] and 0 <= click["x"] <= 1 and click["url"].endswith("/next")
    assert all(e["src"].startswith("data:image/jpeg;base64,") for e in events if e["type"] == "browser.frame")
    assert [p["title"] for p in result.data["pages"]] == ["首页", "第二页"]
    # The model saw the page text and a screenshot, and only the newest snapshot stays in full.
    last = model.seen[-1]
    assert any("答案是 42" in str(m["content"]) for m in last)
    assert sum(isinstance(m["content"], list) for m in last) == 1


def test_browse_refuses_password_fields_and_other_hosts(site):
    needs_chromium()
    model = Script([
        lambda m: ("type", {"ref": ref_of(m, r"input\(password\)"), "text": "hunter2"}),
        lambda m: ("open", {"url": "http://169.254.169.254/latest/meta-data"}),
        lambda m: ("done", {"answer": "做不到"}),
    ])
    items = run(browser.browse(model, "登录", site + "/"))
    failed = [e for e in items if isinstance(e, dict) and e.get("error")]
    assert [e["action"] for e in failed] == ["type", "open"]
    assert "密码框" in failed[0]["detail"] and "内网" in failed[1]["detail"]
    tool_replies = [m["content"] for m in model.seen[-1] if m["role"] == "tool"]
    assert any("密码框" in r for r in tool_replies)


def test_browse_screens_page_text(site):
    needs_chromium()
    model = Script([lambda m: ("done", {"answer": "完成"})])

    async def always_injection(text):
        return 0.9

    run(browser.browse(model, "看看", site + "/next", screen=always_injection))
    first = model.seen[0][1]["content"]
    assert "已拦截" in first and "答案是 42" not in first


def test_browse_ends_with_text_when_out_of_steps(site, monkeypatch):
    needs_chromium()
    monkeypatch.setattr(browser, "max_steps", lambda: 2)
    model = Script([lambda m: ("scroll", {"direction": "down"}), lambda m: "只看到首页"])
    items = run(browser.browse(model, "随便看看", site + "/"))
    assert items[-1].text.endswith("首页 " + site + "/") and "只看到首页" in items[-1].text
    assert model.seen[-1][-1]["content"].startswith("步数或时间用完了")
