"""Saved analysis sessions in SQLite: one per link job, with its frame states and conversation.

A session outlives the in-memory FrameJob: after a restart the job is rebuilt from here (without
stream addresses), so its frames can still be viewed and questioned.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from modules.frames import FrameJob
from modules.frames.job import Slot
from modules.screentext import ScreenText
from modules.transcript import Transcript
from modules.video_source import Part, ResolvedVideo, Resolver

HISTORY_TURNS = 4  # earlier question/answer pairs sent back to the model

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  source TEXT NOT NULL,           -- what the user pasted
  task TEXT NOT NULL DEFAULT '',  -- the question typed on the import screen
  video TEXT NOT NULL,            -- ResolvedVideo.public() + resolver-private `extra`
  slots TEXT NOT NULL,            -- [{index, time, status, reason}]
  transcript TEXT,                -- Transcript.as_dict(): {status, message, segments: [{start, end, text}]}
  screentext TEXT                 -- ScreenText.as_dict(): {status, message, segments: [{start, end, text, pos}]}
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  created REAL NOT NULL,
  role TEXT NOT NULL,             -- user | assistant
  content TEXT NOT NULL,          -- question, or the answer text
  status TEXT NOT NULL DEFAULT 'done',  -- assistant: done | error | stopped
  data TEXT NOT NULL DEFAULT '{}' -- user: {frames: [index]}; assistant: {events: [non-delta §9.2 events]}
);
CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
-- Every typed decision (modules/decide), kept for calibration and possible fine-tuning later.
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created REAL NOT NULL,
  task TEXT NOT NULL,             -- e.g. source_reliability, research_intent, injection
  model TEXT NOT NULL,
  state TEXT NOT NULL,
  question TEXT NOT NULL,         -- {instructions, criteria}
  probabilities TEXT NOT NULL,    -- {option: p}
  latency_ms REAL,
  label TEXT                      -- the correct option, when someone reviews it
);
"""


class SessionStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(sessions)")}
        if "transcript" not in columns:  # databases created before transcription existed
            self.db.execute("ALTER TABLE sessions ADD COLUMN transcript TEXT")
        if "screentext" not in columns:  # ... and before on-screen text
            self.db.execute("ALTER TABLE sessions ADD COLUMN screentext TEXT")

    def close(self) -> None:
        self.db.close()

    # ---- sessions ------------------------------------------------------------------------
    def create(self, job: FrameJob, source: str, task: str = "") -> None:
        now = time.time()
        with self.db:
            self.db.execute(
                "INSERT INTO sessions (id, created, updated, source, task, video, slots) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job.id, now, now, source, task, json.dumps(video_record(job.video), ensure_ascii=False), slots_json(job)))

    def save_slots(self, job: FrameJob) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET slots = ? WHERE id = ?", (slots_json(job), job.id))

    def save_transcript(self, job: FrameJob) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET transcript = ? WHERE id = ?",
                            (json.dumps(job.transcript.as_dict(), ensure_ascii=False), job.id))

    def save_screentext(self, job: FrameJob) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET screentext = ? WHERE id = ?",
                            (json.dumps(job.screentext.as_dict(), ensure_ascii=False), job.id))

    def exists(self, session_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone() is not None

    def ids(self) -> set[str]:
        return {row[0] for row in self.db.execute("SELECT id FROM sessions")}

    def delete(self, session_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def get(self, session_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    def list(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute("""
            SELECT s.id, s.created, s.updated, s.video, s.slots, json_extract(s.transcript, '$.status') AS transcript,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id AND m.role = 'user') AS questions,
                   (SELECT content FROM messages m WHERE m.session_id = s.id AND m.role = 'user'
                     ORDER BY m.id DESC LIMIT 1) AS last_question
            FROM sessions s ORDER BY s.updated DESC LIMIT ?""", (limit,)).fetchall()
        items = []
        for row in rows:
            video, slots = json.loads(row["video"]), json.loads(row["slots"])
            ok = [s["index"] for s in slots if s["status"] == "ok"]
            items.append({
                "id": row["id"], "created": row["created"], "updated": row["updated"],
                "title": video["title"], "author": video["author"], "platform": video["platform"],
                "video_id": video["video_id"], "part": video["part"], "duration": video["duration"],
                "kind": video.get("kind") or "video", "image_count": video.get("image_count") or 0,
                "frames_ok": len(ok), "frames_total": len(slots),
                "cover_index": ok[len(ok) // 2] if ok else None, "transcript": row["transcript"],
                "questions": row["questions"], "last_question": row["last_question"] or "",
            })
        return items

    def restore(self, session_id: str, resolver: Resolver, root: Path) -> FrameJob | None:
        """Rebuild a FrameJob from a saved session. It has no stream addresses until re-resolved."""
        row = self.get(session_id)
        if row is None:
            return None
        video = video_from_record(json.loads(row["video"]))
        saved = json.loads(row["slots"])
        job = FrameJob(session_id, video, resolver, root, count=len(saved))
        job.slots = [Slot(s["index"], s["time"], s["status"], s["reason"]) for s in saved]
        for slot in job.slots:
            if slot.status == "pending" or (slot.status == "ok" and not job.frame_path(slot.index).is_file()):
                # Sampling was cut off by the restart, or the file is gone.
                slot.status, slot.reason = "missing", "interrupted"
        job.created = row["created"]
        job.restored = True
        job.transcript = Transcript.from_dict(json.loads(row["transcript"]) if row["transcript"] else None)
        job.screentext = ScreenText.from_dict(json.loads(row["screentext"]) if row["screentext"] else None)
        return job

    # ---- decisions -----------------------------------------------------------------------
    def log_decision(self, task: str, state: str, question: dict, decision) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO decisions (created, task, model, state, question, probabilities, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), task, decision.model, state, json.dumps(question, ensure_ascii=False),
                 json.dumps({k: round(v, 4) for k, v in decision.probabilities.items()}), decision.latency_ms))

    # ---- messages ------------------------------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str, *, status: str = "done", data: dict | None = None) -> None:
        now = time.time()
        with self.db:
            self.db.execute(
                "INSERT INTO messages (session_id, created, role, content, status, data) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, now, role, content, status, json.dumps(data or {}, ensure_ascii=False)))
            self.db.execute("UPDATE sessions SET updated = ? WHERE id = ?", (now, session_id))

    def messages(self, session_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, created, role, content, status, data FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
        return [{"id": r["id"], "created": r["created"], "role": r["role"], "content": r["content"],
                 "status": r["status"], **json.loads(r["data"])} for r in rows]

    def framed(self, session_id: str) -> list[tuple[float, float]]:
        """Stretches replayed by hand on the timeline since the last question, oldest first."""
        out = []
        for row in reversed(self.messages(session_id)):
            if row.get("manual") != "replay":
                break
            data = next((e.get("data") for e in row.get("events", []) if e.get("type") == "tool_call.output"), None) or {}
            if isinstance(data.get("start"), (int, float)) and isinstance(data.get("end"), (int, float)):
                out.append((float(data["start"]), float(data["end"])))
        return out[::-1]

    def history(self, session_id: str, turns: int = HISTORY_TURNS) -> list[dict]:
        """Completed question/answer pairs, oldest first, as chat messages."""
        pairs = []
        rows = self.messages(session_id)
        for question, answer in zip(rows, rows[1:]):
            if question["role"] == "user" and answer["role"] == "assistant" and answer["status"] == "done" and answer["content"]:
                pairs.append([{"role": "user", "content": question["content"]},
                              {"role": "assistant", "content": answer["content"]}])
        return [m for pair in pairs[-turns:] for m in pair]


def slots_json(job: FrameJob) -> str:
    return json.dumps([{"index": s.index, "time": s.time, "status": s.status, "reason": s.reason} for s in job.slots])


def video_record(video: ResolvedVideo) -> dict:
    record = video.public()
    record.pop("stream_count", None)
    record["extra"] = video.extra
    return record


def video_from_record(r: dict) -> ResolvedVideo:
    return ResolvedVideo(
        r["platform"], r["video_id"], r["canonical_url"], r["title"], r["duration"], [],
        part=r["part"], parts=[Part(p["index"], p["title"], p["duration"]) for p in r["parts"]],
        cover=r["cover"], author=r["author"], description=r["description"],
        playable_duration=r["playable_duration"], notes=r["notes"], extra=r.get("extra") or {})
