"""Short OCR leases share actual sampling frames between browsers and server workers.

Only the event-loop thread mutates work. A disconnected browser's lease expires, so hybrid work
continues on the server; local mode explicitly fails instead of silently moving OCR to the server.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from modules.frames import sampling
from .ocr import Line

LEASE_SECONDS = 20.0
MAX_LEASE_SECONDS = 60.0
LOCAL_IDLE_TIMEOUT = 120.0
MAX_BODY = 1_000_000
MAX_CLIENTS = 4
now = time.monotonic


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Client(Payload):
    client_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')


class LeaseClient(Client):
    lease_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-f0-9]+$')


class Release(Client):
    lease_id: str | None = Field(default=None, max_length=64, pattern=r'^[a-f0-9]+$')
    reason: str = Field(default='', max_length=80)


Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class OCRLine(Payload):
    text: str = Field(max_length=2000)
    confidence: Unit
    x: Unit
    y: Unit
    w: Unit
    h: Unit


class FrameResult(Payload):
    id: Annotated[StrictInt, Field(ge=0)]
    lines: list[OCRLine] = Field(max_length=200)


class Results(LeaseClient):
    results: list[FrameResult] = Field(min_length=1, max_length=4)


@dataclass
class Lease:
    client: str
    ids: list[int]
    born: float
    expires: float


class WorkSession:
    def __init__(self, job, files: list[Path], fps: float, mode: str):
        self.job, self.files, self.fps, self.mode = job, files, fps, mode
        self.total = len(files)
        self.results: dict[int, list[Line]] = {}
        self.assigned: set[int] = set()
        self.leases: dict[str, Lease] = {}
        self.completed: dict[str, str] = {}
        self.clients: dict[str, int] = {}
        self.local = self.server = 0
        self.last_result = now()
        self.changed = asyncio.Event()
        self.closed = False
        self.client_error = getattr(job, '_ocr_client_error', '')
        job._ocr_client_error = ''
        self.update()

    @property
    def complete(self):
        return len(self.results) >= self.total

    def progress(self):
        return {'mode': self.mode, 'done': len(self.results), 'total': self.total,
                'local': self.local, 'server': self.server}

    def update(self):
        state = self.job.screentext
        state.processing = self.progress()
        place = '本机' if self.mode == 'local' else '本机与服务器'
        state.message = f'{place}识别画面文字 {len(self.results)}/{self.total}'
        self.changed.set()
        self.job.emit({'type': 'screentext', **state.summary()})

    def reap(self):
        expired = [key for key, lease in self.leases.items() if lease.expires <= now()]
        for key in expired:
            lease = self.leases.pop(key)
            self.assigned.difference_update(lease.ids)
        if expired:
            self.changed.set()

    def _lease(self, client: str, key: str):
        self.reap()
        lease = self.leases.get(key)
        if self.closed or lease is None or lease.client != client:
            raise HTTPException(409, '本机识别任务已过期，请重新领取')
        return lease

    def _available(self, limit: int):
        return [i for i in range(self.total) if i not in self.results and i not in self.assigned][:limit]

    def claim(self, client: str):
        self.reap()
        if self.closed or self.complete:
            return {'state': 'done', 'mode': self.mode, 'frames': [], 'progress': self.progress()}
        key = next((key for key, lease in self.leases.items() if lease.client == client), None)
        if key is None:
            if len(self.leases) >= MAX_CLIENTS:
                return {'state': 'waiting', 'mode': self.mode, 'frames': [], 'progress': self.progress()}
            ids = self._available(1 if not self.clients.get(client) else 2)
            if not ids:
                return {'state': 'waiting', 'mode': self.mode, 'frames': [], 'progress': self.progress()}
            if client not in self.clients and len(self.clients) >= 32:
                active = {lease.client for lease in self.leases.values()}
                oldest = next((key for key in self.clients if key not in active), None)
                if oldest is not None:
                    self.clients.pop(oldest)
            self.clients[client] = self.clients.pop(client, 0)
            key = uuid.uuid4().hex
            self.leases[key] = Lease(client, ids, now(), now() + LEASE_SECONDS)
            self.assigned.update(ids)
        lease = self.leases[key]
        return {'state': 'ready', 'mode': self.mode, 'lease_id': key,
                'lease_seconds': max(0, round(lease.expires - now(), 1)),
                'frames': [{'id': i, 'time': (int(self.files[i].stem) - 1) / self.fps,
                            'url': f'/api/link-jobs/{self.job.id}/ocr/frames/{key}/{i}.jpg'} for i in lease.ids],
                'progress': self.progress()}

    def heartbeat(self, client: str, key: str):
        lease = self._lease(client, key)
        lease.expires = min(lease.born + MAX_LEASE_SECONDS, now() + LEASE_SECONDS)
        return {'state': 'ready', 'mode': self.mode, 'lease_seconds': max(0, round(lease.expires - now(), 1)),
                'progress': self.progress()}

    def submit(self, client: str, key: str, results):
        if self.completed.get(key) == client:
            return 0
        lease = self._lease(client, key)
        try:
            rows = [r if isinstance(r, FrameResult) else FrameResult.model_validate(r) for r in results]
        except ValidationError:
            raise HTTPException(422, '本机识别结果格式不正确') from None
        if len(rows) != len(lease.ids) or {r.id for r in rows} != set(lease.ids):
            raise HTTPException(409, '结果与领取的画面不一致')
        for row in rows:
            self.results[row.id] = [Line(**line.model_dump()) for line in row.lines]
        self.local += len(rows)
        self.clients[client] += len(rows)
        self.last_result = now()
        self.assigned.difference_update(lease.ids)
        self.leases.pop(key)
        self.completed[key] = client
        if len(self.completed) > 128:
            self.completed.pop(next(iter(self.completed)))
        self.update()
        return len(rows)

    def release(self, client: str, key: str | None, reason: str = ''):
        if key is not None:
            lease = self.leases.get(key)
            if lease is not None and lease.client == client:
                self.leases.pop(key)
                self.assigned.difference_update(lease.ids)
        else:
            for lease_key in [k for k, lease in self.leases.items() if lease.client == client]:
                self.release(client, lease_key)
        if self.mode == 'local' and reason in {'unsupported', 'model_error', 'too_slow'}:
            self.client_error = client_error(reason)
        self.changed.set()

    def take_server(self, limit=4):
        self.reap()
        if self.mode == 'local' or self.closed:
            return []
        ids = self._available(limit)
        self.assigned.update(ids)
        return ids

    def accept_server(self, ids, lines):
        if len(lines) != len(ids):
            raise ValueError("服务器文字识别结果不完整，请重试")
        for i, found in zip(ids, lines):
            self.results[i] = found
        self.server += len(ids)
        self.assigned.difference_update(ids)
        self.last_result = now()
        self.update()

    def readings(self):
        return [((int(self.files[i].stem) - 1) / self.fps, self.results[i]) for i in sorted(self.results)]

    def close(self):
        self.closed = True
        self.leases.clear()
        self.assigned.clear()
        self.changed.set()


def client_error(reason):
    return {'unsupported': '此浏览器暂不支持本机文字识别，请重试，或返回首页选择混合或服务器处理后重新导入',
            'too_slow': '本机文字识别较慢，请重试，或返回首页选择混合或服务器处理后重新导入'}.get(
                reason, '本机文字识别模型未能加载，请重试，或返回首页选择服务器处理后重新导入')


@asynccontextmanager
async def free_slot():
    yield


async def run_distributed(job, files, fps, mode, recognize_batch, publish, server_gate=None):
    work = WorkSession(job, files, fps, mode)
    job._ocr_work = work
    gate = server_gate or free_slot

    async def server_worker():
        while not work.complete and not work.closed:
            work.reap()
            if not work._available(1):
                await asyncio.sleep(.1)
                continue
            async with gate():
                if work.complete or work.closed:
                    return
                ids = work.take_server()
                if not ids:
                    continue
                running = asyncio.create_task(asyncio.to_thread(recognize_batch, [files[i] for i in ids]))
                try:
                    lines = await asyncio.shield(running)
                except asyncio.CancelledError:
                    # A Python OCR call cannot be interrupted; keep its input files until it stops.
                    with suppress(Exception):
                        await running
                    raise
                work.accept_server(ids, lines)
            await asyncio.sleep(0)

    server = asyncio.create_task(server_worker()) if mode == 'hybrid' and recognize_batch is not None else None
    published, publish_at = 0, 1
    try:
        while not work.complete:
            work.reap()
            if server is not None and server.done():
                server.result()
            count = len(work.results)
            if count >= publish_at:
                await publish(work.readings())
                published, publish_at = count, max(publish_at * 2, count + 1)
            if work.client_error and mode == 'local':
                if count > published:
                    await publish(work.readings())
                raise ValueError(work.client_error)
            if now() - work.last_result >= LOCAL_IDLE_TIMEOUT:
                if count > published:
                    await publish(work.readings())
                raise ValueError('本机文字识别已暂停，请保持页面打开后重试，或返回首页选择服务器处理后重新导入')
            work.changed.clear()
            try:
                await asyncio.wait_for(work.changed.wait(), .25)
            except asyncio.TimeoutError:
                pass
        if len(work.results) != published:
            await publish(work.readings())
        return work.readings()
    finally:
        work.close()
        if server is not None:
            server.cancel()
            with suppress(asyncio.CancelledError):
                await server
        job._ocr_work = None


class ClientOCRService:
    def __init__(self, own_job):
        self.own_job = own_job
        self.router = APIRouter()
        prefix = '/api/link-jobs/{job_id}/ocr'
        self.router.add_api_route(prefix + '/claim', self.claim_route, methods=['POST'])
        self.router.add_api_route(prefix + '/result', self.result_route, methods=['POST'])
        self.router.add_api_route(prefix + '/heartbeat', self.heartbeat_route, methods=['POST'])
        self.router.add_api_route(prefix + '/release', self.release_route, methods=['POST'])
        self.router.add_api_route(prefix + '/frames/{lease_id}/{frame_id}.jpg', self.frame, methods=['GET'])

    def state(self, job):
        mode = sampling.saved(job.video).get('ocr_mode', 'server')
        return {'state': 'done' if job.screentext.status in {'done', 'empty', 'unavailable'} else
                         'unavailable' if mode == 'server' or job.screentext.status == 'failed' else 'waiting',
                'mode': mode, 'frames': [], 'progress': getattr(job.screentext, 'processing', None)}

    async def payload(self, request, model):
        length = request.headers.get('content-length', '')
        if length.isdigit() and int(length) > MAX_BODY:
            raise HTTPException(413, '本机识别结果过大')
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BODY:
                raise HTTPException(413, '本机识别结果过大')
        try:
            return model.model_validate_json(data)
        except (ValidationError, ValueError):
            raise HTTPException(422, '本机识别请求格式不正确') from None

    async def claim_route(self, job_id: str, request: Request):
        job = self.own_job(job_id)
        body = await self.payload(request, Client)
        work = getattr(job, '_ocr_work', None)
        return work.claim(body.client_id) if work is not None else self.state(job)

    async def result_route(self, job_id: str, request: Request):
        job = self.own_job(job_id)
        body = await self.payload(request, Results)
        work = getattr(job, '_ocr_work', None)
        if work is None:
            if job.screentext.status in {'done', 'empty'}:
                return {**self.state(job), 'accepted': 0}
            raise HTTPException(409, '本机识别任务已结束，请重新领取')
        accepted = work.submit(body.client_id, body.lease_id, body.results)
        return {'accepted': accepted, 'state': 'done' if work.complete else 'waiting',
                'mode': work.mode, 'progress': work.progress()}

    async def heartbeat_route(self, job_id: str, request: Request):
        job = self.own_job(job_id)
        body = await self.payload(request, LeaseClient)
        work = getattr(job, '_ocr_work', None)
        if work is None:
            raise HTTPException(409, '本机识别任务已结束')
        return work.heartbeat(body.client_id, body.lease_id)

    def release(self, job_id, data):
        job = self.own_job(job_id)
        body = Release.model_validate(data)
        work = getattr(job, '_ocr_work', None)
        if work is not None:
            work.release(body.client_id, body.lease_id, body.reason)
        elif sampling.saved(job.video).get('ocr_mode') == 'local' and body.reason in {'unsupported', 'model_error', 'too_slow'}:
            job._ocr_client_error = client_error(body.reason)
        return {'released': True, **self.state(job)}

    async def release_route(self, job_id: str, request: Request):
        self.own_job(job_id)
        body = await self.payload(request, Release)
        return self.release(job_id, body.model_dump())

    async def frame(self, job_id: str, lease_id: str, frame_id: int):
        job = self.own_job(job_id)
        work = getattr(job, '_ocr_work', None)
        if work is not None:
            work.reap()
            lease = work.leases.get(lease_id)
            if lease is not None and frame_id in lease.ids:
                path = work.files[frame_id]
                if path.is_file():
                    return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})
        raise HTTPException(404, '本机识别画面已过期，请重新领取')
