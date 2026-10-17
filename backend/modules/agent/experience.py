"""Lessons the agent learned from its own past answers, put into its instructions.

scripts/experience.py distills them from logged runs on questions with known answers (what the agent
looked at, what the instruments read, what it chose, whether it was right). The file is plain JSON, so
what the agent "learned" can be read, checked and edited — the capability grows in a document, not in
weights. EXPERIENCE_FILE points at it; without it nothing is added.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from modules.llm import Usage
from modules.settings import settings

# Which kinds a question belongs to, asked of the answering model in one small call (~120 tokens).
# On 120 MotionBench training questions (2026-10-17) the right kind was among its top two 94% of the
# time (top one 78%); a keyword classifier got 68%. Two kinds' lessons instead of all of them keep the
# prompt small and keep, say, action-order advice out of a question about objects.
CLASSIFY = "把下面关于视频的问题归到最相关的两类（按相关程度排序），只输出 JSON：{{\"kinds\": [\"…\", \"…\"]}}。\n类别：{kinds}\n问题：{question}"


def load() -> dict | None:
    path = settings().get("EXPERIENCE_FILE", "").strip()
    if not path or not Path(path).is_file():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def selective() -> bool:
    """EXPERIENCE_SELECT=all puts every lesson in (the first experiments); by default only the two relevant kinds."""
    return settings().get("EXPERIENCE_SELECT", "top2").lower() != "all"


def kinds() -> list[str]:
    return list(((load() or {}).get("lessons") or {}).keys())


async def classify(client, question: str, timeout: float = 15) -> list[str] | None:
    """The (up to) two kinds a question belongs to, or None when the model couldn't say."""
    names = kinds()
    if not names:
        return None
    prompt = CLASSIFY.format(kinds="；".join(names), question=question[:1500])

    async def ask() -> str:
        return "".join([d async for d in client.stream([{"role": "user", "content": prompt}], Usage(), max_tokens=60)])

    try:
        text = await asyncio.wait_for(ask(), timeout)
        found = json.loads(re.search(r"\{.*\}", text, re.S).group(0)).get("kinds") or []
    except Exception:
        return None
    picked = [k for k in found if k in names][:2]
    return picked or None


def guide(only: list[str] | None = None) -> str:
    """The lessons as a section of the system prompt (only these kinds when given), or ""."""
    data = load()
    lessons = (data or {}).get("lessons") or {}
    if only:
        lessons = {k: v for k, v in lessons.items() if k in only}
    if not lessons:
        return ""
    lines = ["", "", "以往答题积累的经验（从有标准答案的练习中总结，按问题类型分组；只用和当前问题相关的，和画面证据冲突时以证据为准）："]
    for kind, items in lessons.items():
        lines.append(f"【{kind}】")
        lines += [f"- {item}" for item in items]
    return "\n".join(lines)
