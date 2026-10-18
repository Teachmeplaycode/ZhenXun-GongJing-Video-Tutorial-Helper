import asyncio
import ipaddress
import json

import httpx
import pytest

from modules.agent import papers, web
from modules.agent.tools import AgentTools
from modules.frames import FrameJob
from modules.video_source import ResolvedVideo, Stream


def fake_dns(table):
    async def resolve(host, port):
        if host not in table:
            raise web.WebError(f"找不到网站 {host}")
        return [ipaddress.ip_address(ip) for ip in table[host]]
    return resolve


@pytest.mark.parametrize("url,ok", [
    ("https://example.com/a", True),
    ("https://proxied.com/", True),          # proxy fake-IP range
    ("http://localhost:8000/", False),
    ("http://127.0.0.1:11434/", False),
    ("http://169.254.169.254/latest/", False),
    ("http://printer.local/", False),
    ("http://lan-host.com/", False),         # a name that resolves into the LAN
    ("ftp://example.com/", False),
])
def test_check_public(monkeypatch, url, ok):
    monkeypatch.setattr(web, "resolve", fake_dns({"example.com": ["93.184.216.34"], "proxied.com": ["198.18.0.7"],
                                                  "lan-host.com": ["192.168.1.20"]}))
    if ok:
        asyncio.run(web.check_public(url))
    else:
        with pytest.raises(web.WebError):
            asyncio.run(web.check_public(url))


def test_redirect_into_lan_is_blocked(monkeypatch):
    monkeypatch.setattr(web, "resolve", fake_dns({"example.com": ["93.184.216.34"]}))
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(302, headers={"location": "http://127.0.0.1:8000/api/health"})))
    with pytest.raises(web.WebError) as e:
        asyncio.run(web.fetch("https://example.com/", client=client))
    assert "内网" in str(e.value)


def test_fetch_extracts_text_and_rejects_binary(monkeypatch):
    monkeypatch.setattr(web, "resolve", fake_dns({"example.com": ["93.184.216.34"]}))
    article = "<html><head><title>柚子与药物</title></head><body><article>" + "<p>西柚中的呋喃香豆素会抑制 CYP3A4。</p>" * 30 + "</article></body></html>"

    def handler(request):
        if request.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=article)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    page = asyncio.run(web.fetch("https://example.com/a", client=client))
    assert page.title == "柚子与药物" and "呋喃香豆素" in page.text
    with pytest.raises(web.WebError):
        asyncio.run(web.fetch("https://example.com/pdf", client=client))


def test_openalex_rebuilds_abstract(monkeypatch):
    monkeypatch.setattr(papers, "settings", lambda: {})
    work = {"display_name": "Grapefruit juice–drug interactions", "publication_year": 1998, "cited_by_count": 740,
            "doi": "https://doi.org/10.1046/x", "authorships": [{"author": {"display_name": "D. Bailey"}}],
            "primary_location": {"source": {"display_name": "Br J Clin Pharmacol"}},
            "abstract_inverted_index": {"juice": [1], "Grapefruit": [0], "interacts": [2]}, "open_access": {"oa_url": None}}
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": [work]})))
    [paper] = asyncio.run(papers.search_papers("q", client=client))
    assert paper.abstract == "Grapefruit juice interacts" and paper.citations == 740
    assert "被引 740" in paper.line(1) and "https://doi.org/10.1046/x" in paper.line(1)


def test_fetch_page_tool_reads_in_chunks(tmp_path, monkeypatch):
    job = FrameJob("j", ResolvedVideo("t", "v", "u", "t", 10.0, [Stream("s", {}, "s")]), None, tmp_path, count=1)
    calls = []

    async def fake_fetch(url):
        calls.append(url)
        return web.Page(url, "长文", "字" * 12000)
    monkeypatch.setattr(web, "fetch", fake_fetch)
    tools = AgentTools(job)
    first = asyncio.run(tools.run("fetch_page", {"url": "https://a.com"}))
    assert "继续读用 offset=5000" in first.text and first.text.startswith("以下是外部网页")
    second = asyncio.run(tools.run("fetch_page", {"url": "https://a.com", "offset": 10000}))
    assert "offset=" not in second.text and len(calls) == 1  # second read came from the cache

    monkeypatch.setenv("LLM_WEB", "off")
    assert asyncio.run(tools.run("web_search", {"query": "x"})).error


def test_search_tries_backends_in_order(monkeypatch):
    import ddgs
    from ddgs.exceptions import DDGSException

    tried = []

    class FakeDDGS:
        def __init__(self, timeout=None):
            pass

        def text(self, query, region=None, max_results=None, backend=None, **kwargs):
            tried.append(backend)
            if backend == "bing":
                return [{"title": "PubMed", "href": "https://pubmed.ncbi.nlm.nih.gov/1/", "body": "grapefruit"}]
            raise DDGSException("No results found.")
    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    monkeypatch.setattr(web, "DDGS_PACE", web.Pacer(0))
    monkeypatch.setattr(web, "settings", lambda: {"SEARCH_BACKENDS": "google, bing, brave"})
    results = asyncio.run(web.search("q"))
    assert [(r.title, r.url) for r in results] == [("PubMed", "https://pubmed.ncbi.nlm.nih.gov/1/")]
    assert tried == ["google", "bing"]  # stops at the first engine that answers

    monkeypatch.setattr(web, "settings", lambda: {"SEARCH_BACKENDS": "google,brave"})
    with pytest.raises(web.WebError):
        asyncio.run(web.search("q"))



def test_deepseek_search_brings_authority_site_and_date(monkeypatch):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": [
            {"title": "喝醋软化血管？别再被骗了", "url": "https://news.cctv.com/1", "snippet": "短", "summary": "长摘要 " * 3,
             "site_name": "央视网", "date": "2019-04-21T16:00:00+00:00", "authority": 4, "rerank_score": 1.7},
            {"title": "无名站", "url": "https://farm.example/2", "snippet": "s", "summary": None, "authority": -1, "date": None},
            {"title": "没有链接", "url": ""}]})
    monkeypatch.setattr(web, "settings", lambda: {"DEEPSEEK_API_KEY": "sk-test", "SEARCH_PROVIDERS": "deepseek"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    results = asyncio.run(web.search("喝醋 降血压", 5, "oneYear", client=client))
    assert seen["auth"] == "Bearer sk-test" and seen["body"]["count"] == 5
    assert seen["body"]["query"].startswith("喝醋 降血压 after:20")  # freshness in its own syntax
    assert [(r.authority, r.site, r.date) for r in results] == [(4, "央视网", "2019-04-21"), (None, "", "")]
    assert results[0].snippet.startswith("长摘要") and results[1].snippet == "s"  # the long summary, for the model
    assert web.authority_label(4) == "权威" and web.authority_label(None) == ""


def test_deepseek_key_is_the_chat_models(monkeypatch):
    assert web.deepseek_key({"DEEPSEEK_API_KEY": "a", "LLM_API_KEY": "b"}) == "a"
    assert web.deepseek_key({"LLM_API_KEY": "b"}) == "b"
    assert web.deepseek_key({"LLM_API_KEY": "b", "LLM_BASE_URL": "https://api.openai.com"}) == ""
    assert web.deepseek_key({"LLM_API_KEY": "b", "LLM_PROVIDER": "ollama"}) == ""


def test_deepseek_failures_move_on_to_the_next_provider(monkeypatch):
    def handler(request):
        if "deepseek" in request.url.host:
            return httpx.Response(402, json={"error": {"message": "Insufficient Balance"}})
        return httpx.Response(200, json={"results": [{"title": "T", "url": "https://t.com", "content": "c"}]})
    monkeypatch.setattr(web, "settings", lambda: {"DEEPSEEK_API_KEY": "k", "TAVILY_API_KEY": "t", "SEARCH_PROVIDERS": "deepseek,tavily"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert [r.url for r in asyncio.run(web.search("q", client=client))] == ["https://t.com"]
    monkeypatch.setattr(web, "settings", lambda: {"DEEPSEEK_API_KEY": "k", "SEARCH_PROVIDERS": "deepseek"})
    with pytest.raises(web.WebError, match="余额不足"):
        asyncio.run(web.search("q", client=client))


def test_definitions_follow_the_composer_switches(monkeypatch):
    from modules.agent import tools
    monkeypatch.setattr(tools, "settings", lambda: {})
    names = lambda **kw: {d["function"]["name"] for d in tools.definitions(**kw)}  # noqa: E731
    assert {"web_search", "fetch_page", "search_papers"} <= names()
    assert "search_papers" in names(web=False) and "web_search" not in names(web=False)
    assert "search_papers" not in names(papers=False) and "web_search" in names(papers=False)
    monkeypatch.setattr(tools, "settings", lambda: {"LLM_WEB": "off"})
    assert names() == {"search_transcript", "read_transcript", "read_chapters", "view_frames", "replay", "measure_motion"}
