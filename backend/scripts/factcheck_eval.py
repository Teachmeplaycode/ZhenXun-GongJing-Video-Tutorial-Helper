"""Score the 科普核验 (fact check) against hand-labelled claims in evals/factcheck.json.

    uv run python scripts/factcheck_eval.py                 # reviewed items only
    uv run python scripts/factcheck_eval.py --drafts        # also items whose labels aren't confirmed yet
    uv run python scripts/factcheck_eval.py --only vinegar  # items whose id contains this
    uv run python scripts/factcheck_eval.py --prepare       # only parse the links

Each item is a video or 图文 link with its key claims, each labelled correct / partial / wrong /
unverifiable by a person, with the authoritative source the label rests on. The run imports every
link into a backend of its own (data/evals-factcheck, reused between runs), runs the fact check, and
matches the report's claims to the labelled ones (one model call per item: which extracted claim, if
any, says the same thing). Then, over all labelled claims:

  found       the check extracted the claim at all
  accuracy    its verdict equals the label (among found claims)
  caught      a wrong / partial claim was flagged wrong or partial — the number that matters most:
              misinformation that reaches a parent unflagged
  false alarm a correct claim was called wrong
  sourced     a verdict other than unverifiable cites at least one authoritative source

Results go to data/evals-factcheck/results/<time>.json and are compared with the previous run.
Labels must come from people and authoritative sources, never from this system's own reports.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval as qa  # noqa: E402 — the QA eval's backend runner and link preparation

ITEMS = ROOT / "evals" / "factcheck.json"
DATA = ROOT / "data" / "evals-factcheck"
RESULTS = DATA / "results"
LABELS = ("correct", "partial", "wrong", "unverifiable")
PROBLEM = ("wrong", "partial")
NAMES = {"correct": "正确", "partial": "部分正确", "wrong": "错误", "unverifiable": "无法核实"}


# ---- running ----------------------------------------------------------------------------------
async def run_check(client: httpx.AsyncClient, job_id: str) -> dict:
    """One fact-check run: {status, claims: [{claim, verdict, risk, sources}], seconds, error}."""
    started, report, error = time.perf_counter(), None, None
    try:
        async with client.stream("POST", f"/api/link-jobs/{job_id}/factcheck", json={"web": True, "papers": True}, timeout=900) as r:
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                e = json.loads(line[5:])
                if e.get("type") == "factcheck.completed":
                    report = e.get("report") or {}
                elif e.get("type") == "factcheck.error":
                    error = e.get("message") or e.get("code")
    except httpx.HTTPError as exc:
        error = f"连接失败：{exc}"
    claims = [{"claim": c.get("claim", ""), "verdict": c.get("verdict"), "risk": c.get("risk"),
               "sources": [{"url": s.get("url"), "trusted": bool(s.get("trusted")), "authority": s.get("authority")}
                           for s in c.get("sources") or []]}
              for c in (report or {}).get("claims") or []]
    return {"status": "done" if report is not None else "error", "claims": claims, "error": error,
            "seconds": round(time.perf_counter() - started, 1)}


MATCH_SYSTEM = """你在给事实核查系统打分。给你若干条「标注说法」和系统抽取出的「抽取说法」（都编了号）。
对每条标注说法，找出意思相同（说的是同一件事、同一个主张，措辞可以不同）的抽取说法编号；没有就填 null。
一条抽取说法只能对应一条标注说法。只返回 JSON：{"matches": {"标注编号": 抽取编号或 null}}"""


async def match(llm, labelled: list[dict], extracted: list[dict]) -> dict[str, int | None]:
    """Labelled claim id → index into extracted (or None)."""
    if not extracted:
        return {c["id"]: None for c in labelled}
    payload = {"标注说法": {c["id"]: c["claim"] for c in labelled},
               "抽取说法": {str(i): c["claim"] for i, c in enumerate(extracted)}}
    raw = await ask_json(llm, MATCH_SYSTEM, json.dumps(payload, ensure_ascii=False))
    found = (raw or {}).get("matches") or {}
    out, used = {}, set()
    for c in labelled:
        i = found.get(c["id"])
        try:
            i = int(i) if i is not None else None
        except (TypeError, ValueError):
            i = None
        out[c["id"]] = i if i is not None and 0 <= i < len(extracted) and i not in used else None
        if out[c["id"]] is not None:
            used.add(out[c["id"]])
    return out


async def ask_json(llm, system: str, user: str) -> dict | None:
    from modules.llm import Usage
    chunks = []
    async for delta in llm.stream([{"role": "system", "content": system}, {"role": "user", "content": user}], Usage(), max_tokens=800):
        chunks.append(delta)
    text = "".join(chunks)
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1]) if 0 <= start < end else None
    except ValueError:
        return None


# ---- scoring ----------------------------------------------------------------------------------
def grade(item: dict, run: dict, matches: dict[str, int | None]) -> list[dict]:
    """One row per labelled claim: what the check said about it."""
    rows = []
    for c in item["claims"]:
        i = matches.get(c["id"])
        got = run["claims"][i] if i is not None else None
        verdict = got["verdict"] if got else None
        rows.append({
            "item": item["id"], "claim_id": c["id"], "claim": c["claim"], "label": c["label"],
            "found": got is not None, "verdict": verdict, "extracted": got["claim"] if got else None,
            "correct": verdict == c["label"],
            "flagged": verdict in PROBLEM,
            "sourced": bool(got and any(s["trusted"] for s in got["sources"])),
        })
    return rows


def metrics(rows: list[dict]) -> dict:
    def rate(hit: int, n: int) -> dict:
        return {"rate": round(hit / n, 3) if n else None, "n": n, "hit": hit}
    found = [r for r in rows if r["found"]]
    problems = [r for r in rows if r["label"] in PROBLEM]
    good = [r for r in rows if r["label"] == "correct"]
    decided = [r for r in found if r["verdict"] in ("correct", "partial", "wrong")]
    return {
        "claims": len(rows),
        "found": rate(len(found), len(rows)),
        "accuracy": rate(sum(r["correct"] for r in found), len(found)),
        "caught": rate(sum(r["flagged"] for r in problems), len(problems)),
        "false_alarm": rate(sum(r["verdict"] == "wrong" for r in good), len(good)),
        "sourced": rate(sum(r["sourced"] for r in decided), len(decided)),
        "confusion": {lab: {v or "未抽取": sum(1 for r in rows if r["label"] == lab and r["verdict"] == v)
                            for v in (*LABELS, None)} for lab in LABELS},
    }


def validate(spec: dict) -> list[str]:
    """Problems in evals/factcheck.json (an empty list: fine)."""
    errors = []
    for key, item in (spec.get("items") or {}).items():
        if not item.get("url"):
            errors.append(f"{key}: 没有 url")
        ids = [c.get("id") for c in item.get("claims") or []]
        if not ids:
            errors.append(f"{key}: 没有标注说法")
        if len(set(ids)) != len(ids):
            errors.append(f"{key}: 说法 id 重复")
        for c in item.get("claims") or []:
            if c.get("label") not in LABELS:
                errors.append(f"{key}/{c.get('id')}: label 必须是 {'/'.join(LABELS)}")
            if not (c.get("claim") or "").strip():
                errors.append(f"{key}/{c.get('id')}: 说法是空的")
            if item.get("reviewed") and c.get("label") != "unverifiable" and not c.get("evidence"):
                errors.append(f"{key}/{c.get('id')}: 已确认的标签要附权威出处（evidence）")
    return errors


def pct(m: dict) -> str:
    return "—" if m["rate"] is None else f"{m['rate'] * 100:.0f}%（{m['hit']}/{m['n']}）"


def print_report(m: dict, before: dict | None) -> None:
    def delta(key):
        if not before or before.get(key, {}).get("rate") is None or m[key]["rate"] is None:
            return ""
        d = (m[key]["rate"] - before[key]["rate"]) * 100
        return f"  {'+' if d >= 0 else ''}{d:.0f}"
    print(f"\n标注说法 {m['claims']} 条")
    for key, name in (("found", "抽取到"), ("accuracy", "判定准确"), ("caught", "错误说法被拦下"),
                      ("false_alarm", "正确说法被误判为错误"), ("sourced", "判定有权威出处")):
        print(f"  {name:<14} {pct(m[key])}{delta(key)}")
    print("\n  标注 \\ 判定    " + "  ".join(f"{NAMES[v]:>6}" for v in LABELS) + "   未抽取")
    for lab in LABELS:
        row = m["confusion"][lab]
        print(f"  {NAMES[lab]:<10}" + "  ".join(f"{row[v]:>8}" for v in LABELS) + f"  {row['未抽取']:>6}")


# ---- main ---------------------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="only items whose id contains this (comma-separated: any of them)")
    parser.add_argument("--drafts", action="store_true", help="include items whose labels aren't reviewed yet")
    parser.add_argument("--prepare", action="store_true", help="only import the links")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()

    spec = json.loads(ITEMS.read_text())
    if errors := validate(spec):
        raise SystemExit("evals/factcheck.json 有问题：\n  " + "\n  ".join(errors))
    wanted = [w.strip() for w in (args.only or "").split(",") if w.strip()]
    items = [{"id": k, **v} for k, v in spec["items"].items()
             if (args.drafts or v.get("reviewed")) and (not wanted or any(w in k for w in wanted))]
    if not items:
        raise SystemExit("没有要跑的条目（还没有确认过的？加 --drafts 跑草稿）")
    qa.VIDEOS = DATA / "videos.json"
    with qa.Backend({"GONGJING_DATA_DIR": str(DATA)}) as backend:
        async with httpx.AsyncClient(base_url=backend.base, timeout=60) as client:
            print(f"准备 {len(items)} 条链接")
            ids = await qa.prepare(client, {i["id"]: {"url": i["url"]} for i in items})
            if args.prepare:
                return
            from modules.llm import LLMConfig, create_client
            llm = create_client(LLMConfig.from_env())
            gate = asyncio.Semaphore(args.concurrency)

            async def one(item):
                if item["id"] not in ids:
                    return {"id": item["id"], "status": "error", "error": "链接没有解析成功", "claims": []}, \
                        grade(item, {"claims": []}, {})
                async with gate:
                    run = await run_check(client, ids[item["id"]])
                matches = await match(llm, item["claims"], run["claims"]) if run["status"] == "done" else {}
                rows = grade(item, run, matches)
                ok = sum(r["correct"] for r in rows)
                print(f"  {item['id']}: {ok}/{len(rows)} 判定一致 · 抽出 {len(run['claims'])} 条 · {run['seconds']} 秒"
                      + (f" · {run['error']}" if run.get("error") else ""))
                return {"id": item["id"], **run}, rows

            print(f"核验 {len(items)} 条（同时 {args.concurrency} 条）")
            done = await asyncio.gather(*(one(i) for i in items))
            await llm.aclose()
    runs, rows = [d[0] for d in done], [r for d in done for r in d[1]]
    m = metrics(rows)
    previous = sorted(RESULTS.glob("*.json"))[-1] if RESULTS.exists() and any(RESULTS.glob("*.json")) else None
    before = json.loads(previous.read_text())["metrics"] if previous else None
    print_report(m, before)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"started": time.strftime("%Y-%m-%d %H:%M"), "drafts": args.drafts,
                               "metrics": m, "rows": rows, "runs": runs}, ensure_ascii=False, indent=2))
    print(f"\n结果：{out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
