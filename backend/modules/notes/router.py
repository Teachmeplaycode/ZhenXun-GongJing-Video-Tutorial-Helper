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
import math
import re
import time
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse, Response

from modules import log
from modules.agent.tools import AgentTools
from modules import steps as step_cards
from modules.chapters import load as load_chapters
from modules.llm import LLMError, Usage

from . import export
from .task import BOARD, FILE, build_note, clock, load, write
from .discussion import build_discussion_note, selected_turns
from .revisions import archive, commit_current, effective_note, fingerprint, history_snapshot, recover_commit, revision_board

MAX_BOARD_BYTES = 2_000_000
PICTURES = 3  # sampled frames per section shown to the model
FIRST_MATERIAL_WAIT = 8.0  # wait only for the first usable evidence, never all OCR/chapters


FIGURE_WIDTH = 1600  # px a note's figure is read at (the stream's own width when smaller)


class NotesService:
    def __init__(self, get_job, spawn, get_client, chapters_busy=lambda job_id: False,
                 get_messages=lambda job_id: [], own_job=None):
        self.get_job = get_job
        self.chapters_busy = chapters_busy  # job id → chapters still being built (they're written when done)
        self.spawn = spawn
        self.get_client = get_client
        self.get_messages = get_messages
        self.own_job = own_job or get_job
        self.running: set[str] = set()
        self.router = APIRouter()
        self.router.add_api_route("/api/link-jobs/{job_id}/notes", self.get, methods=["GET"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes", self.post, methods=["POST"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/board", self.put_board, methods=["PUT"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/export", self.export, methods=["GET"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/revisions/{revision_id}/apply", self.apply, methods=["POST"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/draft", self.discard, methods=["DELETE"])
        self.router.add_api_route("/api/link-jobs/{job_id}/notes/revisions/{revision_id}/restore", self.restore, methods=["POST"])

    # ---- generation ---------------------------------------------------------------------------
    def _has_material(self, job) -> bool:
        return (any(state and any(seg.text.strip() for seg in state.segments)
                    for state in (job.transcript, job.screentext)) or
                any(slot.status == "ok" and job.frame_path(slot.index).is_file() for slot in job.slots))

    async def _inputs_ready(self, job) -> dict | None:
        """Use ready evidence and any cached chapters; only an empty import waits briefly."""
        waited = 0.0
        while not self._has_material(job) and waited < FIRST_MATERIAL_WAIT:
            pending = any(x is not None and x.status in {"pending", "running"}
                          for x in (job.transcript, job.screentext)) or job.coverage()["pending"]
            if not pending:
                break
            await asyncio.sleep(2)
            waited += 2
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

    @staticmethod
    def _steps(job) -> list[dict]:
        """The video's step cards, when they have been built: material a note may draw on."""
        record = step_cards.load(job.root) or {}
        return record.get("steps") or [] if record.get("status") == "done" else []

    async def build(self, job, request: dict | None = None) -> None:
        timer = log.Timer()
        previous = load(job.root)
        request = request or {"source": "video", "message_ids": [], "instruction": "", "turns": [], "use_steps": False}
        base_board = load(job.root, BOARD)
        base_note = (previous or {}).get("note")
        base_revision = fingerprint(base_note, base_board)
        generation_id = uuid.uuid4().hex
        self.running.add(job.id)

        def update_generation(status, message, progress=None):
            # Re-read each time: an editor may save hand changes during a long model call.
            state = load(job.root) or {"note": None}
            generation = {"id": generation_id, "status": status, "message": message,
                          "progress": progress or {}}
            state.update(generation=generation, message=message, progress=progress or {},
                         status="done" if state.get("note") else ("running" if status == "running" else "failed"))
            write(job.root, state)

        update_generation("running", "正在整理已有画面和文字…", {"done": 0, "total": 0})
        try:
            client = self.get_client()

            async def complete(messages):
                parts = []
                async for delta in client.stream(messages, Usage(), max_tokens=3000):
                    parts.append(delta)
                return "".join(parts)

            chapters = await self._inputs_ready(job)
            if not self._has_material(job):
                raise ValueError("尚未取得可用画面或文字，请稍后再生成笔记")
            pending = [name for name, state in (("语音", job.transcript), ("画面文字", job.screentext))
                       if state is not None and state.status in {"pending", "running"}]
            if job.coverage()["pending"]:
                pending.append("画面")
            chapter_list = (chapters or {}).get("chapters") or None

            def progress(done, total, message):
                update_generation("running", message, {"done": done, "total": total})

            frame_gate = asyncio.Semaphore(3)

            async def grab(time):
                async with frame_gate:
                    return await self._frame(job, time)

            inputs = dict(title=job.video.title or "", duration=job.video.duration or 0,
                          transcript=job.transcript.segments if job.transcript else [],
                          screen=job.screentext.segments if job.screentext else [],
                          chapters=chapter_list, complete=complete, grab=grab,
                          progress=progress, pictures=lambda a, b: self._pictures(job, a, b),
                          steps=self._steps(job) if request.get("use_steps") else None)
            if request["source"] == "conversation" or base_note or request["instruction"]:
                turns = request.get("turns") or [{
                    "question": {"id": 0, "content": "结合原视频整体修订这份笔记，保留当前手改内容与批注，补齐相关要点。"},
                    "answer": {"id": 0, "content": "请以原素材为依据，现有笔记为基底，整理整段视频。"},
                }]
                async def discussion_pictures(start, end):
                    chosen = {i for turn in request.get("turns") or [] for i in turn["question"].get("frames") or []}
                    selected = [(f"用户所选原片画面 · {clock(s.time)}", job.frame_path(s.index)) for s in job.in_time_order()
                                if s.index in chosen and s.status == "ok" and start <= s.time < end and job.frame_path(s.index).is_file()]
                    sampled = selected + self._pictures(job, start, end)
                    unique, seen = [], set()
                    for label, path in sampled:
                        if path not in seen:
                            unique.append((label, path))
                            seen.add(path)
                    if unique:
                        return unique[:PICTURES]
                    # A focused follow-up may fall between cached frames. Read one actual moment
                    # before writing the section, rather than treating the prior AI answer as proof.
                    moment = (start + end) / 2
                    try:
                        src = await grab(moment)
                    except Exception:
                        return []  # ready transcription may still support this discussion section
                    match = re.search(r"/(extra/\d{8}(?:-hd)?\.jpg|frames/(\d+)\.jpg)$", src or "")
                    if not match:
                        return []
                    path = job.frame_path(int(match.group(2))) if match.group(2) else job.root / match.group(1)
                    if match.group(2):
                        slot = next((s for s in job.slots if s.index == int(match.group(2))), None)
                        if slot is None or not start <= slot.time < end:
                            return []
                        moment = slot.time
                    return [(f"原片画面 · {clock(moment)}", path)] if path.is_file() else []

                note, changed = await build_discussion_note(**{**inputs, "pictures": discussion_pictures}, turns=turns,
                    instruction=request["instruction"], current_note=base_note, current_board=base_board)
            else:
                note = await build_note(**inputs)
                changed = [s["id"] for s in note["sections"]]
            old_coverage = note.pop("coverage_note", "")
            if old_coverage and note.get("summary", "").startswith(old_coverage):
                note["summary"] = note["summary"][len(old_coverage):].lstrip()
            if pending:
                note["coverage_note"] = "本次按已有内容整理；" + "、".join(pending) + "尚未完成，可在完成后重新生成补充。"
                note["summary"] = note["coverage_note"] + ("\n\n" + note["summary"] if note.get("summary") else "")
            board = revision_board(note, base_board, changed) if base_board is not None else None
            original_ids = {s["id"] for s in (effective_note(base_note, base_board) or {}).get("sections") or []}
            changes = [("改写小节：" if s["id"] in original_ids else "新增小节：") + s["title"]
                       for s in note["sections"] if s["id"] in changed]
            used_steps = len(inputs["steps"] or [])
            if used_steps:
                changes.append(f"参考了 {used_steps} 张步骤卡")
            made = time.time()
            result = {"id": uuid.uuid4().hex, "note": note, "board": board, "changes": changes,
                      "base_revision": base_revision, "created": made, "source": request["source"],
                      "message_ids": request["message_ids"], "instruction": request["instruction"], "used_steps": used_steps}
            current = load(job.root) or {}
            if current.get("note"):
                current["draft"] = result
                current.update(status="done", message="修订已生成，请预览后更新当前笔记", progress={})
            else:
                current.update(status="done", note=note, draft=None, made=made,
                               source=request["source"], message_ids=request["message_ids"], used_steps=used_steps,
                               message=f"已整理 {len(note['sections'])} 节" + (f"，参考了 {used_steps} 张步骤卡" if used_steps else "")
                               + ("（部分内容仍在处理）" if pending else ""), progress={})
            current["generation"] = {"id": generation_id, "status": "done", "message": current["message"], "progress": {}}
            write(job.root, current)
            log.event("notes", job_id=job.id, sections=len(note["sections"]),
                      figures=sum(len(s["figures"]) for s in note["sections"]), ms=timer.ms)
        except LLMError as err:
            update_generation("failed", f"模型不可用：{err.message}")
        except asyncio.CancelledError:
            update_generation("failed", "生成已中断，当前笔记已保留，请重试")
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("notes", exc, job_id=job.id)
            update_generation("failed", str(exc)[:120] if isinstance(exc, ValueError) else "笔记生成失败，当前笔记已保留")
        finally:
            self.running.discard(job.id)

    # ---- routes -------------------------------------------------------------------------------
    def _state(self, job) -> dict:
        recover_commit(job.root)
        record = load(job.root) or {"status": "none", "message": "", "progress": {}, "note": None}
        board = load(job.root, BOARD)
        generation = record.get("generation")
        if (record.get("status") == "running" or (generation or {}).get("status") == "running") and job.id not in self.running:
            generation = {"status": "failed", "message": "生成被中断（后端重启），当前笔记已保留，请重新生成", "progress": {}}
            record = {**record, "status": "done" if record.get("note") else "failed",
                      "message": generation["message"], "progress": {}}
        revision = fingerprint(record.get("note"), board)
        draft = record.get("draft")
        if draft:
            draft = {**draft, "conflict": draft.get("base_revision") != revision}
        return {**record, "board": board, "revision": revision, "draft": draft,
                "generation": generation, "history": record.get("history") or []}

    async def get(self, job_id: str):
        return self._state(self.get_job(job_id))

    async def post(self, job_id: str, body: dict | None = Body(default=None)):
        job = self.own_job(job_id)
        body = body or {}
        source = body.get("source", "video")
        instruction = body.get("instruction", "")
        use_steps = body.get("use_steps", False)
        if not isinstance(use_steps, bool):
            raise HTTPException(422, "use_steps 应为 true 或 false")
        if use_steps and not self._steps(job):
            raise HTTPException(409, "还没有整理好的步骤，先在「步骤」里整理")
        if not isinstance(source, str) or source not in {"video", "conversation"} or not isinstance(instruction, str) or len(instruction) > 2000:
            raise HTTPException(422, "笔记来源或整理要求格式不对（要求最多 2000 字）")
        state = self._state(job)
        if "base_revision" in body and body["base_revision"] != state["revision"]:
            raise HTTPException(409, "当前笔记已发生变化，请刷新后重新生成")
        if job.id in self.running:
            raise HTTPException(409, "笔记正在生成，请等待本次完成")
        if state.get("draft"):
            raise HTTPException(409, "已有待预览修订，请先应用或放弃")
        ids = body.get("message_ids", [])
        if not isinstance(ids, list):
            raise HTTPException(422, "消息编号应为列表")
        turns = selected_turns(self.get_messages(job_id), ids) if source == "conversation" else []
        if source == "video" and ids:
            raise HTTPException(422, "使用所选对话时请选择对话来源")
        frame_times = {s.index: s.time for s in job.slots}
        for turn in turns:
            turn["question"] = {**turn["question"], "frame_times": [frame_times[i] for i in turn["question"].get("frames", []) if i in frame_times]}
        request = {"source": source, "use_steps": use_steps, "instruction": instruction.strip(), "message_ids": [m[role]["id"] for m in turns for role in ("question", "answer")], "turns": turns}
        self.running.add(job.id)
        try:
            self.spawn(self.build(job, request))
        except Exception:
            self.running.discard(job.id)
            raise
        await asyncio.sleep(0)
        return self._state(job)

    async def put_board(self, job_id: str, board: dict = Body(...)):
        job = self.own_job(job_id)
        board = dict(board)
        base_revision = board.pop("base_revision", None)
        state = self._state(job)
        if base_revision is not None and base_revision != state["revision"]:
            raise HTTPException(409, "当前笔记已更新，请重新加载编辑器后再编辑")
        if not isinstance(board.get("blocks"), list) or len(board["blocks"]) > 600:
            raise HTTPException(422, "画布内容格式不对")
        for block in board["blocks"]:
            if not isinstance(block, dict):
                raise HTTPException(422, "画布内容格式不对")
            for key in ("x", "y", "w"):
                if key in block and (type(block[key]) not in {int, float} or not math.isfinite(block[key])):
                    raise HTTPException(422, "画布位置格式不对")
        try:
            raw = json.dumps(board, ensure_ascii=False, allow_nan=False)
        except ValueError:
            raise HTTPException(422, "画布内容包含无效数值")
        if len(raw.encode()) > MAX_BOARD_BYTES:
            raise HTTPException(413, "画布内容太大")
        record = load(job.root) or {}
        if not record.get("note"):
            raise HTTPException(409, "还没有生成好的笔记")
        write(job.root, {**board, "saved": time.time()}, BOARD)
        return {"saved": time.time(), "revision": fingerprint(record["note"], board)}

    def _mutation(self, job, body):
        if job.id in self.running:
            raise HTTPException(409, "笔记正在生成，请等待本次完成")
        state = self._state(job)
        if not isinstance(body, dict) or body.get("base_revision") != state["revision"]:
            raise HTTPException(409, "当前笔记已发生变化，请刷新后重试")
        return state

    async def apply(self, job_id: str, revision_id: str, body: dict = Body(...)):
        job = self.own_job(job_id)
        state = self._mutation(job, body)
        draft = state.get("draft")
        if not draft or draft.get("id") != revision_id:
            raise HTTPException(404, "修订不存在，请重新读取笔记")
        if draft.get("base_revision") != state["revision"]:
            raise HTTPException(409, "生成期间笔记已有手动修改，请保留手改并重新生成修订")
        record = load(job.root) or {}
        history = archive(job.root, record, state["board"])
        record.update(note=draft["note"], status="done", draft=None, history=history, made=time.time(),
                      source=draft["source"], message_ids=draft["message_ids"], generation=None,
                      message="修订已更新到当前笔记", progress={})
        commit_current(job.root, record, draft.get("board"))
        return self._state(job)

    async def discard(self, job_id: str):
        job = self.own_job(job_id)
        if job.id in self.running:
            raise HTTPException(409, "笔记正在生成，请等待本次完成")
        record = load(job.root) or {}
        record["draft"] = None
        write(job.root, record)
        return self._state(job)

    async def restore(self, job_id: str, revision_id: str, body: dict = Body(...)):
        job = self.own_job(job_id)
        state = self._mutation(job, body)
        if state.get("draft"):
            raise HTTPException(409, "请先应用或放弃当前修订，再恢复旧版本")
        record = load(job.root) or {}
        old = history_snapshot(job.root, record, revision_id)
        if not old:
            raise HTTPException(404, "历史版本不存在")
        history = archive(job.root, record, state["board"])
        record.update(note=old["note"], status="done", history=history, draft=None, made=time.time(),
                      source=old.get("source", "video"), message_ids=old.get("message_ids") or [],
                      generation=None, message="已恢复历史笔记（含当时的手动修改）", progress={})
        commit_current(job.root, record, old.get("board"))
        return self._state(job)

    async def export(self, job_id: str, preview: bool = False, image: bool = False, draft: bool = False):
        """The note as a zip (笔记.md + images/); with preview=1 as a page showing what it will read like;
        with image=1 as that page in one long PNG (a phone keeps it in its photos)."""
        job = self.get_job(job_id)
        recover_commit(job.root)
        record = load(job.root) or {}
        if draft:
            selected = record.get("draft") or {}
            note, board = selected.get("note"), selected.get("board")
        else:
            note, board = record.get("note"), load(job.root, BOARD)
        if not note:
            raise HTTPException(409, "还没有生成好的笔记")

        def picture(src: str):
            m = re.search(r"/(extra/\d{8}(?:-hd)?\.jpg|frames/(\d+)\.jpg|replay/[\d-]+/\d{2}\.jpg)$", src)
            if not m:
                return None
            path = job.frame_path(int(m.group(2))) if m.group(2) else job.root / m.group(1)
            root = job.root.resolve()
            return path if path.is_file() and root in path.resolve().parents else None

        if preview or image:
            page = export.to_preview_html(note, board, picture)
            if not image:
                return HTMLResponse(page)
            try:
                png = await export.to_long_image(page)
            except export.ImageError as exc:
                raise HTTPException(503, str(exc))
            title = (note.get("title") or "笔记")[:60]
            return Response(png, media_type="image/png",
                            headers={"Content-Disposition": f"inline; filename=notes.png; filename*=UTF-8''{quote(title)}.png"})
        data, title = export.to_zip(note, board, picture)
        name = re.sub(r'[\\/:*?"<>|]+', " ", title).strip()[:60] or "笔记"
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": f"attachment; filename=notes.zip; filename*=UTF-8''{quote(name)}.zip"})
