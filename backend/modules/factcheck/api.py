"""HTTP adapter for fact-check reports; the app supplies job/model/storage access."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from modules import log
from modules.llm import LLMError
from .run import run_factcheck


def sse(event):
    import json
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


class FactCheckRequest(BaseModel):
    web: bool = True     # may the verifier search the web for authoritative sources
    papers: bool = True  # may it search scholarly papers (PubMed / OpenAlex)


def create_router(*, find_job, get_llm, store):
    router = APIRouter()

    @router.post("/api/link-jobs/{job_id}/factcheck")
    async def factcheck(job_id: str, body: FactCheckRequest):
        """SSE stream of a fact-check report: factcheck.started / claims_extracted /
        claim.verifying / claim.done / completed | error (see modules/factcheck/run.py)."""
        run_id = uuid.uuid4().hex[:12]

        async def stream():
            job = find_job(job_id)
            if job is None:
                yield sse({"type": "factcheck.error", "run_id": run_id, "code": "job_not_found",
                           "message": "这个会话已被删除，请重新解析链接"})
                return
            try:
                client = get_llm()
            except LLMError as err:
                yield sse({"type": "factcheck.error", "run_id": run_id, **err.as_dict()})
                return
            timer = log.Timer()
            try:
                async for event in run_factcheck(job, client, web=body.web, papers=body.papers):
                    if event.get("type") == "factcheck.completed":
                        report = event.get("report")
                        if not isinstance(report, dict):
                            raise ValueError("completed event has no report")
                        store.add_message(job.id, "assistant", "科普核查报告已生成", status="done",
                                          data={"events": [], "factcheck": report, "manual": "factcheck"})
                        log.event("factcheck", run_id=run_id, job_id=job.id,
                                  claims=report.get("summary", {}).get("total", 0), ms=timer.ms)
                    yield sse(event)
            except Exception as exc:
                log.error("factcheck", exc, run_id=run_id, job_id=job.id)
                yield sse({"type": "factcheck.error", "run_id": run_id, "code": "internal",
                           "message": "后端出错了，详情见日志"})
                return

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


    @router.get("/api/link-jobs/{job_id}/factcheck")
    async def get_factcheck(job_id: str):
        """The most recent fact-check report saved in this session, if any."""
        job = find_job(job_id)
        if job is None:
            raise HTTPException(404, "任务不存在或已删除")
        for msg in reversed(store.messages(job.id)):
            if msg.get("factcheck"):
                return msg["factcheck"]
        raise HTTPException(404, "还没有核查报告")

    return router
