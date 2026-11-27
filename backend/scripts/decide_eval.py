"""Score the decision model (modules/decide) on evals/decide.json: research intent, source reliability, page injection.

    uv run python scripts/decide_eval.py              # all three tasks on the local decision model
    uv run python scripts/decide_eval.py --json out   # also save every probability for later calibration

Each task is asked exactly as the app asks it (modules/decide/questions.py) and decided with the app's
thresholds. Research intent is reported three ways: the model alone, the keyword rules used when the
model is off (DECISION=off on the web demo), and what the app does with the model on (model or the
explicit-ask keywords). Accuracy comes with a Wilson 95 % interval; probabilities with a Brier score.
Cases the model could not answer are counted as unavailable, never as right or wrong.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.agent.run import OUTSIDE_RE, RESEARCH_RE  # noqa: E402
from modules.agent.tools import INJECTION_BLOCK  # noqa: E402
from modules.decide import questions as dq  # noqa: E402
from modules.decide.client import Decider  # noqa: E402


def wilson(right: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    p = right / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def line(name: str, right: int, n: int, extra: str = "") -> str:
    lo, hi = wilson(right, n)
    return f"  {name}: {right}/{n} = {right / n:.1%}（95% 区间 {lo:.0%}–{hi:.0%}）{extra}"


def binary_report(title: str, rows: list[dict], threshold: float) -> dict:
    """rows: {text, want, p, ms}. Positive = p >= threshold."""
    got = [r for r in rows if r["p"] is not None]
    right = sum((r["p"] >= threshold) == r["want"] for r in got)
    tp = sum(r["p"] >= threshold and r["want"] for r in got)
    fp = sum(r["p"] >= threshold and not r["want"] for r in got)
    fn = sum(r["p"] < threshold and r["want"] for r in got)
    brier = statistics.mean((r["p"] - r["want"]) ** 2 for r in got)
    ms = statistics.median(r["ms"] for r in got)
    print(f"\n{title}（实际判断 {len(got)}/{len(rows)} 题）")
    print(line("准确率", right, len(got), f"  Brier {brier:.3f}  中位耗时 {ms:.0f} ms"))
    print(f"  查准 {tp}/{tp + fp}  查全 {tp}/{tp + fn}")
    for r in got:
        if (r["p"] >= threshold) != r["want"]:
            print(f"  ✗ 应为{'是' if r['want'] else '否'} p={r['p']:.2f}  {r['text'][:60]!r}")
    return {"n": len(got), "right": right, "brier": round(brier, 4), "median_ms": ms}


async def research(decider: Decider, cases) -> dict:
    rows = []
    for question, want in cases:
        try:
            p = await decider.noul(dq.question_state(question), dq.RESEARCH, task="research_intent")
            d = decider.last_ms
        except Exception:
            p, d = None, None
        rows.append({"text": question, "want": want, "p": p, "ms": d})
    model = binary_report("① 要不要查资料 · 决策模型单独（p ≥ 0.5）", rows, 0.5)

    keywords = [bool(RESEARCH_RE.search(q) or OUTSIDE_RE.search(q)) for q, _ in cases]
    right = sum(k == w for k, (_, w) in zip(keywords, cases))
    print("\n  对照 · 关键词规则（决策模型关闭时，网页版 / 云端用这个）")
    print(line("准确率", right, len(cases)))
    app = [(r["p"] is not None and r["p"] >= 0.5) or bool(RESEARCH_RE.search(r["text"])) for r in rows]
    app_right = sum(a == r["want"] for a, r in zip(app, rows))
    print("  对照 · 应用实际判断（模型 p ≥ 0.5，或问题里明确说了要查）")
    print(line("准确率", app_right, len(rows)))
    return {"model": model, "keywords": {"n": len(cases), "right": right},
            "app": {"n": len(rows), "right": app_right}, "rows": rows}


async def reliability(decider: Decider, cases) -> dict:
    criteria = dq.RELIABILITY["criteria"]
    rows = []
    for c in cases:
        try:
            d = await decider.choice(dq.result_state(c["query"], c["title"], c["site"], c["snippet"]),
                                     dq.RELIABILITY["instructions"], criteria, task="source_reliability")
            probs, ms = d.probabilities, d.latency_ms
        except Exception:
            probs, ms = None, None
        rows.append({"text": f"{c['query']} ← {c['title']}（{c['site']}）", "want": c["label"], "probs": probs, "ms": ms})
    got = [r for r in rows if r["probs"]]
    pick = {id(r): max(r["probs"], key=r["probs"].get) for r in got}
    right = sum(pick[id(r)] == r["want"] for r in got)
    brier = statistics.mean(sum((r["probs"][k] - (k == r["want"])) ** 2 for k in criteria) for r in got)
    ms = statistics.median(r["ms"] for r in got)
    print(f"\n② 搜索结果可靠性 · 三选一（实际判断 {len(got)}/{len(rows)} 题）")
    print(line("准确率", right, len(got), f"  Brier(三类) {brier:.3f}  中位耗时 {ms:.0f} ms"))
    names = {"reliable": "可靠", "unreliable": "相关但不可靠", "irrelevant": "不相关"}
    for k in criteria:
        mine = [r for r in got if r["want"] == k]
        ok = sum(pick[id(r)] == k for r in mine)
        print(f"    {names[k]:<6} {ok}/{len(mine)}")
    for (w, g), n in Counter((r["want"], pick[id(r)]) for r in got if pick[id(r)] != r["want"]).most_common():
        print(f"    ✗ {names[w]} → {names[g]} ×{n}")
    # What matters downstream: irrelevant results are dropped, so a relevant result dropped is the costly miss.
    dropped_relevant = sum(pick[id(r)] == "irrelevant" and r["want"] != "irrelevant" for r in got)
    kept_irrelevant = sum(pick[id(r)] != "irrelevant" and r["want"] == "irrelevant" for r in got)
    print(f"    应用里的后果：相关结果被丢掉 {dropped_relevant} 条，不相关结果没丢掉 {kept_irrelevant} 条")
    for r in got:
        if pick[id(r)] != r["want"]:
            print(f"    ✗ {names[r['want']]}→{names[pick[id(r)]]}  {r['text'][:70]}")
    return {"n": len(got), "right": right, "brier": round(brier, 4), "median_ms": ms,
            "dropped_relevant": dropped_relevant, "kept_irrelevant": kept_irrelevant, "rows": rows}


async def injection(decider: Decider, cases) -> dict:
    rows = []
    for text, want in cases:
        try:
            p = await decider.noul(dq.page_state(text), dq.INJECTION, task="injection")
            d = decider.last_ms
        except Exception:
            p, d = None, None
        rows.append({"text": text, "want": want, "p": p, "ms": d})
    report = binary_report(f"③ 网页注入拦截（p ≥ {INJECTION_BLOCK} 拦下）", rows, INJECTION_BLOCK)
    return {**report, "rows": rows}


class TimedDecider(Decider):
    """Remembers how long the last decision took, so noul (which returns only p) can be timed too."""
    last_ms: float | None = None

    async def choice(self, *args, **kwargs):
        d = await super().choice(*args, **kwargs)
        self.last_ms = d.latency_ms
        return d


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="save every probability to this file")
    args = parser.parse_args()
    cases = json.loads((ROOT / "evals" / "decide.json").read_text())
    decider = TimedDecider()
    await decider.warm()
    try:
        print(f"决策模型：{decider.model}")
        out = {"model": decider.model,
               "research": await research(decider, cases["research"]),
               "reliability": await reliability(decider, cases["reliability"]),
               "injection": await injection(decider, cases["injection"])}
    finally:
        await decider.aclose()
    total_right = out["research"]["model"]["right"] + out["reliability"]["right"] + out["injection"]["right"]
    total_n = out["research"]["model"]["n"] + out["reliability"]["n"] + out["injection"]["n"]
    print("\n合计（三类判断，决策模型单独）")
    print(line("准确率", total_right, total_n))
    if args.json:
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"\n逐题概率已存到 {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
