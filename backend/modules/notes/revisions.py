"""Current-note fingerprints, recoverable snapshots and editor-aware revisions.

The editor's blocks are the authoritative user copy. Viewport movement is not an edit; block
content and layout are. A generated revision never writes the current note or board until applied.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import time
import uuid

from .export import reading_order
from .task import BOARD, FILE, load, write

HISTORY_DIR = "notes-revisions"
COMMIT_DIR = ".notes-commit"


def recover_commit(root) -> None:
    """A stopped/failed two-file commit rolls back by renaming prepared backups, without LLM work."""
    stage = root / COMMIT_DIR
    marker = load(stage, "pending.json")
    if marker is None:
        return
    for name, flag, backup in ((FILE, "had_note", "previous-note.json"), (BOARD, "had_board", "previous-board.json")):
        if marker[flag]:
            if (stage / backup).is_file():
                os.replace(stage / backup, root / name)
        else:
            (root / name).unlink(missing_ok=True)
    (stage / "pending.json").unlink(missing_ok=True)
    shutil.rmtree(stage, ignore_errors=True)


def commit_current(root, record: dict, board: dict | None) -> None:
    """Prepare both documents before touching either current file, with restart-safe rollback."""
    recover_commit(root)
    stage = root / COMMIT_DIR
    stage.mkdir(exist_ok=True)
    write(stage, record, "next-note.json")
    if board is not None:
        write(stage, board, "next-board.json")
    marker = {"had_note": (root / FILE).is_file(), "had_board": (root / BOARD).is_file()}
    for name, flag, backup in ((FILE, "had_note", "previous-note.json"), (BOARD, "had_board", "previous-board.json")):
        if marker[flag]:
            shutil.copyfile(root / name, stage / backup)
    write(stage, marker, "pending.json")
    try:
        if board is None:
            (root / BOARD).unlink(missing_ok=True)
        else:
            os.replace(stage / "next-board.json", root / BOARD)
        os.replace(stage / "next-note.json", root / FILE)
    except BaseException:
        recover_commit(root)
        raise
    (stage / "pending.json").unlink(missing_ok=True)
    shutil.rmtree(stage, ignore_errors=True)


def fingerprint(note: dict | None, board: dict | None) -> str | None:
    if not note:
        return None
    value = {"note": note, "blocks": board.get("blocks") if board else None}
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "r_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def effective_note(note: dict | None, board: dict | None) -> dict | None:
    """Use edited section text/title/figures rather than the older model output as the base."""
    if not note:
        return None
    out = copy.deepcopy(note)
    if not board or not isinstance(board.get("blocks"), list):
        return out
    sections = []
    last = None
    for b in reading_order(board["blocks"]):
        kind = b.get("type")
        if kind == "title":
            out["title"], out["summary"] = b.get("text") or out.get("title", ""), b.get("summary", "")
        elif kind == "section":
            sid = str(b.get("id") or f"edited-{len(sections) + 1}")
            last = {"id": sid.removeprefix("sec-"), "figures": [],
                    **{k: copy.deepcopy(b.get(k, [] if k in {"points", "formulas", "examples", "keywords"} else ""))
                       for k in ("title", "start", "end", "points", "formulas", "examples", "keywords")}}
            sections.append(last)
        elif kind == "figure":
            linked = next((s for s in sections if "sec-" + s["id"] == b.get("section")), None)
            target = linked or last
            if target is not None:
                target["figures"].append({k: b.get(k) for k in ("time", "caption", "src")})
        elif kind == "mindmap":
            out["mindmap"] = copy.deepcopy(b.get("tree"))
    # An intentionally emptied board is still an edited copy; do not resurrect deleted sections.
    out["sections"] = sections
    return out


def board_context(board: dict | None) -> str:
    """Free annotations have no section equivalent, but must inform a revision and stay intact."""
    if not board or not isinstance(board.get("blocks"), list):
        return ""
    content = []
    for b in reading_order(board["blocks"]):
        if b.get("type") == "text" and b.get("text"):
            content.append(str(b["text"])[:4000])
    return "\n\n".join(content)[:12000]


def _height(b: dict) -> float:
    if b.get("type") == "title":
        return 156
    if b.get("type") == "figure":
        return float(b.get("w") or 380) * 9 / 16 + 44
    if b.get("type") == "section":
        # A conservative fallback until the editor measures actual fonts/formulas/images.
        columns = max(10, int((float(b.get("w") or 580) - 48) / 16))
        def lines(items):
            return sum(max(1, (len(str(s)) + columns - 1) // columns) for s in items or [])
        return 80 + 30 * lines(b.get("points")) + 64 * lines(b.get("formulas")) + 32 * lines(b.get("examples"))
    return 300


def revision_board(note: dict, base_board: dict | None, changed_ids: list[str] | None = None) -> dict:
    """Preserve annotations and edited layout; update named sections and append new material."""
    if base_board is not None:
        board = copy.deepcopy(base_board)
        board.pop("saved", None)
        blocks = board.setdefault("blocks", [])
    else:
        board = {"version": 1, "viewport": {"x": 40, "y": 40, "zoom": 0.8}, "blocks": []}
        blocks = board["blocks"]
    by_id = {b.get("id"): b for b in blocks}
    if "title" not in by_id and base_board is None:
        title = {"id": "title", "type": "title", "x": 0, "y": 0, "w": 1000,
                 "text": note.get("title", "视频笔记"), "summary": note.get("summary", "")}
        blocks.append(title)
    y = max((float(b.get("y") or 0) + _height(b) for b in blocks), default=0) + 56
    changed = set(changed_ids or [])
    changed_blocks = []
    for s in note.get("sections") or []:
        bid = "sec-" + s["id"]
        old = by_id.get(bid)
        if old is None:
            block = {"id": bid, "type": "section", "x": 0, "y": y, "w": 580}
            blocks.append(block)
        elif s["id"] in changed:
            block = old
        else:
            continue
        old_height = _height(block)
        block.update({k: copy.deepcopy(s.get(k)) for k in ("title", "start", "end", "points", "formulas", "examples", "keywords")})
        changed_blocks.append(bid)
        growth = max(0, _height(block) - old_height) if old is not None else 0
        if growth:
            # Keep every column's horizontal arrangement and relative lower layout intact.
            old_bottom = float(block.get("y") or 0) + old_height
            for lower in blocks:
                if lower is not block and float(lower.get("y") or 0) >= old_bottom:
                    lower["y"] = float(lower.get("y") or 0) + growth
        fy = float(block.get("y") or 0)
        known_srcs = {b.get("src") for b in blocks if b.get("type") == "figure"}
        for f in s.get("figures") or []:
            if not f.get("src") or f["src"] in known_srcs:
                continue
            figure = {"id": "fig-" + uuid.uuid4().hex[:12], "type": "figure", "section": bid,
                      "x": 620, "y": fy, "w": 380, **copy.deepcopy(f)}
            blocks.append(figure)
            known_srcs.add(f["src"])
            fy += _height(figure) + 20
        y = max(y, float(block.get("y") or 0) + _height(block), fy) + 56
    if base_board is None and note.get("mindmap"):
        blocks.append({"id": "mindmap", "type": "mindmap", "x": 1060, "y": 212, "w": 640,
                       "tree": copy.deepcopy(note["mindmap"])})
    board["needs_measure"] = True
    board["changed_blocks"] = changed_blocks
    return board


def archive(root, record: dict, board: dict | None) -> list[dict]:
    """Snapshot precisely what the editor/exports currently show, including hand edits."""
    history = list(record.get("history") or [])
    if not record.get("note"):
        return history
    rid = uuid.uuid4().hex
    note = effective_note(record["note"], board)
    meta = {"id": rid, "title": note.get("title") or "视频笔记", "created": time.time(),
            "source": record.get("source", "video"), "message_ids": record.get("message_ids") or []}
    write(root / HISTORY_DIR, {**meta, "note": record["note"], "board": board}, rid + ".json")
    return [meta, *history]


def history_snapshot(root, record: dict, rid: str) -> dict | None:
    # Only indexed UUIDs can be opened; no arbitrary paths or another job's snapshots.
    if not any(item.get("id") == rid for item in record.get("history") or []):
        return None
    return load(root / HISTORY_DIR, rid + ".json")
