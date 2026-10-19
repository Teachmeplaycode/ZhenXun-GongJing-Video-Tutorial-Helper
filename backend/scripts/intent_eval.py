"""Score the question-kind decision (modules/agent/intent.py) on evals/intent.json.

    uv run python scripts/intent_eval.py            # keyword rules and the local decision model
    uv run python scripts/intent_eval.py --keywords # keyword rules only

Prints accuracy per method and per kind, the confusions, and for the decision model how many
decisions were sure enough (p >= intent.CONFIDENT) to change anything, and how often those were right.
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


def report(name: str, rows: list[tuple[str, str, object]]) -> None:
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
    started = time.perf_counter()
    rows = [(q, k, await intent.classify(q, decider)) for q, k in questions]
    await decider.aclose()
    if all(g.how == "关键词" for _, _, g in rows):
        print("\n决策模型不可用（Ollama 没有运行？），上面就是退回时的结果")
        return
    report(f"决策模型（{decider.model}，平均 {(time.perf_counter() - started) / len(rows) * 1000:.0f} ms/题）", rows)


if __name__ == "__main__":
    asyncio.run(main())
