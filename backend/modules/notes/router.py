"""Background note writing and the HTTP routes of the notes module (app.py only registers it).

    GET  /api/link-jobs/{id}/notes         status, progress, the note and the editor's board
    POST /api/link-jobs/{id}/notes         write it (again); returns at once, status running
    PUT  /api/link-jobs/{id}/notes/board   save the editor's arrangement
    GET  /api/link-jobs/{id}/notes/export  Markdown + pictures as a zip

Nothing is written until asked: a note costs one model call per section.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse, Response

from modules import log
from modules.agent.tools import AgentTools
from modules.chapters import load as load_chapters
from modules.llm import LLMError, Usage

from . import export
from .task import BOARD, FILE, build_note, clock, load, write

MAX_BOARD_BYTES = 2_000_000
PICTURES = 3  # sampled frames per section shown to the model
CHAPTER_WAIT = 180.0  # seconds to wait for chapters still being built before using even stretches


FIGURE_WIDTH = 1600  # px a note's figure is read at (the stream's own width when smaller)


class NotesService:
    def __init__(self, get_job, spawn, get_client, chapters_busy=lambda job_id: False):
        self.get_job = get_job
        self.chapters_busy = chapters_busy  # job id → chapters still being built (they're written when done)
        self.spawn = spawn
        self.get_client = get_client
        self.running: set[str] = set()
        self.router = APIRouter()
        self.router.add_api_route("/api/link-jobs/{job_id}/notes", self.get, methods=["GET"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes", self.post, methods=["POST"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/board", self.put_board, methods=["PUT"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/export", self.export, methods=["GET"])

    # ---- generation ---------------------------------------------------------------------------
    async def _inputs_ready(self, job) -> dict | None:
        """Wait for speech and on-screen text; then the chapters if they are on their way."""
        while any(x is not None and x.status in {"pending", "running"} for x in (job.transcript, job.screentext)):
            await asyncio.sleep(2)
        deadline = time.monotonic() + CHAPTER_WAIT
        while self.chapters_busy(job.id) and time.monotonic() < deadline:
            await asyncio.sleep(2)
        record = load_chapters(job.root)
        return record if record is not None and record.get("status") == "done" else None

    async def _frame(self, job, t: float) -> str | None:
        """A picture of the moment: read from the video as wide as it comes (up to FIGURE_WIDTH; the
        640 px keyframes look blurred in a note), else at keyframe size, else the nearest keyframe."""
        tools = AgentTools(job)
        name = f"{int(t * 100):08d}-hd.jpg"
        path = job.root / "extra" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() or await tools.sharp(t, path, FIGURE_WIDTH):
            return f"/api/link-jobs/{job.id}/extra/{name}"
        result = await tools.run("view_frames", {"start": t, "end": t, "count": 1})
        if result.data.get("frames"):
            return result.data["frames"][0]
        ok = [s for s in job.slots if s.status == "ok" and job.frame_path(s.index).is_file()]
        if not ok:
            return None
        nearest = min(ok, key=lambda s: abs(s.time - t))
        return f"/api/link-jobs/{job.id}/frames/{nearest.index}.jpg"

    def _pictures(self, job, start: float, end: float, n: int = PICTURES) -> list[tuple[str, object]]:
        """Up to n sampled frames spread over [start, end), labelled with their time, for the model to read."""
        inside = [s for s in job.in_time_order() if s.status == "ok" and start <= s.time < end and job.frame_path(s.index).is_file()]
        if len(inside) > n:
            step = (len(inside) - 1) / (n - 1)
            inside = [inside[round(i * step)] for i in range(n)]
        return [(f"画面 · {clock(s.time)}", job.frame_path(s.index)) for s in inside]

    async def build(self, job) -> None:
        timer = log.Timer()
        state = {"status": "running", "message": "等待语音转写和画面文字…", "progress": {"done": 0, "total": 0}, "note": None}
        previous = load(job.root)
        if previous and previous.get("note"):
            state["previous"] = True
        write(job.root, state)
        try:
            client = self.get_client()

            async def complete(messages):
                parts = []
                async for delta in client.stream(messages, Usage(), max_tokens=3000):
                    parts.append(delta)
                return "".join(parts)

            chapters = await self._inputs_ready(job)
            chapter_list = (chapters or {}).get("chapters") or None

            def progress(done, total, message):
                write(job.root, {**state, "message": message, "progress": {"done": done, "total": total}})

            note = await build_note(title=job.video.title or "", duration=job.video.duration or 0,
                                    transcript=job.transcript.segments if job.transcript else [],
                                    screen=job.screentext.segments if job.screentext else [],
                                    chapters=chapter_list, complete=complete,
                                    grab=lambda t: self._frame(job, t), progress=progress,
                                    pictures=lambda a, b: self._pictures(job, a, b))
            write(job.root, {"status": "done", "message": f"已整理 {len(note['sections'])} 节", "progress": {}, "note": note,
                             "made": time.time()})
            (job.root / BOARD).unlink(missing_ok=True)  # a new note starts from its own layout
            log.event("notes", job_id=job.id, sections=len(note["sections"]),
                      figures=sum(len(s["figures"]) for s in note["sections"]), ms=timer.ms)
        except LLMError as err:
            write(job.root, {"status": "failed", "message": f"模型不可用：{err.message}", "progress": {}, "note": None})
        except Exception as exc:  # noqa: BLE001
            log.error("notes", exc, job_id=job.id)
            write(job.root, {"status": "failed", "message": str(exc)[:120] if isinstance(exc, ValueError) else "笔记生成失败",
                             "progress": {}, "note": None})
        finally:
            self.running.discard(job.id)

    # ---- routes -------------------------------------------------------------------------------
    def _state(self, job) -> dict:
        record = load(job.root) or {"status": "none", "message": "", "progress": {}, "note": None}
        if record.get("status") == "running" and job.id not in self.running:  # cut off by a restart
            record = {"status": "failed", "message": "生成被中断（后端重启），请重新生成", "progress": {}, "note": None}
        return {**record, "board": load(job.root, BOARD)}

    async def get(self, job_id: str):
        return self._state(self.get_job(job_id))

    async def post(self, job_id: str, body: dict | None = Body(default=None)):
        job = self.get_job(job_id)
        if job.id not in self.running:
            self.running.add(job.id)
            self.spawn(self.build(job))
            await asyncio.sleep(0)
        return {**self._state(job), "status": "running"}

    async def put_board(self, job_id: str, board: dict = Body(...)):
        job = self.get_job(job_id)
        if not isinstance(board.get("blocks"), list) or len(board["blocks"]) > 600:
            raise HTTPException(422, "画布内容格式不对")
        raw = json.dumps(board, ensure_ascii=False)
        if len(raw.encode()) > MAX_BOARD_BYTES:
            raise HTTPException(413, "画布内容太大")
        if (load(job.root) or {}).get("status") != "done":
            raise HTTPException(409, "还没有生成好的笔记")
        write(job.root, {**board, "saved": time.time()}, BOARD)
        return {"saved": time.time()}

    async def export(self, job_id: str, preview: bool = False, image: bool = False):
        """The note as a zip (笔记.md + images/); with preview=1 as a page showing what it will read like;
        with image=1 as that page in one long PNG (a phone keeps it in its photos)."""
        job = self.get_job(job_id)
        record = load(job.root) or {}
        if record.get("status") != "done" or not record.get("note"):
            raise HTTPException(409, "还没有生成好的笔记")

        def picture(src: str):
            m = re.search(r"/(extra/\d{8}(?:-hd)?\.jpg|frames/(\d+)\.jpg|replay/[\d-]+/\d{2}\.jpg)$", src)
            if not m:
                return None
            path = job.frame_path(int(m.group(2))) if m.group(2) else job.root / m.group(1)
            root = job.root.resolve()
            return path if path.is_file() and root in path.resolve().parents else None

        if preview or image:
            page = export.to_preview_html(record["note"], load(job.root, BOARD), picture)
            if not image:
                return HTMLResponse(page)
            try:
                png = await export.to_long_image(page)
            except export.ImageError as exc:
                raise HTTPException(503, str(exc))
            title = (record["note"].get("title") or "笔记")[:60]
            return Response(png, media_type="image/png",
                            headers={"Content-Disposition": f"inline; filename=notes.png; filename*=UTF-8''{quote(title)}.png"})
        data, title = export.to_zip(record["note"], load(job.root, BOARD), picture)
        name = re.sub(r'[\\/:*?"<>|]+', " ", title).strip()[:60] or "笔记"
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": f"attachment; filename=notes.zip; filename*=UTF-8''{quote(name)}.zip"})
