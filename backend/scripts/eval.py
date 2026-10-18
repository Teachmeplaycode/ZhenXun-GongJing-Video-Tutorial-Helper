"""Run the fixed question set in evals/cases.json against a real backend and compare with the last run.

    uv run python scripts/eval.py                  # all cases, 2 at a time
    uv run python scripts/eval.py --only danmaku   # cases whose id contains "danmaku" (a,b: either)
    uv run python scripts/eval.py --judge          # also have the model grade answers against each rubric
    uv run python scripts/eval.py --prepare        # only parse the videos (frames + transcript) and stop

It starts its own backend on a free port with data in backend/data/evals, so the server you use is not
touched. Videos are parsed once and reused (data/evals/videos.json maps each to its session). Questions are
asked without conversation history, so they don't influence each other. A provider hiccup (busy, timeout)
gets one more try after 20 s; the result records it. Results go to
data/evals/results/<time>.json; the summary compares pass rate, time and tokens with the previous run.

Checks per case (all optional):
  tools_any     at least one of these tools was called (names as in the trace, e.g. "audience.danmaku")
  tools_all     every one of these was called
  tools_none    none of these was called
  contains_any  list of groups; each group: at least one of its strings is in the answer
  contains_none none of these strings is in the answer
  timestamps    the answer cites at least one time like [01:23] or 01:23 (true) or none at all (false)
  rubric        what a good answer does; graded 0–2 by the model with --judge (2 passes)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.schema import CATEGORIES, QTYPES, load  # noqa: E402

CASES = ROOT / "evals" / "cases.json"
DATA = ROOT / "data" / "evals"
VIDEOS = DATA / "videos.json"
RESULTS = DATA / "results"
TIME_RE = re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?![\d:])")  # the chat links [01:23] and bare 01:23 alike
TRANSIENT = ("busy", "timeout", "network", "upstream", "empty", "http")  # provider hiccups: asked again once
# Steps every answer has; they say nothing about the model's choices.
ROUTINE = ("frames.select", "transcript.read", "decision.research_intent", "vision.")


# ---- the backend under test ---------------------------------------------------------------------
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Backend:
    """A backend of its own on a free port; `env` overrides settings (GONGJING_DATA_DIR defaults to data/evals)."""

    def __init__(self, env: dict | None = None):
        self.extra = env or {}
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc = None

    def __enter__(self):
        env = {**os.environ, "GONGJING_DATA_DIR": str(DATA), **self.extra}
        data = Path(env["GONGJING_DATA_DIR"])
        data.mkdir(parents=True, exist_ok=True)
        self.log = (data / "server.log").open("w")
        self.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", str(self.port)],
                                     cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(60):
            try:
                if httpx.get(f"{self.base}/api/health", timeout=1).status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            if self.proc.poll() is not None:
                break
            time.sleep(0.5)
        self.__exit__()
        raise SystemExit(f"后端没有启动，见 {data / 'server.log'}")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.log.close()


# ---- videos ------------------------------------------------------------------------------------
async def prepare(client: httpx.AsyncClient, videos: dict[str, dict]) -> dict[str, str]:
    """video key → job id, parsing what isn't cached yet; waits until frames and transcript are done."""
    cache = json.loads(VIDEOS.read_text()) if VIDEOS.exists() else {}
    started: dict[str, str] = {}
    for key, spec in videos.items():  # start every missing video first; they parse in parallel
        job_id = cache.get(key, {}).get("job_id") if cache.get(key, {}).get("url") == spec["url"] else None
        if job_id and (await client.get(f"/api/sessions/{job_id}")).status_code != 200:
            job_id = None
        if job_id is None:
            r = await client.post("/api/link-jobs", json={"url": spec["url"]}, timeout=120)
            if r.status_code != 200:
                print(f"  ✗ {key}: {r.json().get('message', r.text)}")
                continue
            job_id = r.json()["job_id"]
            print(f"  · {key}: 解析中（{r.json()['video']['title'][:30]}）")
        started[key] = job_id
    for key, job_id in started.items():  # parsed before a step existed (on-screen text): fill it in
        snap = (await client.get(f"/api/link-jobs/{job_id}")).json()
        if (snap.get("screentext") or {}).get("status") == "failed" or (snap.get("transcript") or {}).get("status") == "failed":
            r = await client.post(f"/api/link-jobs/{job_id}/retry", timeout=120)
            if r.status_code == 200:
                print(f"  · {key}: 补上缺的步骤（画面文字 {r.json().get('screentext')} · 语音 {r.json().get('transcript')}）")
    ids = {}
    for key, job_id in started.items():
        for _ in range(240):
            snap = (await client.get(f"/api/link-jobs/{job_id}")).json()
            if not snap["running"] and all((snap.get(k) or {}).get("status") not in ("running", "pending") for k in ("transcript", "screentext")):
                break
            await asyncio.sleep(5)
        cov = snap["coverage"]
        print(f"  ✓ {key}: {cov['ok']}/{cov['total']} 帧 · 转写 {(snap.get('transcript') or {}).get('status')}"
              f" · 画面文字 {(snap.get('screentext') or {}).get('status')} {(snap.get('screentext') or {}).get('count', '')}")
        ids[key] = job_id
        cache[key] = {"url": videos[key]["url"], "job_id": job_id, "title": snap["video"]["title"]}
        VIDEOS.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return ids


# ---- asking ------------------------------------------------------------------------------------
async def ask(client: httpx.AsyncClient, job_id: str, case: dict) -> dict:
    body = {"video_id": job_id, "question": case["question"], "history": False,
            "web": case.get("web", True), "papers": case.get("papers", True),
            "scope": {"type": "frames", "frames": case["frames"]} if case.get("frames") else {"type": "all"}}
    text, tools, final, started = [], [], {}, time.perf_counter()
    try:
        async with client.stream("POST", "/api/agent/runs", json=body, timeout=600) as r:
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                e = json.loads(line[5:])
                if e["type"] == "assistant.message.delta":
                    text.append(e["delta"])
                elif e["type"] == "tool_call.started" and not e["tool_name"].startswith(ROUTINE):
                    tools.append({"name": e["tool_name"]})
                elif e["type"] == "tool_call.input" and tools and e["call_id"].startswith(("tool", "zoom")):
                    tools[-1]["args"] = (e.get("input") or {}).get("params")
                elif e["type"] in ("run.completed", "run.error"):
                    final = e
    except httpx.HTTPError as exc:
        final = {"type": "run.error", "code": "http", "message": str(exc)}
    usage = final.get("usage") or {}
    return {"answer": "".join(text), "tools": tools, "status": "done" if final.get("type") == "run.completed" else "error",
            "error": final.get("message") if final.get("type") != "run.completed" else None, "code": final.get("code"),
            "seconds": round(time.perf_counter() - started, 1), "prompt_tokens": usage.get("prompt"),
            "completion_tokens": usage.get("completion"), "model": final.get("model")}


def check(case: dict, run: dict) -> list[str]:
    """Failed checks, as short reasons (empty: passed)."""
    if run["status"] != "done":
        return [f"出错：{run['error']}"]
    c, answer = case.get("checks", {}), run["answer"]
    flat = re.sub(r"\s+", "", answer).lower()  # "9 块 9" matches "9块9"
    has = lambda s: re.sub(r"\s+", "", s).lower() in flat  # noqa: E731
    called = {t["name"] for t in run["tools"]}
    fails = []
    if c.get("tools_any") and not called & set(c["tools_any"]):
        fails.append(f"没有调用 {' / '.join(c['tools_any'])}")
    for name in c.get("tools_all", []):
        if name not in called:
            fails.append(f"没有调用 {name}")
    for name in c.get("tools_none", []):
        if name in called:
            fails.append(f"不该调用 {name}")
    for group in c.get("contains_any", []):
        if not any(has(s) for s in group):
            fails.append(f"回答里没有「{' / '.join(group)}」")
    for s in c.get("contains_none", []):
        if has(s):
            fails.append(f"回答里不该出现「{s}」")
    if c.get("timestamps") is True and not TIME_RE.search(answer):
        fails.append("没有引用时间点")
    if c.get("timestamps") is False and TIME_RE.search(answer):
        fails.append("不该引用时间点")
    return fails


JUDGE = """你是评测员。根据评分标准给一个视频问答系统的回答打分，只输出 JSON：{"score": 0 到 2 的整数, "reason": "一句话理由"}。
2 = 满足标准的全部要点；1 = 部分满足或有小错；0 = 没有满足、答非所问或有明显编造。
标准里的时间点是大概位置：回答里的时间点相差 5 秒以内算对。回答比标准多出的内容，只要不和视频矛盾、不是编造，就不扣分。

问题：{question}
评分标准：{rubric}
回答：
{answer}"""


async def judge(llm, case: dict, run: dict) -> dict | None:
    from modules.llm import Usage

    if not case.get("rubric") or run["status"] != "done":
        return None
    prompt = JUDGE.replace("{question}", case["question"]).replace("{rubric}", case["rubric"]).replace("{answer}", run["answer"][:6000])
    try:
        text = "".join([d async for d in llm.stream([{"role": "user", "content": prompt}], Usage(), max_tokens=200)])
    except Exception as exc:  # the grader being unreachable must not lose the whole run
        return {"score": None, "reason": f"未评分：{exc}"}
    match = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(match.group(0)) if match else {"score": 0, "reason": f"无法解析：{text[:80]}"}
    except json.JSONDecodeError:
        return {"score": 0, "reason": f"无法解析：{text[:80]}"}


# ---- report -------------------------------------------------------------------------------------
def summary(results: list[dict]) -> dict:
    n = len(results) or 1
    tokens = [r["prompt_tokens"] or 0 for r in results]
    graded = [r["judge"]["score"] for r in results if r.get("judge") and r["judge"].get("score") is not None]
    return {"cases": len(results), "passed": sum(r["passed"] for r in results),
            "avg_seconds": round(sum(r["seconds"] for r in results) / n, 1),
            "avg_prompt_k": round(sum(tokens) / n / 1000, 1),
            "judge_avg": round(sum(graded) / len(graded), 2) if graded else None}


def previous() -> dict | None:
    runs = sorted(RESULTS.glob("*.json"))
    return json.loads(runs[-1].read_text()) if runs else None


def print_matrix(results: list[dict]) -> None:
    """按类别 × 题型打印通过率矩阵（Issue #7）。没有 category/qtype 的旧结果会跳过。"""
    if not any(r.get("category") and r.get("qtype") for r in results):
        return
    cats = list(CATEGORIES)
    qts = list(QTYPES)
    cells = {(c, q): [0, 0] for c in cats for q in qts}  # [passed, total]
    cat_tot = {c: [0, 0] for c in cats}
    qt_tot = {q: [0, 0] for q in qts}
    for r in results:
        c, q = r.get("category"), r.get("qtype")
        if c not in CATEGORIES or q not in QTYPES:
            continue
        cells[(c, q)][1] += 1
        cat_tot[c][1] += 1
        qt_tot[q][1] += 1
        if r["passed"]:
            cells[(c, q)][0] += 1
            cat_tot[c][0] += 1
            qt_tot[q][0] += 1

    def cell(p, n):
        return f"{p}/{n}" if n else "·"

    print(f"\n{'类别 × 题型通过率':}")
    header = f"{'':<10}" + "".join(f"{QTYPES[q]:<8}" for q in qts) + "合计"
    print(header)
    for c in cats:
        row = f"{CATEGORIES[c]:<10}" + "".join(f"{cell(*cells[(c, q)]):<8}" for q in qts) + cell(*cat_tot[c])
        print(row)
    print(f"{'合计':<10}" + "".join(f"{cell(*qt_tot[q]):<8}" for q in qts)
          + cell(sum(p for p, _ in qt_tot.values()), sum(n for _, n in qt_tot.values())))


def print_report(results: list[dict], before: dict | None) -> None:
    print(f"\n{'':2}{'用例':<26}{'结果':<6}{'耗时':>7}{'输入k':>7}  说明")
    old = {r["id"]: r for r in (before or {}).get("results", [])}
    for r in results:
        mark = "✓" if r["passed"] else "✗"
        was = old.get(r["id"])
        change = "" if not was or was["passed"] == r["passed"] else ("（新通过）" if r["passed"] else "（退步）")
        note = "；".join(r["fails"]) or (f"评分 {r['judge']['score']}：{r['judge']['reason']}" if r.get("judge") else "")
        k = f"{(r['prompt_tokens'] or 0) / 1000:.0f}"
        print(f"{mark:2}{r['id']:<26}{'通过' if r['passed'] else '失败':<6}{r['seconds']:>6.0f}s{k:>7}  {change}{note}"[:220])
    s = summary(results)
    line = f"\n通过 {s['passed']}/{s['cases']} · 平均 {s['avg_seconds']}s · 平均输入 {s['avg_prompt_k']}k tokens"
    if s["judge_avg"] is not None:
        line += f" · 评分均值 {s['judge_avg']}/2"
    print(line)
    if before:
        b = before["summary"]
        same = {r["id"] for r in results} == {r["id"] for r in before["results"]}
        print(f"上次（{before['started']}{'' if same else '，用例不同'}）：通过 {b['passed']}/{b['cases']} · 平均 {b['avg_seconds']}s · "
              f"平均输入 {b['avg_prompt_k']}k" + (f" · 评分均值 {b['judge_avg']}/2" if b.get("judge_avg") is not None else ""))
    print_matrix(results)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="only cases whose id contains this (comma-separated: any of them)")
    parser.add_argument("--judge", action="store_true", help="grade answers against each rubric with the model")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--prepare", action="store_true", help="only parse the videos")
    args = parser.parse_args()

    spec = load(CASES)
    wanted = [w.strip() for w in (args.only or "").split(",") if w.strip()]
    cases = [c for c in spec["cases"] if not wanted or any(w in c["id"] for w in wanted)]
    needed = {c["video"] for c in cases}
    videos = {k: v for k, v in spec["videos"].items() if k in needed or args.prepare}
    before = previous()
    with Backend() as backend:
        async with httpx.AsyncClient(base_url=backend.base, timeout=60) as client:
            print(f"准备 {len(videos)} 个视频")
            ids = await prepare(client, videos)
            if args.prepare:
                return
            llm = None
            if args.judge:
                from modules.llm import LLMConfig, create_client
                llm = create_client(LLMConfig.from_env())
            print(f"运行 {len(cases)} 个用例（同时 {args.concurrency} 个）")
            gate = asyncio.Semaphore(args.concurrency)

            async def one(case):
                if case["video"] not in ids:
                    return {"id": case["id"], "passed": False, "fails": ["视频没有解析成功"], "seconds": 0, "prompt_tokens": 0,
                            "answer": "", "tools": [], "status": "error"}
                async with gate:
                    run = await ask(client, ids[case["video"]], case)
                    if run["status"] == "error" and run.get("code") in TRANSIENT:
                        await asyncio.sleep(20)
                        first = run["error"]
                        run = await ask(client, ids[case["video"]], case)
                        run["retried"] = first
                fails = check(case, run)
                verdict = await judge(llm, case, run) if llm else None
                if verdict and verdict.get("score") is not None and verdict["score"] < 2:
                    fails.append(f"评分 {verdict.get('score')}：{verdict.get('reason', '')}")
                print(f"  {'✓' if not fails else '✗'} {case['id']}")
                return {"id": case["id"], "question": case["question"], **run, "fails": fails, "passed": not fails, "judge": verdict}

            results = await asyncio.gather(*(one(c) for c in cases))
            for case, result in zip(cases, results):
                result["category"] = spec["videos"].get(case["video"], {}).get("category")
                result["qtype"] = case.get("qtype")
            if llm:
                await llm.aclose()
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%d %H:%M")
    record = {"started": started, "only": args.only, "judge": args.judge, "summary": summary(results), "results": results}
    path = RESULTS / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print_report(results, before)
    print(f"\n完整结果：{path.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
