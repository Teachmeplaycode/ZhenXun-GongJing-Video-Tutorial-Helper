"""Background chapter generation and HTTP wiring owned by the chapters module."""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter

from modules import log
from modules.frames import cuts
from modules.llm import LLMError, Usage

from .task import load, run_chapters, save


class ChapterService:
    def __init__(self, get_job, spawn, get_client, cutting):
        self.get_job = get_job
        self.spawn = spawn
        self.get_client = get_client
        self.cutting = cutting
        self.running: set[str] = set()
        self.router = APIRouter()
        self.router.add_api_route('/api/link-jobs/{job_id}/chapters', self.get, methods=['GET'])

    async def wait_inputs(self, job, timeout: float = 600.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            t, s = job.transcript, job.screentext
            if ((t is None or t.status not in {'pending', 'running'})
                    and (s is None or s.status not in {'pending', 'running'})
                    and job.id not in self.cutting):
                return
            await asyncio.sleep(2)
        raise TimeoutError('章节输入尚未准备完成')

    def start(self, job):
        # Reserve before scheduling: multiple requests cannot enqueue duplicate model calls.
        if job.id in self.running:
            return
        self.running.add(job.id)
        self.spawn(self.build(job))

    async def build(self, job):
        timer = log.Timer()
        try:
            await self.wait_inputs(job)
            try:
                client = self.get_client()
            except LLMError:
                client = None

            async def complete(messages):
                parts = []
                async for delta in client.stream(messages, Usage(), max_tokens=2048):
                    parts.append(delta)
                return ''.join(parts)

            record = await run_chapters(job.root,
                                        job.transcript.segments if job.transcript else [],
                                        job.screentext.segments if job.screentext else [],
                                        cuts.load(job.root), job.video.duration or 0,
                                        complete=complete if client is not None else None)
        except Exception as exc:
            log.error('chapters', exc, job_id=job.id)
            record = save(job.root, 'failed', message='章节生成失败')
        finally:
            self.running.discard(job.id)
        log.event('chapters', job_id=job.id, status=record['status'],
                  count=len(record['chapters']), ms=timer.ms)

    async def get(self, job_id: str):
        job = self.get_job(job_id)
        record = load(job.root)
        if record is not None:
            return record
        self.start(job)
        return {'status': 'running', 'chapters': [], 'message': ''}
