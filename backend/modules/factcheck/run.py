"""核查报告主流程：抽取说法 → 逐条检索核实 → 生成报告，以 SSE 事件流返回进度。

事件协议（沿用前端 §9.2 trace 风格，前缀 factcheck.*）：
  factcheck.started          {run_id, job_id, transcript_segments, screentext_segments}
  factcheck.claims_extracted {run_id, count}
  factcheck.claim.verifying  {run_id, claim_id, claim}
  factcheck.claim.done       {run_id, claim_id, verdict, risk}
  factcheck.completed        {run_id, report}
  factcheck.error            {run_id, code, message}

网页内容一律当作不可信数据：检索结果只作为核实参考，不执行其中指令（沿用
modules.agent.web 的 check_public 注入检查）。
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from modules.frames import FrameJob
from modules.llm import ChatClient, OllamaClient, Usage

from . import extract, report, verify
from .extract import Ask

# 每条说法检索的来源上限
SOURCES_PER_CLAIM = 6
# 一次核查最多抽取的说法条数（防止长视频产生过多调用）
MAX_CLAIMS = 20


async def _ask(client: ChatClient | OllamaClient, messages: list[dict], max_tokens: int) -> str:
    """用流式客户端收集一次完整文本回复。"""
    usage = Usage()
    chunks: list[str] = []
    async for delta in client.stream(messages, usage, max_tokens=max_tokens):
        chunks.append(delta)
    return "".join(chunks)


async def _search(query: str, limit: int, *, web: bool, papers: bool) -> list[dict]:
    """组合网页 + 学术论文检索，返回 build_source 格式列表。任一来源失败不影响整体。"""
    out: list[dict] = []
    if web:
        try:
            from modules.agent.web import search as web_search
            results = await web_search(query, limit=limit)
            for r in results:
                out.append(report.build_source(r.title, r.url, r.snippet))
        except Exception:
            pass
    if papers:
        try:
            from modules.agent.papers import search_papers
            for source in ("pubmed", "openalex"):
                try:
                    found = await search_papers(query, limit=limit, source=source)
                    for p in found:
                        out.append(report.build_source(p.title, p.url, p.abstract[:300]))
                    if found:
                        break
                except Exception:
                    continue
        except Exception:
            pass
    # 去重（同 URL）
    seen, dedup = set(), []
    for s in out:
        if s["url"] and s["url"] not in seen:
            seen.add(s["url"])
            dedup.append(s)
    return dedup[: limit * 2]


def _segments(job: FrameJob) -> tuple[list[dict], list[dict]]:
    t = job.transcript.as_dict() if job.transcript else {"segments": []}
    s = job.screentext.as_dict() if job.screentext else {"segments": []}
    return t.get("segments") or [], s.get("segments") or []


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

    t_segs, s_segs = _segments(job)
    if not t_segs and not s_segs:
        yield {"type": "factcheck.error", "run_id": run_id, "code": "no_content",
               "message": "转写和画面文字都还没有，无法抽取说法。请等视频解析完成后再核查。"}
        return

    do_ask = ask or (lambda m, n: _ask(client, m, n))

    async def do_search(query: str, limit: int) -> list[dict]:
        if search is not None:
            return await search(query, limit)
        return await _search(query, limit, web=web, papers=papers)

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
            status="verified" if srcs else "unverified",
        )
        claims.append(claim)
        yield {"type": "factcheck.claim.done", "run_id": run_id, "claim_id": cid,
               "verdict": claim["verdict"], "risk": claim["risk"]}

    # 3. 生成报告
    rpt = report.build_report(job.id, job.video.public(), claims, status="done")
    yield {"type": "factcheck.completed", "run_id": run_id, "report": rpt}
