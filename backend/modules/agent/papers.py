"""Scholarly search: OpenAlex (all fields, with abstracts and citation counts), PubMed (biomedicine) and arXiv
(preprints). Semantic Scholar answers 429 to unauthenticated requests, and Crossref rarely has abstracts.

  NCBI_API_KEY     optional; PubMed allows 3 requests/s without a key, 10 with one

  OPENALEX_API_KEY free key from openalex.org/settings/api. Since 2026-02-13 OpenAlex bills usage: a
                   search costs $0.001; without a key the daily budget is $0.10 (~100 searches), with a
                   free key $1 (~1,000 searches), reset at midnight UTC.
  OPENALEX_MAILTO  optional contact address
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from modules.settings import settings

from .web import HEADERS, Pacer, WebError, rerank

ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ABSTRACT_CHARS = 600
ARXIV_PACE = Pacer(3.0)  # arXiv asks API users for at most one request every 3 seconds
PUBMED_PACE = Pacer(0.4)  # 3 requests/s without an NCBI key
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class Paper:
    title: str
    year: int | None
    authors: list[str]
    venue: str
    citations: int | None
    url: str
    pdf: str
    abstract: str

    def line(self, i: int) -> str:
        names = "、".join(self.authors[:3]) + (" 等" if len(self.authors) > 3 else "")
        meta = " · ".join(str(x) for x in (self.year, self.venue, f"被引 {self.citations}" if self.citations is not None else None) if x)
        text = f"{i}. {self.title}\n   {names}{' · ' if names and meta else ''}{meta}\n   {self.url}"
        if self.pdf and self.pdf != self.url:
            text += f"\n   PDF: {self.pdf}"
        if self.abstract:
            text += f"\n   摘要：{self.abstract[:ABSTRACT_CHARS]}{'…' if len(self.abstract) > ABSTRACT_CHARS else ''}"
        return text


def _abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted:
        return ""
    words = sorted((pos, word) for word, positions in inverted.items() for pos in positions)
    return " ".join(word for _, word in words)


async def openalex(query: str, limit: int, client: httpx.AsyncClient) -> list[Paper]:
    params = {"search": query, "per-page": limit, "select": "id,doi,display_name,publication_year,authorships,"
              "primary_location,cited_by_count,abstract_inverted_index,open_access"}
    config = settings()
    if config.get("OPENALEX_MAILTO"):
        params["mailto"] = config["OPENALEX_MAILTO"]
    if config.get("OPENALEX_API_KEY"):
        params["api_key"] = config["OPENALEX_API_KEY"]
    response = await client.get("https://api.openalex.org/works", params=params)
    if response.status_code == 429:
        raise WebError("OpenAlex 今天的免费额度已用完（不带 key 约 100 次检索/天），可在 .env 配置 OPENALEX_API_KEY 或改用 arXiv")
    if response.status_code != 200:
        raise WebError(f"OpenAlex 返回 HTTP {response.status_code}")
    papers = []
    for w in response.json().get("results", []):
        source = ((w.get("primary_location") or {}).get("source") or {})
        papers.append(Paper(
            title=w.get("display_name") or "", year=w.get("publication_year"),
            authors=[(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []],
            venue=source.get("display_name") or "", citations=w.get("cited_by_count"),
            url=w.get("doi") or w.get("id") or "", pdf=(w.get("open_access") or {}).get("oa_url") or "",
            abstract=_abstract(w.get("abstract_inverted_index")),
        ))
    return papers


async def arxiv(query: str, limit: int, client: httpx.AsyncClient) -> list[Paper]:
    async with ARXIV_PACE:
        response = await client.get("https://export.arxiv.org/api/query",
                                    params={"search_query": f"all:{query}", "max_results": limit, "sortBy": "relevance"})
    if response.status_code != 200:
        raise WebError(f"arXiv 返回 HTTP {response.status_code}")
    root = ET.fromstring(response.text)
    papers = []
    for e in root.findall("a:entry", ATOM):
        text = lambda tag: " ".join((e.findtext(tag, "", ATOM) or "").split())  # noqa: E731
        pdf = next((l.get("href") for l in e.findall("a:link", ATOM) if l.get("title") == "pdf"), "")
        papers.append(Paper(
            title=text("a:title"), year=int(text("a:published")[:4]) if text("a:published") else None,
            authors=[a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)],
            venue="arXiv " + (e.find("arxiv:primary_category", ATOM).get("term") if e.find("arxiv:primary_category", ATOM) is not None else ""),
            citations=None, url=text("a:id"), pdf=pdf, abstract=text("a:summary"),
        ))
    return papers


async def pubmed(query: str, limit: int, client: httpx.AsyncClient) -> list[Paper]:
    """esearch for PMIDs by relevance, then efetch their records (title, abstract, journal, year, DOI)."""
    key = settings().get("NCBI_API_KEY", "")
    base = {"db": "pubmed", "tool": "gongjing"} | ({"api_key": key} if key else {})
    pace = PUBMED_PACE if not key else Pacer(0.12)
    async with pace:
        found = await client.get(f"{EUTILS}/esearch.fcgi", params=base | {"term": query, "retmode": "json", "retmax": limit, "sort": "relevance"})
    if found.status_code != 200:
        raise WebError(f"PubMed 返回 HTTP {found.status_code}")
    ids = (found.json().get("esearchresult") or {}).get("idlist") or []
    if not ids:
        return []
    async with pace:
        fetched = await client.get(f"{EUTILS}/efetch.fcgi", params=base | {"id": ",".join(ids), "retmode": "xml"})
    if fetched.status_code != 200:
        raise WebError(f"PubMed 返回 HTTP {fetched.status_code}")
    papers = []
    for art in ET.fromstring(fetched.content).findall(".//PubmedArticle"):
        cite = art.find("MedlineCitation")
        pmid = cite.findtext("PMID", "")
        article = cite.find("Article")
        year = article.findtext("Journal/JournalIssue/PubDate/Year") or (article.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
        parts = []
        for node in article.findall("Abstract/AbstractText"):
            text = "".join(node.itertext()).strip()
            parts.append(f"{node.get('Label')}: {text}" if node.get("Label") else text)
        doi = next((i.text for i in art.findall("PubmedData/ArticleIdList/ArticleId") if i.get("IdType") == "doi"), "")
        authors = [f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip() or a.findtext("CollectiveName", "")
                   for a in article.findall("AuthorList/Author")]
        papers.append(Paper(
            title="".join(article.find("ArticleTitle").itertext()).strip() if article.find("ArticleTitle") is not None else "",
            year=int(year) if year.isdigit() else None, authors=[a for a in authors if a],
            venue=article.findtext("Journal/Title", ""), citations=None,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", pdf=f"https://doi.org/{doi}" if doi else "",
            abstract=" ".join(parts),
        ))
    order = {pmid: i for i, pmid in enumerate(ids)}  # efetch doesn't keep the relevance order
    return sorted(papers, key=lambda p: order.get(p.url.rstrip("/").rsplit("/", 1)[-1], len(order)))


SOURCES = {"openalex": openalex, "pubmed": pubmed, "arxiv": arxiv}


async def search_papers(query: str, limit: int = 6, source: str = "openalex", *,
                        client: httpx.AsyncClient | None = None) -> list[Paper]:
    own = client is None
    client = client or httpx.AsyncClient(timeout=20, headers=HEADERS, trust_env=False, follow_redirects=True)
    try:
        found = await SOURCES.get(source, openalex)(query, limit, client)
        ranked = await rerank(query, [f"{p.title}\n{p.abstract[:800]}" for p in found], client)
        return [found[i] for i, _ in ranked] if ranked else found
    except httpx.HTTPError:
        raise WebError("无法连接论文检索服务，请检查网络") from None
    except ET.ParseError:
        raise WebError(f"{source} 返回了无法解析的内容") from None
    finally:
        if own:
            await client.aclose()
