"""GongJ!ng? backend. Run: `uv run uvicorn app:app --port 8000` (the Vite dev server proxies /api)."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from modules.agent import run_agent
from modules.frames import FrameJob
from modules.decide import Decider
from modules.decide import enabled as decision_enabled
from modules.llm import ChatClient, LLMConfig, LLMError, OllamaClient, create_client
from modules.store import SessionStore
from modules.transcript import Transcript, run_transcript
from modules.video_source import ResolveError, default_registry
from modules.video_source.local import PLATFORM as LOCAL, resolve_file

# GONGJING_DATA_DIR lets a second server (e.g. for testing) keep its own frames and sessions:
# on startup a server deletes frame folders that its own database does not know.
DATA_ROOT = Path(os.environ.get("GONGJING_DATA_DIR") or Path(__file__).parent / "data")
DATA_DIR = DATA_ROOT / "jobs"
DB_PATH = DATA_ROOT / "sessions.sqlite3"
JOB_TTL = 6 * 3600  # seconds an idle job stays in memory; its session and frames stay on disk
MAX_UPLOAD = 4 << 30  # bytes
SOURCE = "source"  # an uploaded file is kept as <job dir>/source.<ext> only while it is being processed

registry = default_registry()
store = SessionStore(DB_PATH)
jobs: dict[str, FrameJob] = {}  # active jobs; saved sessions are restored on demand
tasks: set[asyncio.Task] = set()
llm: ChatClient | OllamaClient | None = None
decider: Decider | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    prune(force=True)
    yield
    for task in tasks:
        task.cancel()
    await registry.aclose()
    if llm is not None:
        await llm.aclose()
    if decider is not None:
        await decider.aclose()
    store.close()


app = FastAPI(title="GongJ!ng? backend", lifespan=lifespan)


class LinkRequest(BaseModel):
    url: str
    part: int | None = None
    task: str = ""  # question typed on the import screen, kept with the session


class AgentRequest(BaseModel):
    video_id: str  # a link job id
    question: str
    scope: dict = {"type": "all"}  # {"type": "all"} or {"type": "frames", "frames": [index, ...]}


@app.exception_handler(ResolveError)
async def on_resolve_error(_, exc: ResolveError):
    return JSONResponse(status_code=422, content=exc.as_dict())


def prune(force: bool = False) -> None:
    """Unload idle jobs from memory; on startup also delete frame folders no session owns."""
    now = time.time()
    for job_id in [j for j, job in jobs.items() if now - job.created > JOB_TTL and not job.running]:
        jobs.pop(job_id)
    if force and DATA_DIR.exists():
        saved = store.ids()
        for path in DATA_DIR.iterdir():
            if path.name not in saved:
                shutil.rmtree(path, ignore_errors=True)
            else:
                for source in path.glob(f"{SOURCE}.*"):  # an upload whose processing a restart cut off
                    source.unlink(missing_ok=True)


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def sample(job: FrameJob, indexes: list[int] | None = None) -> None:
    """Run sampling and save the frame states to the session, also when cut off."""
    try:
        await job.run(indexes)
    finally:
        store.save_slots(job)


async def transcribe(job: FrameJob) -> None:
    try:
        await run_transcript(job)
    finally:
        store.save_transcript(job)


def busy(job: FrameJob) -> bool:
    """Frames or transcript still in progress."""
    return job.running or job.transcript.running


def snapshot(job: FrameJob) -> dict:
    return {**job.snapshot(), "transcript": job.transcript.summary()}


def find_job(job_id: str) -> FrameJob | None:
    job = jobs.get(job_id)
    if job is None:
        record = store.get(job_id)
        if record is None:
            return None
        platform = json.loads(record["video"])["platform"]
        resolver = next((r for r in registry.resolvers if r.platform == platform), None)
        job = store.restore(job_id, resolver, DATA_DIR / job_id)
        jobs[job_id] = job
    return job


def get_job(job_id: str) -> FrameJob:
    job = find_job(job_id)
    if job is None:
        raise HTTPException(404, "任务不存在或已删除")
    return job


def get_llm() -> ChatClient | OllamaClient:
    """Created on first use so a missing key only affects questions, not link parsing."""
    global llm
    if llm is None:
        llm = create_client(LLMConfig.from_env())
    return llm


def get_decider() -> Decider | None:
    """The local decision model (DECISION=off disables it); every decision is logged for calibration."""
    global decider
    if not decision_enabled():
        return None
    if decider is None:
        decider = Decider(log=store.log_decision)
    return decider


def warm_decider() -> None:
    """A question usually follows a new job: have the decision model loaded by then."""
    d = get_decider()
    if d is not None:
        spawn(d.warm())


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/api/health")
async def health():
    try:
        model = get_llm().config.model
    except LLMError:
        model = None
    return {"ok": True, "platforms": [r.platform for r in registry.resolvers], "ffmpeg": bool(shutil.which("ffmpeg")),
            "model": model}


@app.post("/api/links/resolve")
async def resolve_link(body: LinkRequest):
    """Identity and metadata only, e.g. to show title and parts before sampling."""
    _, video = await registry.resolve(body.url, body.part)
    return video.public()


@app.post("/api/link-jobs")
async def create_link_job(body: LinkRequest):
    """Resolve the link and start sampling frames in the background."""
    prune()
    resolver, video = await registry.resolve(body.url, body.part)
    job_id = uuid.uuid4().hex[:12]
    job = FrameJob(job_id, video, resolver, DATA_DIR / job_id)
    job.transcript = Transcript()
    jobs[job_id] = job
    store.create(job, body.url, body.task)
    spawn(sample(job))
    spawn(transcribe(job))
    warm_decider()
    return snapshot(job)


@app.post("/api/videos")
async def upload_video(file: UploadFile = File(...), task: str = Form("")):
    """Upload a local video: it then runs exactly like a link job (frames + transcript, then deleted)."""
    prune()
    name = Path(file.filename or "").name or "上传的视频"
    job_id = uuid.uuid4().hex[:12]
    root = DATA_DIR / job_id
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{SOURCE}{Path(name).suffix.lower()[:8] or '.mp4'}"
    try:
        size = 0
        with path.open("wb") as out:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, f"文件超过 {MAX_UPLOAD >> 30} GB 上限")
                out.write(chunk)
        video = await resolve_file(path, name)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    resolver = next(r for r in registry.resolvers if r.platform == LOCAL)
    job = FrameJob(job_id, video, resolver, root)
    job.transcript = Transcript()
    jobs[job_id] = job
    store.create(job, f"上传：{name}", task)

    async def process() -> None:
        try:
            await asyncio.gather(sample(job), transcribe(job))
        finally:
            path.unlink(missing_ok=True)

    spawn(process())
    warm_decider()
    return snapshot(job)


@app.get("/api/link-jobs/{job_id}")
async def job_snapshot(job_id: str):
    return snapshot(get_job(job_id))


@app.get("/api/link-jobs/{job_id}/events")
async def job_events(job_id: str, since: int = 0):
    """SSE stream of job events from `since`; ends once frames and transcript are both finished."""
    job = get_job(job_id)

    async def stream():
        cursor = since
        # Close only once everything has been sent and nothing is running: a late subscriber
        # replaying a finished job gets every event first.
        while busy(job) or cursor < len(job.events):
            events = await job.wait_events(cursor)
            for event in events:
                cursor = event["seq"] + 1
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if not events:
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/link-jobs/{job_id}/frames/{index}.jpg")
async def job_frame(job_id: str, index: int):
    job = get_job(job_id)
    path = job.frame_path(index)
    if not (0 <= index < len(job.slots)) or job.slots[index].status != "ok" or not path.is_file():
        raise HTTPException(404, "该帧尚未获取")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.post("/api/link-jobs/{job_id}/retry")
async def retry_missing(job_id: str):
    """Sample the missing frames again (trial-limited ones excluded); a failed transcript is redone too."""
    job = get_job(job_id)
    if busy(job):
        raise HTTPException(409, "仍在抓取中，请稍后再试")
    if job.video.platform == LOCAL:
        raise HTTPException(409, "本地上传的视频处理完已删除，不能补抓，请重新上传")
    redo_transcript = job.transcript.status == "failed"
    if job.restored and (redo_transcript or any(s.status == "missing" and s.reason != "trial" for s in job.slots)):
        # Rebuilt after a restart without stream addresses: resolve the link again first.
        _, job.video = await registry.resolve(job.video.canonical_url, job.video.part)
        job.restored = False
    since = len(job.events)
    indexes = await job.retry_missing()
    # Claimed before the tasks start, so an event stream opened right away stays open for them.
    if redo_transcript:
        job.transcript.status = "running"
    if indexes:
        job.running = True
        spawn(sample(job, indexes))
    if redo_transcript:
        spawn(transcribe(job))
    return {"retrying": len(indexes), "transcript": redo_transcript, "since": since}


@app.get("/api/link-jobs/{job_id}/transcript")
async def job_transcript(job_id: str):
    """Transcript status and timed segments."""
    return get_job(job_id).transcript.as_dict()


@app.post("/api/agent/runs")
async def agent_run(body: AgentRequest):
    """SSE stream of one answer: progress / tool_call.* / assistant.message.delta / run.completed | run.error."""
    run_id = uuid.uuid4().hex[:12]

    async def stream():
        job = find_job(body.video_id)
        if job is None:
            yield sse({"type": "run.error", "run_id": run_id, "code": "job_not_found", "message": "这个会话已被删除，请重新解析链接"})
            return
        try:
            client = get_llm()
        except LLMError as err:
            yield sse({"type": "run.error", "run_id": run_id, **err.as_dict()})
            return
        frames = body.scope.get("frames") if body.scope.get("type") == "frames" else None
        history = store.history(job.id)
        store.add_message(job.id, "user", body.question, data={"frames": frames or []})
        # The answer is saved as its text plus the non-delta events, which the UI replays to
        # rebuild the trace. A disconnect (the user pressed stop) saves what arrived so far.
        text, events, status = [], [], "stopped"
        try:
            async for event in run_agent(job, client, body.question, frames=frames, history=history, decider=get_decider()):
                if event["type"] == "assistant.message.delta":
                    text.append(event["delta"])
                else:
                    events.append(event)
                    if event["type"] in ("run.completed", "run.error"):
                        status = "done" if event["type"] == "run.completed" else "error"
                yield sse({"run_id": run_id, **event})
        finally:
            if status == "stopped":
                events.append({"type": "run.error", "code": "stopped", "message": "已停止"})
            store.add_message(job.id, "assistant", "".join(text), status=status, data={"events": events})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/sessions")
async def list_sessions(limit: int = 50):
    """Saved sessions, most recently used first."""
    return {"sessions": store.list(limit)}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Everything needed to reopen a session: the job snapshot plus its conversation."""
    job = get_job(session_id)
    return {**snapshot(job), "task": store.get(session_id)["task"], "messages": store.messages(session_id)}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    job = find_job(session_id)
    if job is None:
        raise HTTPException(404, "会话不存在")
    if busy(job):
        raise HTTPException(409, "仍在抓取中，请稍后再删除")
    jobs.pop(session_id, None)
    store.delete(session_id)
    shutil.rmtree(DATA_DIR / session_id, ignore_errors=True)
    return {"ok": True}
