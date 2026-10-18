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



def test_rerank_reorders_and_drops_misses(monkeypatch):
    monkeypatch.setattr(web, "settings", lambda: {"BOCHA_API": "sk-test", "SEARCH_RERANK": "on"})
    results = [web.SearchResult("腹胀", "https://farm.com", "饭后腹胀"), web.SearchResult("Amlodipine", "https://a.com", "no effect"),
               web.SearchResult("Nifedipine", "https://n.com", "raises levels"), web.SearchResult("维C", "https://c.com", "柚子维C"),
               web.SearchResult("FDA", "https://fda.gov", "grapefruit")]
    scores = {"index": 0}

    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "gte-rerank" and len(body["documents"]) == 5
        ranked = [(1, 0.96), (2, 0.8), (4, 0.3), (3, 0.05), (0, 0.02)]
        return httpx.Response(200, json={"code": 200, "data": {"results": [{"index": i, "relevance_score": s} for i, s in ranked]}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kept = asyncio.run(web.rerank_results("does grapefruit affect amlodipine", results, client))
    assert [r.url for r in kept] == ["https://a.com", "https://n.com", "https://fda.gov"]  # the two misses are gone

    # Off by default, and without a key: the original order stays.
    monkeypatch.setattr(web, "settings", lambda: {"BOCHA_API": "sk-test"})
    assert asyncio.run(web.rerank_results("q", results, client)) == results
    monkeypatch.setattr(web, "settings", lambda: {"SEARCH_RERANK": "on"})
    assert asyncio.run(web.rerank_results("q", results, client)) == results


def test_definitions_follow_the_composer_switches(monkeypatch):
    from modules.agent import tools
    monkeypatch.setattr(tools, "settings", lambda: {})
    names = lambda **kw: {d["function"]["name"] for d in tools.definitions(**kw)}  # noqa: E731
    assert {"web_search", "fetch_page", "search_papers"} <= names()
    assert "search_papers" in names(web=False) and "web_search" not in names(web=False)
    assert "search_papers" not in names(papers=False) and "web_search" in names(papers=False)
    monkeypatch.setattr(tools, "settings", lambda: {"LLM_WEB": "off"})
    assert names() == {"search_transcript", "read_transcript", "read_chapters", "view_frames", "replay", "measure_motion"}
