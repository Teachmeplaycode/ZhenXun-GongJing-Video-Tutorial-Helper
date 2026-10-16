"""Lessons the agent learned from its own past answers, put into its instructions.

scripts/experience.py distills them from logged runs on questions with known answers (what the agent
looked at, what the instruments read, what it chose, whether it was right). The file is plain JSON, so
what the agent "learned" can be read, checked and edited — the capability grows in a document, not in
weights. EXPERIENCE_FILE points at it; without it nothing is added.
"""
from __future__ import annotations

import json
from pathlib import Path

from modules.settings import settings


def load() -> dict | None:
    path = settings().get("EXPERIENCE_FILE", "").strip()
    if not path or not Path(path).is_file():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def guide() -> str:
    """The lessons as a section of the system prompt, or ""."""
    data = load()
    lessons = (data or {}).get("lessons") or {}
    if not lessons:
        return ""
    lines = ["", "", "以往答题积累的经验（从有标准答案的练习中总结，按问题类型分组；只用和当前问题相关的，和画面证据冲突时以证据为准）："]
    for kind, items in lessons.items():
        lines.append(f"【{kind}】")
        lines += [f"- {item}" for item in items]
    return "\n".join(lines)
