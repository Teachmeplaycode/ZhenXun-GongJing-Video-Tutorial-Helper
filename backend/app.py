"""GongJ!ng? backend. Run: `uv run uvicorn app:app --port 8000` (the Vite dev server proxies /api)."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from modules import accounts, log, playback
from modules.chapters.router import ChapterService
from modules.notes.router import NotesService
from modules.agent import browser, run_agent
from modules.agent.tools import AgentTools, TRACE_NAMES
from modules.export.api import create_router as create_export_router
from modules.frames import FrameJob, cuts
from modules.frames import images, sampling
from modules.frames.job import MAX_FRAMES, shot_fill
from modules.decide import Decider
from modules.decide import enabled as decision_enabled
from modules.llm import ChatClient, LLMConfig, LLMError, OllamaClient, create_client
from modules.store import SessionStore
from modules.screentext import ScreenText, run_screentext
from modules.factcheck.api import create_router as create_factcheck_router
from modules.transcript import Transcript, run_transcript
from modules.antifraud.router import create_router as antifraud_router
from modules.video_source import ResolveError, ResolvedVideo, Stream, default_registry
from modules.video_source.local import PLATFORM as LOCAL, resolve_file

# GONGJING_DATA_DIR lets a second server (e.g. for testing) keep its own frames and sessions:
# on startup a server deletes frame folders that its own database does not know.
DATA_ROOT = Path(os.environ.get("GONGJING_DATA_DIR") or Path(__file__).parent / "data")
DATA_DIR = DATA_ROOT / "jobs"
DB_PATH = DATA_ROOT / "sessions.sqlite3"
JOB_TTL = 6 * 3600  # seconds an idle job stays in memory; its session and frames stay on disk
MAX_UPLOAD = 4 << 30  # bytes
SOURCE = "source"  # an uploaded file is kept as <job dir>/source.<ext>
# Uploads are kept after processing, so a cited moment can be played in the original and replay and
# close looks can read it again (modules/playback). KEEP_UPLOADS=off deletes them once read (e.g. a
# shared server); the user can also delete one session's original from the page.
KEEP_UPLOADS = os.environ.get("KEEP_UPLOADS", "on").lower() not in ("0", "off", "false", "no")

registry = default_registry()
store = SessionStore(DB_PATH)
jobs: dict[str, FrameJob] = {}  # active jobs; saved sessions are restored on demand
tasks: set[asyncio.Task] = set()
llm: ChatClient | OllamaClient | None = None
decider: Decider | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.setup(DATA_ROOT / "logs")
    prune(force=True)
    yield
    for task in tasks:
        task.cancel()
    await registry.aclose()
    if llm is not None:
        await llm.aclose()
    if decider is not None:
        await decider.aclose()
    await accounts.shutdown()
    await browser.shutdown()
    store.close()


app = FastAPI(title="GongJ!ng? backend", lifespan=lifespan)


class LinkRequest(BaseModel):
    url: str
    part: int | None = None
    task: str = ""  # question typed on the import screen, kept with the session
    sampling: dict | None = None  # preset and overrides chosen on the import screen (modules/frames/sampling)


class AgentRequest(BaseModel):
    video_id: str  # a link job id
    question: str
    scope: dict = {"type": "all"}  # {"type": "all"} or {"type": "frames", "frames": [index, ...]}
    web: bool = True     # composer switch: may the model search the web for this question
    papers: bool = True  # composer switch: may it search papers
    history: bool = True  # send earlier turns along; the eval runner turns it off so questions don't influence each other


@app.exception_handler(ResolveError)
async def on_resolve_error(request: Request, exc: ResolveError):
    log.event("request.failed", path=request.url.path, code=exc.code, message=exc.message)
    return JSONResponse(status_code=422, content=exc.as_dict())


@app.exception_handler(Exception)
async def on_unexpected(request: Request, exc: Exception):
    log.error(request.url.path, exc)
    return JSONResponse(status_code=500, content={"code": "internal", "message": "后端出错了，详情见日志"})


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
                    if not KEEP_UPLOADS:
                        source.unlink(missing_ok=True)


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def sample(job: FrameJob, indexes: list[int] | None = None) -> None:
    """Run sampling and save the frame states to the session, also when cut off."""
    timer = log.Timer()
    try:
        await job.run(indexes)
    except Exception as exc:
        log.error("link.frames", exc, job_id=job.id)
        raise
    finally:
        store.save_slots(job)
        c = job.coverage()
        log.event("link.frames", job_id=job.id, ok=c["ok"], missing=c["missing"], total=c["total"], ms=timer.ms,
                  retry=indexes is not None)


CUTS_WAIT = 600.0  # seconds the shot fill waits for shot changes after the uniform pass


async def sample_with_shots(job: FrameJob, cap: int = MAX_FRAMES) -> None:
    """The uniform pass first (chat can start after it), then a keyframe for every shot it missed,
    once the shot changes are known (modules/frames/cuts.py), up to `cap` frames in all."""
    job.filling = True
    try:
        await sample(job)
        deadline = time.monotonic() + CUTS_WAIT
        while job.id in cutting and time.monotonic() < deadline:
            await asyncio.sleep(1)
        record = cuts.load(job.root) or {}
        if record.get("status") != "done":
            return
        times = shot_fill(record["cuts"], job.video.duration or 0, [s.time for s in job.slots], cap)
        log.event("link.shots", job_id=job.id, cuts=len(record["cuts"]), added=len(times))
        if times:
            await sample(job, job.add_slots(times))
    finally:
        job.filling = False
        job.emit({"type": "status", "message": ""})  # wakes the event stream so it can close


async def transcribe(job: FrameJob) -> None:
    timer = log.Timer()
    try:
        await run_transcript(job)
    except Exception as exc:
        log.error("transcript", exc, job_id=job.id)
        raise
    finally:
        store.save_transcript(job)
        t = job.transcript
        log.event("transcript", job_id=job.id, status=t.status if t else None, segments=len(t.segments) if t else 0,
                  message=(t.message if t and t.status != "done" else ""), ms=timer.ms)


async def read_screen(job: FrameJob) -> None:
    timer = log.Timer()
    try:
        await run_screentext(job)
    except Exception as exc:
        log.error("screentext", exc, job_id=job.id)
        raise
    finally:
        store.save_screentext(job)
        t = job.screentext
        log.event("screentext", job_id=job.id, status=t.status, segments=len(t.segments), skipped=t.skipped,
                  message=(t.message if t.status != "done" else ""), ms=timer.ms)


cutting: set[str] = set()  # job ids whose shot changes are being detected


async def find_cuts(job: FrameJob) -> None:
    """Detect the shot changes for the timeline's marks (modules/frames/cuts.py), cached in the job folder."""
    timer = log.Timer()
    cutting.add(job.id)

    async def refresh():
        job.video = await job.resolver.refresh(job.video)
        return job.video.streams

    try:
        if not job.video.streams and job.video.platform != LOCAL:  # restored after a restart: no addresses yet
            _, job.video = await registry.resolve(job.video.canonical_url, job.video.part)
            job.restored = False
        record = await cuts.run(job.root, job.video.streams, job.video.duration or 0, refresh=refresh)
    except Exception as exc:
        log.error("cuts", exc, job_id=job.id)
        record = cuts.save(job.root, "failed", message="镜头切换检测失败")
    finally:
        cutting.discard(job.id)
    log.event("cuts", job_id=job.id, status=record["status"], count=len(record["cuts"]), ms=timer.ms)


def start_sampling(job: FrameJob, spec: dict | None) -> tuple:
    """The import's sampling plan, saved with the video; returns the frame-sampling coroutine to run."""
    p = sampling.plan(spec, job.video.duration or 0)
    job.video.extra["sampling"] = p.as_dict()
    return sample_with_shots(job, p.cap) if p.shots else sample(job)


def busy(job: FrameJob) -> bool:
    """Frames, transcript or on-screen text still in progress."""
    return job.running or job.filling or job.transcript.running or job.screentext.running


def snapshot(job: FrameJob) -> dict:
    return {**job.snapshot(), "transcript": job.transcript.summary(), "screentext": job.screentext.summary()}


def find_job(job_id: str) -> FrameJob | None:
    job = jobs.get(job_id)
    if job is None:
        record = store.get(job_id)
        if record is None:
            return None
        platform = json.loads(record["video"])["platform"]
        resolver = next((r for r in registry.resolvers if r.serves(platform)), None)
        job = store.restore(job_id, resolver, DATA_DIR / job_id)
        kept = next((DATA_DIR / job_id).glob(f"{SOURCE}.*"), None)
        if job.video.platform == LOCAL and kept is not None:  # a kept upload can be read and played again
            job.video.streams = [Stream(str(kept), {}, "local-file")]
            job.video.audio_streams = [Stream(str(kept), {}, "local-file")]
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


chapter_service = ChapterService(lambda job_id: get_job(job_id), spawn, lambda: get_llm(), cutting, lambda job: find_cuts(job))
app.include_router(chapter_service.router)
notes_service = NotesService(lambda job_id: get_job(job_id), spawn, lambda: get_llm(),
                             chapters_busy=lambda job_id: job_id in chapter_service.running)
app.include_router(notes_service.router)


@app.post("/api/link-jobs")
async def create_link_job(body: LinkRequest):
    """Resolve the link and start sampling frames in the background."""
    prune()
    timer = log.Timer()
    try:
        resolver, video = await registry.resolve(body.url, body.part)
    except ResolveError as exc:
        log.event("link.resolve", ok=False, url=body.url[:200], code=exc.code, message=exc.message, ms=timer.ms)
        raise
    job_id = uuid.uuid4().hex[:12]
    log.event("link.resolve", ok=True, job_id=job_id, platform=video.platform, video_id=video.video_id,
              duration=video.duration, ms=timer.ms)
    if images.is_images(video):  # an image post: pictures, their text; no sampling, speech or shots
        job = FrameJob(job_id, video, resolver, DATA_DIR / job_id, count=len(video.extra["images"]))
        job.transcript, job.screentext = Transcript(), ScreenText()
        jobs[job_id] = job
        store.create(job, body.url, body.task)
        spawn(process_images(job))
        return snapshot(job)
    job = FrameJob(job_id, video, resolver, DATA_DIR / job_id, count=sampling.plan(body.sampling, video.duration or 0).frames)
    job.transcript = Transcript()
    job.screentext = ScreenText()
    frames_run = start_sampling(job, body.sampling)
    jobs[job_id] = job
    store.create(job, body.url, body.task)
    spawn(frames_run)
    spawn(transcribe(job))
    spawn(read_screen(job))
    spawn(find_cuts(job))
    chapter_service.start(job)
    warm_decider()
    return snapshot(job)


async def process_images(job: FrameJob) -> None:
    """An image post's import (modules/frames/images.py), saved like a video's."""
    timer = log.Timer()
    try:
        await images.process(job)
    except Exception as exc:
        log.error("images", exc, job_id=job.id)
        raise
    finally:
        store.save_slots(job)
        store.save_transcript(job)
        store.save_screentext(job)
        c = job.coverage()
        log.event("images", job_id=job.id, ok=c["ok"], missing=c["missing"], text=len(job.screentext.segments), ms=timer.ms)


@app.get("/api/link-jobs/{job_id}/texts")
async def picture_texts(job_id: str):
    """A picture set's text, picture by picture, for the picture page."""
    job = get_job(job_id)
    if not images.is_images(job.video):
        raise HTTPException(404, "只有图集有逐张的文字")
    return {"status": job.screentext.status if job.screentext else "none", "items": images.texts_by_picture(job)}


MAX_IMAGE_BYTES = 25 << 20
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


@app.post("/api/images")
async def upload_images(files: list[UploadFile] = File(...), task: str = Form("")):
    """Upload pictures (screenshots, a saved image post): they become an image job, kept on disk."""
    prune()
    if not files or len(files) > images.MAX_IMAGES:
        raise HTTPException(422, f"一次上传 1 到 {images.MAX_IMAGES} 张图片")
    job_id = uuid.uuid4().hex[:12]
    root = DATA_DIR / job_id
    folder = root / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    try:
        for i, f in enumerate(files):
            name = Path(f.filename or "").name
            suffix = Path(name).suffix.lower()
            if suffix not in IMAGE_SUFFIXES and not (f.content_type or "").startswith("image/"):
                raise HTTPException(422, f"不是图片：{name}")
            data = await f.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(413, f"图片超过 {MAX_IMAGE_BYTES >> 20} MB：{name}")
            path = folder / f"{i:03d}{suffix or '.img'}"
            path.write_bytes(data)
            saved.append({"path": str(path), "name": name})
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    first = saved[0]["name"] or "上传的图片"
    title = first if len(saved) == 1 else f"{first} 等 {len(saved)} 张图片"
    video = ResolvedVideo(LOCAL, job_id, f"local://{job_id}", title, float(len(saved)), [],
                          notes=[f"上传的图片 {len(saved)} 张"], extra={"kind": images.KIND, "images": saved})
    resolver = next(r for r in registry.resolvers if r.platform == LOCAL)
    job = FrameJob(job_id, video, resolver, root, count=len(saved))
    job.transcript, job.screentext = Transcript(), ScreenText()
    jobs[job_id] = job
    store.create(job, f"上传：{title}", task)
    log.event("upload.images", job_id=job_id, count=len(saved))
    spawn(process_images(job))
    return snapshot(job)


@app.post("/api/videos")
async def upload_video(file: UploadFile = File(...), task: str = Form(""), sampling_spec: str = Form("", alias="sampling")):
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
        log.event("upload", job_id=job_id, size=size, duration=video.duration)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    resolver = next(r for r in registry.resolvers if r.platform == LOCAL)
    try:
        spec = json.loads(sampling_spec) if sampling_spec else None
    except ValueError:
        spec = None
    job = FrameJob(job_id, video, resolver, root, count=sampling.plan(spec, video.duration or 0).frames)
    job.transcript = Transcript()
    job.screentext = ScreenText()
    frames_run = start_sampling(job, spec)
    jobs[job_id] = job
    store.create(job, f"上传：{name}", task)

    async def process() -> None:
        try:
            await asyncio.gather(frames_run, transcribe(job), read_screen(job), find_cuts(job))
            chapter_service.start(job)
        finally:
            if not KEEP_UPLOADS:
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
    """Sample the missing frames again (trial-limited ones excluded); a failed transcript or on-screen text pass is redone too."""
    job = get_job(job_id)
    if busy(job):
        raise HTTPException(409, "仍在抓取中，请稍后再试")
    if images.is_images(job.video):  # pictures: fetch the missing ones again, then read their text
        since = len(job.events)
        indexes = await job.retry_missing()

        async def again():
            if indexes:
                await images.fetch(job, indexes)
            await images.read_text(job)
            store.save_slots(job)
            store.save_screentext(job)

        job.screentext.status = "running"
        spawn(again())
        return {"retrying": len(indexes), "transcript": False, "screentext": True, "since": since}
    if job.video.platform == LOCAL:
        raise HTTPException(409, "本地上传的视频处理完已删除，不能补抓，请重新上传")
    redo_transcript = job.transcript.status == "failed"
    redo_screen = job.screentext.status == "failed"
    if job.restored and (redo_transcript or redo_screen or any(s.status == "missing" and s.reason != "trial" for s in job.slots)):
        # Rebuilt after a restart without stream addresses: resolve the link again first.
        _, job.video = await registry.resolve(job.video.canonical_url, job.video.part)
        job.restored = False
    since = len(job.events)
    indexes = await job.retry_missing()
    # Claimed before the tasks start, so an event stream opened right away stays open for them.
    if redo_transcript:
        job.transcript.status = "running"
    if redo_screen:
        job.screentext.status = "running"
    if indexes:
        job.running = True
        spawn(sample(job, indexes))
    if redo_transcript or redo_screen:
        chapter_service.invalidate(job)
    if redo_transcript:
        spawn(transcribe(job))
    if redo_screen:
        spawn(read_screen(job))
    return {"retrying": len(indexes), "transcript": redo_transcript, "screentext": redo_screen, "since": since}


REPLAY_KEY = re.compile(r"^\d{7}-\d{7}-\d{3}$")


@app.get("/api/link-jobs/{job_id}/replay/{key}/{name}")
async def replay_frame(job_id: str, key: str, name: str):
    """A frame of a slow-motion replay (modules/frames/replay.py), for the chat's frame strip."""
    if not REPLAY_KEY.match(key) or not re.fullmatch(r"\d{2}\.jpg", name):
        raise HTTPException(404, "没有这张画面")
    path = DATA_DIR / job_id / "replay" / key / name
    if not path.is_file() or DATA_DIR.resolve() not in path.resolve().parents:
        raise HTTPException(404, "没有这张画面")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/link-jobs/{job_id}/extra/{name}")
async def extra_frame(job_id: str, name: str):
    """A frame read on demand by view_frames (补看), for the timeline and the zoom view."""
    if not re.fullmatch(r"\d{8}\.jpg", name):
        raise HTTPException(404, "没有这张画面")
    path = DATA_DIR / job_id / "extra" / name
    if not path.is_file() or DATA_DIR.resolve() not in path.resolve().parents:
        raise HTTPException(404, "没有这张画面")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/link-jobs/{job_id}/cuts")
async def job_cuts(job_id: str):
    """The video's shot changes, for marks on the timeline. Sessions from before cuts existed get them on first ask."""
    job = get_job(job_id)
    record = cuts.load(job.root)
    if record is not None:
        return record
    if job.id in cutting:
        return {"status": "running", "cuts": [], "message": ""}
    if not job.video.streams and job.video.platform == LOCAL:  # an upload whose file was deleted after processing
        return cuts.save(job.root, "unavailable", message="上传的视频处理完已删除，无法检测镜头切换")
    spawn(find_cuts(job))
    return {"status": "running", "cuts": [], "message": ""}


@app.get("/api/link-jobs/{job_id}/source")
async def job_source(job_id: str):
    """Whether a cited moment can be played in the original, or only seen in the cached frames."""
    return await playback.state(get_job(job_id))


@app.get("/api/link-jobs/{job_id}/media")
async def job_media(job_id: str, request: Request):
    """The original video for the page's player: a kept upload, or the platform's MP4 relayed with
    the headers its CDN wants. Range requests pass through, so the player can seek."""
    job = get_job(job_id)
    playable = await playback.find(job)
    if playable is None:
        raise HTTPException(404, "原视频不可用，只能查看缓存的画面")
    if playable.kind == "file":
        kind = mimetypes.guess_type(playable.path.name)[0] or "video/mp4"
        return FileResponse(playable.path, media_type=kind)
    client = playback.http()  # one pool for every seek: no new connection per Range request
    for attempt in range(2):
        try:
            status, headers, response = await playback.relay(client, playable.stream, request.headers.get("range"))
        except httpx.HTTPError:
            raise HTTPException(502, "连不上视频平台，原视频暂时播放不了") from None
        if status in (401, 403, 404, 410) and attempt == 0:  # the address expired: ask the platform again
            await response.aclose()
            playable = await playback.find(job, fresh=True)
            if playable is None:
                raise HTTPException(404, "原视频已失效，只能查看缓存的画面")
            continue
        break
    if status >= 400:
        await response.aclose()
        raise HTTPException(502, f"视频平台拒绝播放（HTTP {status}），只能查看缓存的画面")

    first, last = playback.span(headers.get("content-range"), headers.get("content-length"))

    async def body():
        nonlocal response
        sent, resumes = 0, 0
        try:
            while True:
                try:
                    async for chunk in response.aiter_bytes():  # as they arrive: a cut-off keeps what came
                        sent += len(chunk)
                        yield chunk
                    return
                except httpx.HTTPError:
                    # The CDN dropped the connection part-way: carry on from the next byte, unseen by the player.
                    if last is None or resumes >= playback.RESUMES or first + sent > last:
                        return
                    resumes += 1
                    await response.aclose()
                    _, _, response = await playback.relay(client, playable.stream, f"bytes={first + sent}-{last}")
        finally:
            await response.aclose()

    return StreamingResponse(body(), status_code=status, headers=headers)


@app.delete("/api/link-jobs/{job_id}/source")
async def delete_source(job_id: str):
    """Delete a kept upload (the frames, text and answers stay); its moments become cached evidence."""
    job = get_job(job_id)
    if job.video.platform != LOCAL:
        raise HTTPException(400, "只有上传的视频可以删除原文件")
    if job.running:
        raise HTTPException(409, "视频还在处理，处理完再删除原文件")
    for path in (DATA_DIR / job_id).glob(f"{SOURCE}.*"):
        path.unlink(missing_ok=True)
    job.video.streams, job.video.audio_streams = [], []
    playback.forget(job_id)
    return await playback.state(job)


class ReplayRequest(BaseModel):
    start: float
    end: float


@app.post("/api/link-jobs/{job_id}/replay")
async def manual_replay(job_id: str, body: ReplayRequest):
    """A slow-motion replay the user framed on the timeline: no model involved. It is saved in the
    conversation (as an answer with no text, so the model's history skips it) and reopens with the session."""
    job = get_job(job_id)
    timer = log.Timer()
    result = await AgentTools(job).run("replay", {"start": body.start, "end": body.end})
    log.event("replay.manual", job_id=job.id, start=body.start, end=body.end, ok=not result.error, count=result.count, ms=timer.ms)
    if result.error:
        raise HTTPException(409, result.text)
    call_id = f"manual-{uuid.uuid4().hex[:8]}"
    events = [
        {"type": "tool_call.started", "call_id": call_id, "tool_name": TRACE_NAMES["replay"], "t": 0},
        {"type": "tool_call.input", "call_id": call_id, "input": {"kind": "params", "params": {"start": body.start, "end": body.end, "reason": "手动框选"}}, "t": 0},
        {"type": "tool_call.output", "call_id": call_id, "stdout": result.text, "exit_code": 0, "data": result.data, "t": round(timer.ms / 1000, 2)},
        {"type": "tool_call.completed", "call_id": call_id, "result_count": result.count, "t": round(timer.ms / 1000, 2)},
    ]
    store.add_message(job.id, "assistant", "", data={"events": events, "manual": "replay"})
    return {"manual": "replay", "events": events}


MOTION_KEY = re.compile(r"^\d{7}-\d{7}$")


@app.get("/api/link-jobs/{job_id}/motion/{key}/{name}")
async def motion_image(job_id: str, key: str, name: str):
    """A picture from measure_motion (heat map or trail), for the chat's step detail."""
    if not MOTION_KEY.match(key) or name not in ("heat.jpg", "trail.jpg"):
        raise HTTPException(404, "没有这张图")
    path = DATA_DIR / job_id / "motion" / key / "out" / name
    if not path.is_file() or DATA_DIR.resolve() not in path.resolve().parents:
        raise HTTPException(404, "没有这张图")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/link-jobs/{job_id}/screentext")
async def job_screentext(job_id: str):
    """On-screen text status and timed captions."""
    return get_job(job_id).screentext.as_dict()


@app.get("/api/link-jobs/{job_id}/transcript")
async def job_transcript(job_id: str):
    """Transcript status and timed segments."""
    return get_job(job_id).transcript.as_dict()


app.include_router(antifraud_router(lambda job_id: get_job(job_id), lambda: get_llm()))


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
        history = store.history(job.id) if body.history else []
        framed = store.framed(job.id)  # read before the question is saved: it ends the run of hand replays
        store.add_message(job.id, "user", body.question, data={"frames": frames or []})
        # The answer is saved as its text plus its events in order, consecutive text deltas merged,
        # so the UI can replay where text fell between tool calls. `t` is seconds since the question.
        # A disconnect (the user pressed stop) saves what arrived so far.
        text, events, status = [], [], "stopped"
        started = time.perf_counter()
        calls: dict[str, dict] = {}  # call_id → {name, start, ok, count, ms}
        final: dict = {}
        try:
            async for event in run_agent(job, client, body.question, frames=frames, history=history, decider=get_decider(),
                                         web=body.web, papers=body.papers, framed=framed):
                event = {**event, "t": round(time.perf_counter() - started, 2)}
                if event["type"] == "assistant.message.delta":
                    text.append(event["delta"])
                    if events and events[-1]["type"] == "assistant.message.delta":
                        events[-1] = {**events[-1], "delta": events[-1]["delta"] + event["delta"]}
                    else:
                        events.append(event)
                elif event["type"] == "browser.frame":
                    # Screenshots are large: a saved answer keeps only each browse's latest one.
                    events = [e for e in events if not (e["type"] == "browser.frame" and e.get("call_id") == event.get("call_id"))]
                    events.append(event)
                else:
                    events.append(event)
                    if event["type"] in ("run.completed", "run.error"):
                        status = "done" if event["type"] == "run.completed" else "error"
                        final = event
                    track(calls, event)
                yield sse({"run_id": run_id, **event})
        except Exception as exc:
            log.error("answer", exc, run_id=run_id, job_id=job.id)
            status, final = "error", {"code": "internal", "message": str(exc)[:200]}
            events.append({"type": "run.error", "code": "internal", "message": "后端出错了，详情见日志"})
            yield sse({"run_id": run_id, **events[-1]})
        finally:
            if status == "stopped":
                events.append({"type": "run.error", "code": "stopped", "message": "已停止"})
            store.add_message(job.id, "assistant", "".join(text), status=status, data={"events": events})
            usage = final.get("usage") or {}
            log.event("answer", run_id=run_id, job_id=job.id, platform=job.video.platform, question=body.question[:200],
                      status=status, code=final.get("code"), message=final.get("message") if status == "error" else None,
                      elapsed_ms=round((time.perf_counter() - started) * 1000), model=final.get("model"),
                      prompt_tokens=usage.get("prompt"), completion_tokens=usage.get("completion"),
                      rounds=sum(1 for c in calls.values() if c["name"].startswith("vision.")),
                      web=body.web, papers=body.papers, scope="frames" if frames else "all",
                      tools=[{k: c[k] for k in ("name", "ms", "ok", "count")} for c in calls.values()
                             if not c["name"].startswith("vision.") and "ms" in c])

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def track(calls: dict[str, dict], event: dict) -> None:
    """Fold tool_call.* events into per-call timings for the answer's log line."""
    kind, cid = event["type"], event.get("call_id")
    if kind == "tool_call.started":
        calls[cid] = {"name": event.get("tool_name", ""), "start": event["t"]}
    elif kind == "tool_call.output" and cid in calls:
        calls[cid]["ok"] = not event.get("exit_code")
    elif kind == "tool_call.completed" and cid in calls:
        calls[cid].update(ms=round((event["t"] - calls[cid]["start"]) * 1000), count=event.get("result_count"))
        calls[cid].setdefault("ok", True)


app.include_router(create_factcheck_router(
    find_job=lambda job_id: find_job(job_id), get_llm=lambda: get_llm(), store=store,
))


# ---- platform logins ------------------------------------------------------------------------------
LOCAL_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")


def local_only(request: Request) -> None:
    """Login endpoints write credentials: refuse calls made by pages from other sites."""
    origin = request.headers.get("origin")
    if (origin and not LOCAL_ORIGIN.match(origin)) or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "只能从本机的页面调用")


def platform_or_404(platform: str) -> str:
    if platform not in accounts.PLATFORMS:
        raise HTTPException(404, "没有这个平台")
    return platform


class CookieBody(BaseModel):
    cookie: str


@app.get("/api/accounts")
async def list_accounts(request: Request):
    local_only(request)
    return {"accounts": await accounts.all_status()}


@app.post("/api/accounts/{platform}/login")
async def start_login(platform: str, request: Request):
    local_only(request)
    try:
        login = await accounts.start(platform_or_404(platform))
    except accounts.AccountError as exc:
        return JSONResponse({"code": "login_unavailable", "message": str(exc)}, status_code=502)
    return login.public()


@app.get("/api/accounts/login/{login_id}")
async def poll_login(login_id: str, request: Request):
    local_only(request)
    try:
        login = await accounts.poll(login_id)
    except accounts.AccountError as exc:
        return JSONResponse({"code": "login_gone", "message": str(exc)}, status_code=404)
    out = login.public(qr=False)  # the image was sent when the login started
    if login.state in ("done", "expired", "error") and not getattr(login, "logged", False):
        login.logged = True
        log.event("account.login", platform=login.platform, state=login.state, message=login.message)
    if login.state == "done":
        out["account"] = await accounts.status(login.platform)
    return out


@app.delete("/api/accounts/login/{login_id}")
async def cancel_login(login_id: str, request: Request):
    local_only(request)
    await accounts.cancel(login_id)
    return {"ok": True}


@app.put("/api/accounts/{platform}")
async def paste_cookie(platform: str, body: CookieBody, request: Request):
    local_only(request)
    try:
        return await accounts.set_cookie(platform_or_404(platform), body.cookie)
    except accounts.AccountError as exc:
        return JSONResponse({"code": "bad_cookie", "message": str(exc)}, status_code=400)


@app.delete("/api/accounts/{platform}")
async def logout(platform: str, request: Request):
    local_only(request)
    accounts.logout(platform_or_404(platform))
    return await accounts.status(platform)


@app.get("/api/sessions")
async def list_sessions(limit: int = 50):
    """Saved sessions, most recently used first."""
    return {"sessions": store.list(limit)}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Everything needed to reopen a session: the job snapshot plus its conversation."""
    job = get_job(session_id)
    return {**snapshot(job), "task": store.get(session_id)["task"], "messages": store.messages(session_id)}


app.include_router(create_export_router(store=store, get_job=get_job, data_dir=DATA_DIR))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    job = find_job(session_id)
    if job is None:
        raise HTTPException(404, "会话不存在")
    if busy(job):
        raise HTTPException(409, "仍在抓取中，请稍后再删除")
    chapter_service.remove(session_id)
    jobs.pop(session_id, None)
    store.delete(session_id)
    shutil.rmtree(DATA_DIR / session_id, ignore_errors=True)
    return {"ok": True}
