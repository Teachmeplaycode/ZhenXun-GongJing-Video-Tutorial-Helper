"""Web access for the agent, run by this backend: search, and fetch a page as plain text.

Search providers, tried in order (SEARCH_PROVIDERS): a self-hosted SearXNG (SEARXNG_URL), Tavily
(TAVILY_API_KEY), Bocha 博查 (BOCHA_API_KEY), then the keyless open-source ddgs metasearch library
(Bing, Brave, Google, DuckDuckGo, Wikipedia). Providers without configuration are skipped. In testing
Tavily's results were by far the best; Bocha's Chinese results included unrelated content-farm pages. Pages are fetched with httpx and reduced to their main text with trafilatura.

Fetching follows URLs a model chose, possibly from text on other pages, so every request and every
redirect hop is checked: only http(s) to public addresses, never this machine or the local network.
"""
from __future__ import annotations

import asyncio
import html
import ipaddress
import re
import socket
import urllib.parse
from dataclasses import dataclass

import httpx

from modules.settings import settings

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
MAX_BYTES = 3 << 20
MAX_REDIRECTS = 4
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")


class Pacer:
    """Keeps requests to one free service at least `interval` seconds apart, across all answers."""

    def __init__(self, interval: float):
        self.interval, self.lock, self.last = interval, asyncio.Lock(), 0.0

    async def __aenter__(self):
        await self.lock.acquire()
        loop = asyncio.get_running_loop()
        wait = self.last + self.interval - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)

    async def __aexit__(self, *exc):
        self.last = asyncio.get_running_loop().time()
        self.lock.release()


DDGS_PACE = Pacer(1.0)  # between queries from this backend, so the engines don't flag us as quickly


class WebError(Exception):
    """A user-facing reason the request failed (Chinese)."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment or "")).strip()


# ddgs (github.com/deedy5/ddgs) scrapes the engines like a browser would. Tried in this order until one
# answers; Chinese engines are left out on purpose. On the test machine (2026-10-15) only Bing answered:
# Google, Brave, DuckDuckGo and Mojeek returned nothing to scripted requests.
DEFAULT_BACKENDS = "bing,brave,google,duckduckgo,wikipedia"


def _ddgs(query: str, limit: int, backends: list[str], region: str, freshness: str = "") -> tuple[list[SearchResult], list[str]]:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException

    failures = []
    for backend in backends:
        try:
            rows = DDGS(timeout=10).text(query, region=region, max_results=limit, backend=backend,
                                         timelimit=FRESHNESS[freshness][1] if freshness in FRESHNESS else None)
        except DDGSException as exc:
            failures.append(f"{backend}: {str(exc)[:60]}")
            continue
        results = [SearchResult(r.get("title", ""), r.get("href", ""), r.get("body", "")) for r in rows if r.get("href")]
        if results:
            return results[:limit], failures
        failures.append(f"{backend}: 无结果")
    return [], failures


def setting(config: dict, *names: str) -> str:
    """First non-empty value among several spellings (the .env may use e.g. Tavily_API_KEY)."""
    return next((config[n].strip() for n in names if config.get(n, "").strip()), "")


# freshness → each provider's own notation
FRESHNESS = {"oneDay": ("day", "d"), "oneWeek": ("week", "w"), "oneMonth": ("month", "m"), "oneYear": ("year", "y")}


async def _tavily(query: str, limit: int, key: str, client: httpx.AsyncClient, freshness: str = "") -> list[SearchResult]:
    body = {"query": query, "max_results": limit, "search_depth": "basic"}
    if freshness in FRESHNESS:
        body["time_range"] = FRESHNESS[freshness][0]
    response = await client.post("https://api.tavily.com/search", headers={"Authorization": f"Bearer {key}"}, json=body)
    if response.status_code in (401, 403):
        raise WebError("Tavily key 无效")
    if response.status_code in (429, 432, 433):
        raise WebError("Tavily 额度已用完或请求过多")
    if response.status_code != 200:
        raise WebError(f"Tavily 返回 HTTP {response.status_code}")
    return [SearchResult(r.get("title", ""), r.get("url", ""), " ".join((r.get("content") or "").split())[:400])
            for r in response.json().get("results", []) if r.get("url")]


async def _bocha(query: str, limit: int, key: str, client: httpx.AsyncClient, freshness: str = "") -> list[SearchResult]:
    response = await client.post("https://api.bochaai.com/v1/web-search", headers={"Authorization": f"Bearer {key}"},
                                 json={"query": query, "count": limit, "summary": True, "freshness": freshness if freshness in FRESHNESS else "noLimit"})
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code != 200 or payload.get("code") not in (200, None):
        raise WebError(f"博查返回错误（{payload.get('code') or response.status_code}）：{payload.get('msg') or ''}".rstrip("："))
    pages = ((payload.get("data") or {}).get("webPages") or {}).get("value") or []
    return [SearchResult(p.get("name", ""), p.get("url", ""),
                         " ".join((p.get("summary") or p.get("snippet") or "").split())[:400]) for p in pages if p.get("url")]


async def _searxng(query: str, limit: int, base: str, client: httpx.AsyncClient, freshness: str = "") -> list[SearchResult]:
    params = {"q": query, "format": "json"}
    if freshness in FRESHNESS:
        params["time_range"] = FRESHNESS[freshness][0]
    response = await client.get(f"{base}/search", params=params)
    if response.status_code != 200:
        raise WebError(f"SearXNG 返回 HTTP {response.status_code}（检查它是否开启了 JSON 输出）")
    return [SearchResult(r.get("title", ""), r.get("url", ""), r.get("content", ""))
            for r in response.json().get("results", [])[:limit] if r.get("url")]


DEFAULT_PROVIDERS = "searxng,tavily,bocha,ddgs"
# Bocha's rerank API, off unless SEARCH_RERANK=on. Tested 2026-10-15: on Bocha's Chinese results it scored a
# content-farm page 0.77 and a professional medical article 0.19 (relevance, not reliability), and on
# OpenAlex it barely changed an already good order, so by default it isn't worth the extra call.
RERANK_MODEL = "gte-rerank"  # Bocha's own bocha-semantic-reranker-* answered 500 on the test account
RERANK_FLOOR = 0.15          # results scoring below this are dropped (at least RERANK_KEEP stay)
RERANK_KEEP = 3


async def rerank(query: str, documents: list[str], client: httpx.AsyncClient) -> list[tuple[int, float]] | None:
    """(index, relevance) best first via Bocha's rerank API, or None without a key or on any failure."""
    key = setting(settings(), "BOCHA_API_KEY", "BOCHA_API", "Bocha_API_KEY")
    if not key or len(documents) < 2 or settings().get("SEARCH_RERANK", "off").lower() not in ("on", "1", "true"):
        return None
    try:
        response = await client.post("https://api.bochaai.com/v1/rerank", headers={"Authorization": f"Bearer {key}"},
                                     json={"model": RERANK_MODEL, "query": query, "documents": documents,
                                           "top_n": len(documents), "return_documents": False}, timeout=15)
        rows = ((response.json() or {}).get("data") or {}).get("results") or []
        ranked = [(int(r["index"]), float(r["relevance_score"])) for r in rows]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    return ranked if len(ranked) == len(documents) else None


async def rerank_results(query: str, results: list[SearchResult], client: httpx.AsyncClient) -> list[SearchResult]:
    """Order results by semantic relevance and drop clear misses (e.g. content-farm pages)."""
    ranked = await rerank(query, [f"{r.title}\n{r.snippet}" for r in results], client)
    if ranked is None:
        return results
    kept = [results[i] for n, (i, score) in enumerate(ranked) if score >= RERANK_FLOOR or n < RERANK_KEEP]
    return kept


async def search(query: str, limit: int = 8, freshness: str = "", *, client: httpx.AsyncClient | None = None) -> list[SearchResult]:
    """Try SEARCH_PROVIDERS in order (default searxng, tavily, bocha, ddgs), skipping those without
    configuration; the first one that returns results wins, a failure moves on to the next."""
    config = settings()
    keyed = {
        "searxng": setting(config, "SEARXNG_URL").rstrip("/"),
        "tavily": setting(config, "TAVILY_API_KEY", "Tavily_API_KEY", "TAVILY_API"),
        "bocha": setting(config, "BOCHA_API_KEY", "BOCHA_API", "Bocha_API_KEY"),
        "ddgs": "builtin",
    }
    providers = [p.strip().lower() for p in config.get("SEARCH_PROVIDERS", DEFAULT_PROVIDERS).split(",")]
    providers = [p for p in providers if keyed.get(p)]
    own = client is None
    client = client or httpx.AsyncClient(timeout=20, headers=HEADERS, trust_env=False)
    failures = []
    try:
        for provider in providers:
            try:
                if provider == "ddgs":
                    backends = [b.strip() for b in config.get("SEARCH_BACKENDS", DEFAULT_BACKENDS).split(",") if b.strip()]
                    async with DDGS_PACE:
                        results, _ = await asyncio.to_thread(_ddgs, query, limit, backends, config.get("SEARCH_REGION", "us-en"), freshness)
                    if not results:
                        failures.append("ddgs 的搜索引擎都没有返回结果（可能被拦截）")
                else:
                    fetcher = {"tavily": _tavily, "bocha": _bocha, "searxng": _searxng}[provider]
                    results = await fetcher(query, limit, keyed[provider], client, freshness)
            except WebError as exc:
                failures.append(str(exc))
                continue
            except (httpx.HTTPError, ValueError):
                failures.append(f"{provider} 连接失败")
                continue
            if results:
                return await rerank_results(query, results[:limit], client)
        if failures:
            # ddgs reports "no results" both for empty searches and for engines that blocked the request.
            raise WebError("搜索没有返回结果：" + "；".join(failures) + "。换个关键词或稍后再试")
        return []
    finally:
        if own:
            await client.aclose()


# Proxy tools in fake-IP mode (Clash, Surge…) answer every name with an address from these ranges
# and resolve the real one themselves, so they are allowed for names (never as literal IPs). Residual
# risk: behind such a proxy, a public name that points at 127.0.0.1 can't be told apart here.
FAKE_IP_NETS = [ipaddress.ip_network("198.18.0.0/15"), ipaddress.ip_network("fdfe:dcba:9876::/48")]
LOCAL_NAMES = re.compile(r"(^|\.)(localhost|local|lan|internal|intranet|home|corp)$", re.I)


async def resolve(host: str, port: int | None) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port or None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise WebError(f"找不到网站 {host}") from None
    return [ipaddress.ip_address(info[4][0]) for info in infos]


async def check_public(url: str) -> None:
    """Reject anything but http(s) to public addresses (no localhost, LAN, link-local, metadata)."""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    if parts.scheme not in ("http", "https") or not host:
        raise WebError("只能打开 http/https 网页")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise WebError("不能访问本机或内网地址")
        return
    if LOCAL_NAMES.search(host.rstrip(".")):
        raise WebError("不能访问本机或内网地址")
    for ip in await resolve(host, parts.port):
        if not ip.is_global and not any(ip in net for net in FAKE_IP_NETS):
            raise WebError("不能访问本机或内网地址")


@dataclass
class Page:
    url: str
    title: str
    text: str


async def fetch(url: str, *, client: httpx.AsyncClient | None = None) -> Page:
    """Fetch a page and extract its main text. Redirects are followed by hand so each hop is checked."""
    import trafilatura

    own = client is None
    client = client or httpx.AsyncClient(timeout=15, headers=HEADERS, trust_env=False, follow_redirects=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            await check_public(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urllib.parse.urljoin(url, response.headers.get("location", ""))
                    continue
                if response.status_code >= 400:
                    raise WebError(f"网页返回 HTTP {response.status_code}" + ("（网站拒绝了自动访问）" if response.status_code in (401, 403) else ""))
                kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if kind and kind not in TEXT_TYPES:
                    raise WebError(f"不是网页（{kind}）")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        break
                raw = body.decode(response.encoding or "utf-8", errors="replace")
                break
        else:
            raise WebError("跳转次数过多")
    except httpx.HTTPError:
        raise WebError("网页打开失败（连接错误或超时）") from None
    finally:
        if own:
            await client.aclose()
    if kind == "text/plain":
        return Page(url, url, raw.strip())
    title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    text = trafilatura.extract(raw, include_comments=False, include_tables=True, favor_recall=True) or ""
    return Page(url, _text(title.group(1)) if title else url, text.strip())
