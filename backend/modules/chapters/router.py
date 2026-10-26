"""Background chapter generation and HTTP wiring owned by the chapters module."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time

from fastapi import APIRouter

from modules import log
from modules.frames import cuts
from modules.llm import LLMError, Usage

from .task import FILE, _rows, load, prepare_inputs, run_chapters, save, write_record

REFRESH_INTERVAL = 30.0  # coalesce arriving frames; completed producers bypass this delay
MAX_ATTEMPTS = 3  # a temporary model failure gets two retries without polling forever
INPUT_VERSION = 3  # fingerprint the selected evidence and use a text-aware image budget


class ChapterService:
    def __init__(self, get_job, spawn, get_client, cutting, ensure_cuts):
        self.get_job = get_job
        self.spawn = spawn
        self.get_client = get_client
        self.cutting = cutting
        self.ensure_cuts = ensure_cuts
        self.deleted: set[str] = set()
        self.workers: dict[str, asyncio.Task] = {}
        self.running: set[str] = set()
        self.revisions: dict[str, int] = {}
        self.router = APIRouter()
        self.router.add_api_route('/api/link-jobs/{job_id}/chapters', self.get, methods=['GET'])

    def pictures(self, job):
        return [(slot.time, job.frame_path(slot.index)) for slot in job.in_time_order()
                if slot.status == 'ok' and job.frame_path(slot.index).is_file()]

    def pending_sources(self, job):
        pending = [name for name in ('transcript', 'screentext')
                   if getattr(job, name) is not None and getattr(job, name).status in {'pending', 'running'}]
        if job.running or job.filling or any(slot.status == 'pending' for slot in job.slots):
            pending.append('frames')
        if job.id in self.cutting:
            pending.append('cuts')
        return pending

    def inputs(self, job):
        """Fingerprint exactly the prepared model evidence, not every arriving raw frame/text row."""
        transcript = _rows(job.transcript.segments if job.transcript else [])
        screen = _rows(job.screentext.segments if job.screentext else [])
        pictures = self.pictures(job)
        cuts_record = cuts.load(job.root)
        prepared = prepare_inputs(transcript, screen, cuts_record, job.video.duration or 0, pictures)
        key = json.dumps([INPUT_VERSION, prepared.chunks, prepared.picture_keys], ensure_ascii=False)
        return dict(transcript=transcript, screen=screen, pictures=pictures, cuts_record=cuts_record,
                    prepared=prepared, signature=hashlib.sha256(key.encode()).hexdigest(), pending=self.pending_sources(job))

    async def wait_inputs(self, job, timeout: float | None = None):
        """Wait only for the first usable evidence, never for every producer to finish."""
        deadline = time.monotonic() + timeout if timeout is not None else None
        while deadline is None or time.monotonic() < deadline:
            if (self.pictures(job) or
                    any(text.strip() for state in (job.transcript, job.screentext) if state
                        for _, _, text in _rows(state.segments)) or not self.pending_sources(job)):
                return
            await asyncio.sleep(2)
        raise TimeoutError('章节输入尚未准备完成')

    def start(self, job):
        # Reserve before scheduling: multiple requests cannot enqueue duplicate model calls.
        if job.id in self.running or job.id in self.deleted:
            return
        self.running.add(job.id)
        self.spawn(self.build(job))

    def remove(self, job_id):
        self.deleted.add(job_id)
        worker = self.workers.get(job_id)
        if worker is not None:
            worker.cancel()

    def invalidate(self, job):
        self.revisions[job.id] = self.revisions.get(job.id, 0) + 1
        (job.root / FILE).unlink(missing_ok=True)
        self.start(job)

    async def build(self, job):
        timer = log.Timer()
        record = None
        self.workers[job.id] = asyncio.current_task()
        try:
            while job.id not in self.deleted:
                revision = self.revisions.get(job.id, 0)
                if cuts.load(job.root) is None and job.id not in self.cutting:
                    self.spawn(self.ensure_cuts(job))
                    await asyncio.sleep(0)  # let it start and mark the job as cutting
                await self.wait_inputs(job)
                inputs = self.inputs(job)
                previous = load(job.root) or {}
                try:
                    client = self.get_client()
                except LLMError:
                    client = None

                async def complete(messages):
                    parts = []
                    async for delta in client.stream(messages, Usage(), max_tokens=4096):
                        parts.append(delta)
                    return ''.join(parts)

                record = await run_chapters(job.root, inputs['transcript'], inputs['screen'],
                                            inputs['cuts_record'], job.video.duration or 0,
                                            prepared=inputs['prepared'],
                                            complete=complete if client is not None else None, cache=False)
                if job.id in self.deleted:
                    break
                if revision == self.revisions.get(job.id, 0):
                    # A failed refresh must not replace a previously successful chapter with a placeholder.
                    incomplete = set(record.get('incomplete_chapters', []))
                    generated = set(record.get('generated_chapters', []))
                    old_generated = set(previous.get('generated_chapters', []))
                    old_chapters = {(c['start'], c['end']): c
                                    for i, c in enumerate(previous.get('chapters', []))
                                    if i in old_generated}
                    for i in incomplete:
                        chapter = record['chapters'][i]
                        old = old_chapters.get((chapter['start'], chapter['end']))
                        if old is not None:
                            record['chapters'][i] = old
                            generated.add(i)
                    record['generated_chapters'] = sorted(generated)
                    if incomplete and previous.get('summary'):
                        record['summary'] = previous['summary']
                    attempts = (previous.get('_attempts', 0) if previous.get('_inputs') == inputs['signature'] else 0) + 1
                    record.update(_inputs=inputs['signature'], _pending_sources=inputs['pending'],
                                  _generated_at=time.time(), _attempts=attempts, input_version=INPUT_VERSION,
                                  provisional=bool(inputs['pending']) or bool(record.get('needs_retry') and attempts < MAX_ATTEMPTS))
                    if inputs['pending'] and not record.get('needs_retry'):
                        record['message'] = '已根据现有画面和文字生成，后续内容就绪后自动补充'
                    write_record(job.root, record)
                    break
        except Exception as exc:
            log.error('chapters', exc, job_id=job.id)
            if job.id not in self.deleted:
                record = save(job.root, 'failed', message='章节生成失败')
        finally:
            self.running.discard(job.id)
            self.workers.pop(job.id, None)
        if record is None or job.id in self.deleted:
            return
        log.event('chapters', job_id=job.id, status=record['status'],
                  count=len(record['chapters']), chosen_images=record.get('chosen_images', 0),
                  input_version=record.get('input_version', INPUT_VERSION), attempt=record.get('_attempts', 0), ms=timer.ms)

    async def get(self, job_id: str):
        job = self.get_job(job_id)
        if (job.video.extra or {}).get("kind") == "images":
            return {"status": "unavailable", "chapters": [], "message": "图集没有章节", "summary": ""}
        record = load(job.root)
        if record is not None:
            inputs = self.inputs(job)
            stale = record.get('_inputs') != inputs['signature']
            finished_source = set(record.get('_pending_sources', [])) - set(inputs['pending'])
            elapsed = time.time() - record.get('_generated_at', 0)
            retryable = record.get('needs_retry') and record.get('_attempts', 0) < MAX_ATTEMPTS
            if stale and (not inputs['pending'] or finished_source or
                          elapsed >= REFRESH_INTERVAL):
                self.start(job)
            elif retryable and elapsed >= REFRESH_INTERVAL:
                self.start(job)
            updating = job.id in self.running
            provisional = bool(inputs['pending']) or stale or bool(retryable)
            if updating:
                message = '正在补充章节，已有章节仍可使用'
            elif record.get('needs_retry'):
                message = ('部分章节摘要暂未生成，稍后自动重试' if retryable else
                           '部分章节摘要暂未生成，已有章节仍可使用')
            elif provisional:
                message = '已根据现有画面和文字生成，后续内容就绪后自动补充'
            else:
                message = (f"已生成 {len(record['chapters'])} 个章节" if record['status'] == 'done' else record.get('message', ''))
            return {**record, 'provisional': provisional, 'updating': updating, 'message': message}
        self.start(job)
        return {'status': 'running', 'chapters': [], 'message': ''}
