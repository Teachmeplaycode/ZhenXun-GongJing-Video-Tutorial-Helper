"""Several tutorials of the same task side by side (2–5: the 对照 tab, or several links pasted on the homepage): one row per operation, each video's step for it.

Three VLOOKUP tutorials: which step is where in each, who explains absolute references and who skips
them, which one fits WPS. Built from each video's step cards (modules/steps.py) with one model call
that aligns them; the step numbers it gives are checked against the cards, so every cell in the table
is a real step with its time and frame. Cached per set of videos in DATA_ROOT/compare/.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

LABELS = "甲乙丙丁戊"
MAX_VIDEOS = 5  # the homepage takes up to five links at once
MAX_ROWS = 40

PROMPT = ("你在对照讲同一类操作的几个软件教程。给你每个教程的操作步骤（带序号）。"
          "把做同一件事的步骤对成一行，按操作的自然先后排。每行格式：行|操作|{cols}|差别。"
          "某个教程没有这一步就写 -；一个教程的几步合起来做这件事，写第一步的号。操作不超过 16 字；"
          "差别不超过 40 字，写各教程做法或讲解的不同（比如谁讲了原因、谁跳过了、谁用了快捷键、版本或界面不同），没有差别就留空。"
          "每个步骤最多出现在一行里，不要编造步骤。"
          "最后再输出：总结|一段话，不超过 120 字，说这几个教程各自适合什么人、该先看哪个；"
          "然后每个教程一行：{labels_line}。")

Completer = Callable[[list[dict]], Awaitable[str]]


def key(ids: list[str]) -> str:
    return hashlib.sha1(",".join(sorted(ids)).encode()).hexdigest()[:16]


def path(root: Path, ids: list[str]) -> Path:
    return root / "compare" / f"{key(ids)}.json"


def load(root: Path, ids: list[str]) -> dict | None:
    try:
        return json.loads(path(root, ids).read_text())
    except (OSError, ValueError):
        return None


def save(root: Path, ids: list[str], record: dict) -> dict:
    p = path(root, ids)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False))
    return record


def _clock(t: float) -> str:
    t = int(max(0, t))
    return f"{t // 60:02d}:{t % 60:02d}"


def messages(videos: list[dict]) -> list[dict]:
    parts = []
    for label, v in zip(LABELS, videos):
        listing = "\n".join(f"{s['n']}. [{_clock(s['time'])}] {s['action']}" for s in v["steps"])
        parts.append(f"教程{label}：{v['title']}\n{listing}")
    labels = LABELS[:len(videos)]
    prompt = PROMPT.format(cols="|".join(f"{x}的步骤号" for x in labels),
                           labels_line="；".join(f"{x}|一句话特点（不超过 40 字）" for x in labels))
    return [{"role": "system", "content": prompt}, {"role": "user", "content": "\n\n".join(parts)}]


ROW = re.compile(r"^\s*(?:行|\d+)\s*\|")  # models number the rows instead of writing 行


def parse(output: str, videos: list[dict]) -> dict:
    n = len(videos)
    by_n = [{s["n"]: s for s in v["steps"]} for v in videos]
    used = [set() for _ in videos]
    rows, summary, traits = [], "", {}
    for line in (output or "").splitlines():
        cells = [c.strip() for c in line.strip().split("|")]
        if ROW.match(line) and len(cells) >= 2 + n and cells[1] != "操作":  # the format line echoed back
            op = cells[1][:24]
            picked = []
            for i in range(n):
                raw = cells[2 + i]
                step = by_n[i].get(int(raw)) if raw.isdigit() else None
                if step is not None and step["n"] in used[i]:
                    step = None  # a step already placed in an earlier row
                if step is not None:
                    used[i].add(step["n"])
                picked.append(None if step is None else {k: step.get(k) for k in ("n", "time", "action", "frame", "shot")})
            note = cells[2 + n] if len(cells) > 2 + n else ""
            if op and any(picked) and len(rows) < MAX_ROWS:
                rows.append({"op": op, "cells": picked, "note": note[:60]})
        elif cells[0] == "总结" and len(cells) > 1:
            summary = cells[1][:200]
        elif len(cells) > 1 and cells[0] in LABELS[:n]:
            traits[cells[0]] = cells[1][:60]
    return {"rows": rows, "summary": summary, "traits": [traits.get(LABELS[i], "") for i in range(n)]}


async def build(root: Path, jobs: list, cards: list[dict], complete: Completer, asked: list[str] | None = None,
                skipped: list[str] | None = None) -> dict:
    """`jobs` and their step `cards`, in the order the person picked them. Raises on a model failure.
    `asked`: the ids the person gave when some were left out (`skipped`: their titles, no steps); the record
    is saved under those too, so asking again finds it."""
    ids = [j.id for j in jobs]
    videos = [{"id": j.id, "title": j.video.title, "duration": j.video.duration, "label": LABELS[i],
               "steps": c.get("steps") or []} for i, (j, c) in enumerate(zip(jobs, cards))]
    table = parse(await complete(messages(videos)), videos)
    shared = sum(1 for r in table["rows"] if all(r["cells"]))
    record = {"status": "done" if table["rows"] else "empty", "ids": ids,
              "videos": [{k: v[k] for k in ("id", "title", "duration", "label")} | {"steps": len(v["steps"]), "trait": t}
                         for v, t in zip(videos, table["traits"])],
              "rows": table["rows"], "summary": table["summary"],
              "message": f"{len(table['rows'])} 个操作，{shared} 个每个教程都有" if table["rows"] else "这几个教程对不上同样的操作",
              "skipped": skipped or []}
    if asked and sorted(asked) != sorted(ids):
        save(root, asked, record)
    return save(root, ids, record)
