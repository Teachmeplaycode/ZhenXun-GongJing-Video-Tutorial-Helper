"""Score the question-kind decision (modules/agent/intent.py) on evals/intent.json.

    uv run python scripts/intent_eval.py             # keyword rules, the local decision model and the main-model fallback
    uv run python scripts/intent_eval.py --keywords  # keyword rules only

Prints accuracy per method and per kind, the confusions, and for the decision model how many
decisions were sure enough (p >= intent.CONFIDENT) to change anything, and how often those were
right. The main-model fallback column only runs when a model key is configured: without one it is
reported as unavailable, never guessed. No accuracy for a method that never actually ran.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.agent import intent  # noqa: E402


def report(name: str, rows: list[tuple[str, str, object]], *, attempts=None) -> None:
    if not rows:
        print(f"\n{name}: 不可用（没有实际分类结果，不计算准确率）")
        report_usage(attempts or [])
        return
    right = sum(got.kind == want for _, want, got in rows)
    print(f"\n{name}: {right}/{len(rows)} = {right / len(rows):.0%}")
    for kind in intent.CRITERIA:
        mine = [(q, w, g) for q, w, g in rows if w == kind]
        ok = sum(g.kind == w for _, w, g in mine)
        print(f"  {intent.NAMES[kind]:<6} {ok}/{len(mine)}")
    wrong = Counter((w, g.kind) for _, w, g in rows if g.kind != w)
    for (w, g), n in wrong.most_common():
        print(f"  ✗ {intent.NAMES[w]} → {intent.NAMES[g]} ×{n}")
    sure = [(q, w, g) for q, w, g in rows if g.p is not None and g.sure]
    if any(g.p is not None for _, _, g in rows):
        ok = sum(g.kind == w for _, w, g in sure)
        print(f"  sure (p ≥ {intent.CONFIDENT}): {len(sure)}/{len(rows)}, right {ok}/{len(sure)}")
    waited = [g.elapsed_ms for _, _, g in rows if g.elapsed_ms]
    if waited:
        print(f"  平均耗时 {sum(waited) / len(rows):.0f} ms/题（含主模型回退等待）")
    report_usage(rows if attempts is None else attempts)


def report_usage(rows):
    """Include failed classifications too: discarded answers can still be billable."""
    tokens = [g.usage for _, _, g in rows if g.usage]
    if tokens:
        prompt = sum(t["prompt_tokens"] for t in tokens if t["prompt_tokens"] is not None)
        completion = sum(t["completion_tokens"] for t in tokens if t["completion_tokens"] is not None)
        unknown = sum(t["prompt_tokens"] is None or t["completion_tokens"] is None for t in tokens)
        print(f"  主模型已知 token：prompt {prompt} + completion {completion}（{len(tokens)}/{len(rows)} 题实际调用；{unknown} 题用量不完整/未知）")


async def with_fallback(questions) -> tuple[list[tuple[str, str, object]], str]:
    """Run classify without a decider: the main-model fallback, then keywords. What actually
    decided is in each Intent's `how` — no fallback available means all rows say 关键词."""
    started = time.perf_counter()
    rows = [(q, k, await intent.classify(q, None)) for q, k in questions]
    took = (time.perf_counter() - started) / len(rows) * 1000
    fell_back = sum(g.how == "主模型回退" for _, _, g in rows)
    name = f"主模型回退（{fell_back}/{len(rows)} 题由主模型分类，平均 {took:.0f} ms/题）"
    if not fell_back:
        reasons = {g.detail for _, _, g in rows if g.detail}
        note = f"；未分类原因：{next(iter(reasons))}" if reasons else ""
        name = f"主模型回退不可用（0/{len(rows)}，全部退回关键词{note}）"
    return rows, name


async def with_decider(questions, decider):
    """Score only the decision model, without silently invoking the main model instead."""
    from modules.decide import questions as dq
    rows = []
    for question, kind in questions:
        started = time.perf_counter()
        try:
            decision = await decider.choice(dq.question_state(question), intent.QUESTION, intent.CRITERIA, task="intent")
            probs = {k: round(v, 3) for k, v in decision.probabilities.items()}
            got = intent.Intent(decision.choice, probs[decision.choice], probs, "决策模型",
                                elapsed_ms=round((time.perf_counter() - started) * 1000))
        except Exception:  # optional local model unavailable; never count another method as it
            continue
        rows.append((question, kind, got))
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keywords", action="store_true")
    args = parser.parse_args()
    questions = json.loads((ROOT / "evals" / "intent.json").read_text())["questions"]
    report("关键词规则", [(q, k, intent.by_keywords(q)) for q, k in questions])
    if args.keywords:
        return
    from modules.decide.client import Decider
    decider = Decider()
    await decider.warm()
    try:
        rows = await with_decider(questions, decider)
    finally:
        await decider.aclose()
    report(f"决策模型（{decider.model}，实际分类 {len(rows)}/{len(questions)} 题；准确率分母仅含实际分类）", rows)
    fallback_rows, name = await with_fallback(questions)
    # Keyword results aren't model predictions, but failed requests can still have usage.
    report(name, [(q, k, g) for q, k, g in fallback_rows if g.how == "主模型回退"], attempts=fallback_rows)


if __name__ == "__main__":
    asyncio.run(main())
