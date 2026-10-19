"""核查报告主流程：抽取说法 → 逐条检索核实 → 生成报告，以 SSE 事件流返回进度。

事件协议（沿用前端 §9.2 trace 风格，前缀 factcheck.*）：
  factcheck.started          {run_id, job_id, transcript_segments, screentext_segments}
  factcheck.claims_extracted {run_id, count}
  factcheck.claim.verifying  {run_id, claim_id, claim}
  factcheck.claim.done       {run_id, claim_id, verdict, risk}
  factcheck.completed        {run_id, report}
  factcheck.error            {run_id, code, message}

网页内容一律当作不可信数据；检索摘要先经独立注入筛查，只有通过筛查的来源进入判定和报告。
"""
from __future__ import annotations

import asyncio
import re
import uuid
from itertools import zip_longest
from collections.abc import AsyncIterator

from modules.frames import FrameJob
from modules.llm import ChatClient, LLMError, OllamaClient, Usage

from . import extract, report, verify
from .extract import Ask

# 每条说法检索的来源上限
SOURCES_PER_CLAIM = 6
# 一次核查最多抽取的说法条数（防止长视频产生过多调用）
MAX_CLAIMS = 20


ASK_TRIES = 3
ASK_PAUSE = 4.0  # seconds before the second try, doubled for the third


async def _ask(client: ChatClient | OllamaClient, messages: list[dict], max_tokens: int) -> str:
    """用流式客户端收集一次完整文本回复。

    A provider hiccup (timeout, network, busy) or an empty reply is tried again, up to ASK_TRIES
    times: a check that failed on it reported "no claims" or an extraction error for a whole video.
    """
    for attempt in range(ASK_TRIES):
        usage = Usage()
        chunks: list[str] = []
        try:
            async for delta in client.stream(messages, usage, max_tokens=max_tokens):
                chunks.append(delta)
        except LLMError as exc:
            if not exc.retryable or attempt == ASK_TRIES - 1:
                raise
        else:
            text = "".join(chunks)
            if text.strip() or attempt == ASK_TRIES - 1:
                return text
        await asyncio.sleep(ASK_PAUSE * 2 ** attempt)
    return ""


CJK = re.compile(r"[\u4e00-\u9fff]")
TERMS_SYSTEM = """把用户给的一条健康/科普说法转成英文医学文献检索词，用于 PubMed。
只输出 2 到 6 个英文检索词，用空格分隔，不要解释、不要标点、不要引号。
例：说法「每天空腹喝一勺白醋能治好高血压」→ vinegar hypertension blood pressure"""
STOP = {"and", "or", "the", "of", "in", "on", "for", "with", "to", "a", "an", "effect", "effects"}


async def paper_terms(ask: Ask, claim: str) -> str:
    """English search terms for a claim's literature search; the claim itself if it is already
    English, "" when a Chinese claim couldn't be put into English (then papers aren't searched:
    OpenAlex answers a Chinese sentence with unrelated works)."""
    if not CJK.search(claim):
        return claim
    try:
        raw = await ask([{"role": "system", "content": TERMS_SYSTEM}, {"role": "user", "content": claim[:300]}], 40)
    except Exception:
        return ""
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", raw or "")
    return " ".join(words[:8]) if len(words) >= 2 else ""


def on_topic(terms: str, title: str, abstract: str) -> bool:
    """A paper shares at least one meaningful search term (or its stem) with the query."""
    text = f"{title} {abstract}".lower()
    keys = [w.lower() for w in terms.split() if len(w) > 3 and w.lower() not in STOP]
    return not keys or any(k[:max(5, len(k) - 2)] in text for k in keys)


async def _search(query: str, limit: int, *, web: bool, papers: bool, terms: str | None = None) -> list[dict]:
    """组合网页 + 学术论文检索，返回 build_source 格式列表。任一来源失败不影响整体。
    terms：论文检索用的英文检索词（None 时用 query 本身；空串时不检索论文）。"""
    terms = query if terms is None else terms
    web_sources: list[dict] = []
    paper_sources: list[dict] = []
    if web:
        try:
            from modules.agent.web import search as web_search
            results = await web_search(query, limit=limit)
            # Most authoritative first (unknown counts as middling); low-authority pages only fill gaps.
            level = lambda r: getattr(r, "authority", None)  # noqa: E731 — only DeepSeek's results carry it
            results = sorted(results, key=lambda r: -(level(r) if level(r) is not None else 2))
            solid = [r for r in results if level(r) is None or level(r) >= 2]
            for r in (solid if len(solid) >= 3 else results):
                web_sources.append(report.build_source(r.title, r.url, r.snippet, level(r), getattr(r, "site", "")))
        except Exception:
            pass
    if papers and terms:
        try:
            from modules.agent.papers import search_papers
            for source in ("pubmed", "openalex"):
                try:
                    found = [p for p in await search_papers(terms, limit=limit, source=source)
                             if on_topic(terms, p.title, p.abstract)]
                    for p in found:
                        paper_sources.append(report.build_source(p.title, p.url, p.abstract[:300]))
                    if found:
                        break
                except Exception:
                    continue
        except Exception:
            pass
    # Interleave before limiting so a full web response cannot exclude all scholarly sources.
    out = [source for pair in zip_longest(web_sources, paper_sources) for source in pair if source is not None]
    # 去重（同 URL）
    seen, dedup = set(), []
    for s in out:
        if s["url"] and s["url"] not in seen:
            seen.add(s["url"])
            dedup.append(s)
    return dedup[:limit]


def _segments(job: FrameJob) -> tuple[list[dict], list[dict]]:
    t = job.transcript.as_dict() if job.transcript else {"segments": []}
    s = job.screentext.as_dict() if job.screentext else {"segments": []}
    return t.get("segments") or [], s.get("segments") or []


def pending_content_error(job: FrameJob) -> dict | None:
    """Shared preflight: content readiness takes precedence over model initialization."""
    if any(getattr(getattr(job, name, None), "status", None) in ("pending", "running")
           for name in ("transcript", "screentext")):
        return {"code": "content_not_ready", "message": "语音转写或画面文字识别尚未完成，请完成后重试核查。",
                "retryable": True}
    return None


async def run_factcheck(
    job: FrameJob,
    client: ChatClient | OllamaClient,
    *,
    web: bool = True,
    papers: bool = True,
    ask: Ask | None = None,
    search=None,
) -> AsyncIterator[dict]:
    """运行核查并 yield 事件。ask/search 可注入用于测试。"""
    run_id = uuid.uuid4().hex[:12]
    yield {"type": "factcheck.started", "run_id": run_id, "job_id": job.id}

    if error := pending_content_error(job):
        yield {"type": "factcheck.error", "run_id": run_id, **error}
        return

    t_segs, s_segs = _segments(job)
    if not t_segs and not s_segs:
        yield {"type": "factcheck.error", "run_id": run_id, "code": "no_content",
               "message": "转写和画面文字都还没有，无法抽取说法。请等视频解析完成后再核查。"}
        return

    do_ask = ask or (lambda m, n: _ask(client, m, n))

    async def do_search(query: str, limit: int) -> list[dict]:
        if search is not None:
            return await search(query, limit)
        terms = await paper_terms(do_ask, query) if papers else ""
        return await _search(query, limit, web=web, papers=papers, terms=terms)

    # 1. 抽取说法
    try:
        raw_claims = await extract.extract_claims(do_ask, t_segs, s_segs)
    except Exception as exc:
        yield {"type": "factcheck.error", "run_id": run_id, "code": "extract_failed",
               "message": f"说法抽取失败：{str(exc)[:120]}"}
        return
    raw_claims = raw_claims[:MAX_CLAIMS]
    yield {"type": "factcheck.claims_extracted", "run_id": run_id, "count": len(raw_claims)}
    if not raw_claims:
        rpt = report.build_report(job.id, job.video.public(), [], status="done",
                                  message="未发现可核实的事实性说法。")
        yield {"type": "factcheck.completed", "run_id": run_id, "report": rpt}
        return

    # 2. 逐条核实
    claims: list[dict] = []
    for i, rc in enumerate(raw_claims):
        cid = f"c{i + 1}"
        yield {"type": "factcheck.claim.verifying", "run_id": run_id, "claim_id": cid, "claim": rc["claim"]}
        try:
            srcs = await verify.gather_sources(do_search, rc["claim"], SOURCES_PER_CLAIM)
            verdict = await verify.verify_claim(do_ask, rc["claim"], srcs)
            srcs = verdict["sources"]
        except Exception:
            srcs, verdict = [], {"verdict": "unverifiable", "risk": "low", "reason": "核实过程出错。"}
        claim = report.build_claim(
            cid=cid,
            claim=rc["claim"],
            original_text=rc["original_text"],
            start=rc["start"],
            end=rc["end"],
            evidence_source=rc["source"],
            segment_index=rc["segment_index"],
            verdict=verdict["verdict"],
            risk=verdict["risk"],
            reason=verdict["reason"],
            srcs=srcs,
            status="verified" if srcs and verdict["verdict"] != "unverifiable" else "unverified",
        )
        claims.append(claim)
        yield {"type": "factcheck.claim.done", "run_id": run_id, "claim_id": cid,
               "verdict": claim["verdict"], "risk": claim["risk"]}

    # 3. 生成报告
    rpt = report.build_report(job.id, job.video.public(), claims, status="done")
    yield {"type": "factcheck.completed", "run_id": run_id, "report": rpt}
