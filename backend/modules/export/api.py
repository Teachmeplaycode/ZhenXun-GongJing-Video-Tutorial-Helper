"""HTTP adapter for note bundles and browser-print HTML; format=pdf is not PDF bytes."""
from __future__ import annotations

import json
import re
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from . import build_markdown, build_print_html, build_zip


def create_router(*, store, get_job, data_dir):
    router = APIRouter()

    @router.get("/api/sessions/{session_id}/export")
    async def export_session(session_id: str, request: Request, format: Literal["md", "pdf"] = "md", ids: str | None = None):
        job = get_job(session_id)
        record = store.get(session_id)
        if record is None:
            raise HTTPException(404, "会话不存在")
        messages = store.messages(session_id)
        selected = None
        if ids is not None:
            if not re.fullmatch(r"[1-9][0-9]*(?:,[1-9][0-9]*)*", ids):
                raise HTTPException(400, "请选择至少一条有效的已保存消息")
            try:
                selected = {int(value) for value in ids.split(",")}
            except ValueError:
                raise HTTPException(400, "消息编号无效")
            if not selected.issubset({message["id"] for message in messages}):
                raise HTTPException(400, "所选消息不属于此会话，请重新打开导出")
        video, slots = json.loads(record["video"]), json.loads(record["slots"])
        if format == "pdf":
            page = build_print_html(video, record["task"], messages, job.snapshot()["slots"], session_id,
                                    str(request.base_url).rstrip("/"), selected, data_dir=data_dir)
            return HTMLResponse(page)
        markdown, refs = build_markdown(video, record["task"], messages, slots, session_id, data_dir, selected)
        return Response(build_zip(markdown, refs), media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=\"note.zip\"; filename*=UTF-8''{quote('笔记.zip')}",
        })

    return router
