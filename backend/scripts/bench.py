"""Run a slice of MotionBench (fine-grained motion, multiple choice) through the agent under different setups.

    uv run python scripts/bench.py --config A       # 16 uniform frames, no tools
    uv run python scripts/bench.py --config A48     # 48 uniform frames, no tools (does density alone help?)
    uv run python scripts/bench.py --config B       # 16 frames + the agent's tools (close look, slow-motion replay)
    uv run python scripts/bench.py --config C       # B + perception instruments (measure_motion)
    uv run python scripts/bench.py --report         # compare the latest run of every config

MotionBench (Hong et al., CVPR 2025; zai-org/MotionBench on Hugging Face, CC-BY-NC-SA-4.0, academic use only)
has six question types. Its dev split carries answers; this samples `--n` questions per type with a fixed
seed, downloads only those clips into data/bench/motionbench/videos, uploads each once to a backend of its
own (data/bench/server, uploads kept so replay can read them) and asks every question without history,
web or papers. Answers end with "答案：X"; accuracy is reported per type with a 95% interval.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eval import Backend  # noqa: E402

BENCH = ROOT / "data" / "bench"
META = BENCH / "motionbench" / "video_info.meta.jsonl"
FILES = BENCH / "motionbench" / "files.json"
VIDEOS = BENCH / "motionbench" / "videos"
SERVER = BENCH / "server"
UPLOADS = SERVER / "uploads.json"
RESULTS = BENCH / "results"
HF = "https://huggingface.co/datasets/zai-org/MotionBench"

CONFIGS = {  # D adds the experience file (scripts/experience.py) on top of C
    "A": {"LLM_MAX_IMAGES": "16", "LLM_TOOLS": "off"},
    "A48": {"LLM_MAX_IMAGES": "48", "LLM_TOOLS": "off"},
    "B": {"LLM_MAX_IMAGES": "16", "LLM_TOOLS": "on", "INSTRUMENTS": "off"},
    "C": {"LLM_MAX_IMAGES": "16", "LLM_TOOLS": "on", "INSTRUMENTS": "on"},
    "D": {"LLM_MAX_IMAGES": "16", "LLM_TOOLS": "on", "INSTRUMENTS": "on", "EXPERIENCE_FILE": str(BENCH / "experience.json")},
}
COMMON = {"LLM_WEB": "off", "BROWSER": "off", "KEEP_UPLOADS": "on", "GONGJING_DATA_DIR": str(SERVER)}
# Benchmarks score an abstention as wrong; the app's prompt says "say you're unsure", so ask for a pick here
# (the first runs of A abstained on 11 of 204, B on 1 — worth keeping in mind as a signal of its own).
SUFFIX = ("\n\n这是一道单选题，请根据视频画面作答。即使不确定，也必须选出最可能的一项（可以先说明不确定的原因）。"
          "回答的最后单独一行写：答案：X（X 是选项字母）。")
ANSWER_RE = re.compile(r"答案\s*[:：]\s*\**\s*([A-F])")


TEST_N, TEST_SEED = 100, 0  # the held-out questions every reported comparison uses


def sample(n: int, seed: int, exclude: set[str] | None = None) -> list[dict]:
    rows = [json.loads(line) for line in META.read_text().splitlines()]
    dev = [r for r in rows if r["qa"] and r["qa"][0]["answer"] != "NA" and r["qa"][0]["uid"] not in (exclude or set())]
    by_type = defaultdict(list)
    for r in dev:
        by_type[r["question_type"]].append(r)
    rng = random.Random(seed)
    picked = []
    for kind in sorted(by_type):
        picked += rng.sample(sorted(by_type[kind], key=lambda r: r["qa"][0]["uid"]), min(n, len(by_type[kind])))
    return [{"uid": r["qa"][0]["uid"], "type": r["question_type"], "video": r["video_path"], "duration": r["video_info"]["duration"],
             "question": r["qa"][0]["question"], "answer": r["qa"][0]["answer"]} for r in picked]


async def video_file(client: httpx.AsyncClient, name: str) -> Path:
    """The clip on disk, downloaded on first use (its folder in the repo is looked up once)."""
    path = VIDEOS / name
    if path.is_file():
        return path
    if not FILES.exists():
        info = (await client.get(f"https://huggingface.co/api/datasets/zai-org/MotionBench", timeout=60)).json()
        FILES.write_text(json.dumps({s["rfilename"].rsplit("/", 1)[-1]: s["rfilename"] for s in info["siblings"]}))
    where = json.loads(FILES.read_text())[name]
    VIDEOS.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):  # the connection to Hugging Face fails now and then (SSL errors, resets)
        try:
            r = await client.get(f"{HF}/resolve/main/{where}", timeout=120, follow_redirects=True)
            r.raise_for_status()
            path.write_bytes(r.content)
            return path
        except httpx.HTTPError:
            if attempt == 2:
                raise
            await asyncio.sleep(5 * (attempt + 1))
    return path


async def download_all(items: list[dict]) -> set[str]:
    """Every clip on disk before the run starts; returns the ones that couldn't be fetched."""
    gate, failed = asyncio.Semaphore(4), set()
    async with httpx.AsyncClient() as hub:
        async def one(name):
            async with gate:
                try:
                    await video_file(hub, name)
                except (httpx.HTTPError, KeyError) as exc:
                    failed.add(name)
                    print(f"  ✗ 下载失败 {name}: {type(exc).__name__}")
        await asyncio.gather(*(one(n) for n in sorted({i["video"] for i in items})))
    return failed


async def upload(api: httpx.AsyncClient, hub: httpx.AsyncClient, item: dict, jobs: dict, uploads: Path = UPLOADS) -> str | None:
    if item["video"] in jobs and (await api.get(f"/api/sessions/{jobs[item['video']]}")).status_code == 200:
        return jobs[item["video"]]
    path = await video_file(hub, item["video"])
    r = await api.post("/api/videos", files={"file": (item["video"], path.read_bytes(), "video/mp4")}, timeout=120)
    if r.status_code != 200:
        print(f"  ✗ 上传失败 {item['video']}: {r.text[:120]}")
        return None
    job_id = r.json()["job_id"]
    for _ in range(120):
        snap = (await api.get(f"/api/link-jobs/{job_id}")).json()
        if not snap["running"] and all((snap.get(k) or {}).get("status") not in ("running", "pending") for k in ("transcript", "screentext")):
            break
        await asyncio.sleep(1)
    jobs[item["video"]] = job_id
    uploads.write_text(json.dumps(jobs, indent=1))
    return job_id


def training(n: int, seed: int) -> list[dict]:
    """Questions for gathering experience: never any of the held-out test questions."""
    return sample(n, seed, exclude={i["uid"] for i in sample(TEST_N, TEST_SEED)})


async def ask(api: httpx.AsyncClient, job_id: str, question: str) -> dict:
    body = {"video_id": job_id, "question": question + SUFFIX, "history": False, "web": False, "papers": False, "scope": {"type": "all"}}
    text, tools, final, started = [], [], {}, time.perf_counter()
    trace: dict[str, dict] = {}  # call id → {tool, args, output}: what the agent looked at and read
    try:
        async with api.stream("POST", "/api/agent/runs", json=body, timeout=600) as r:
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                e = json.loads(line[5:])
                if e["type"] == "assistant.message.delta":
                    text.append(e["delta"])
                elif e["type"] == "tool_call.started" and e["call_id"].startswith(("tool", "zoom")):
                    tools.append(e["tool_name"])
                    trace[e["call_id"]] = {"tool": e["tool_name"]}
                elif e["type"] == "tool_call.input" and e["call_id"] in trace:
                    trace[e["call_id"]]["args"] = (e.get("input") or {}).get("params")
                elif e["type"] == "tool_call.output" and e["call_id"] in trace:
                    trace[e["call_id"]]["output"] = (e.get("stdout") or "")[:1200]
                elif e["type"] in ("run.completed", "run.error"):
                    final = e
    except httpx.HTTPError as exc:
        final = {"type": "run.error", "message": str(exc)}
    answer = "".join(text)
    found = ANSWER_RE.findall(answer)
    usage = final.get("usage") or {}
    return {"reply": answer, "choice": found[-1] if found else None, "tools": tools, "trace": list(trace.values()), "ok": final.get("type") == "run.completed",
            "error": final.get("message") if final.get("type") != "run.completed" else None,
            "seconds": round(time.perf_counter() - started, 1), "prompt_tokens": usage.get("prompt") or 0}


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z, p = 1.96, k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def table(results: list[dict]) -> dict:
    by = defaultdict(list)
    for r in results:
        by[r["type"]].append(r)
    by["全部"] = results
    out = {}
    for kind, rs in by.items():
        k = sum(r["correct"] for r in rs)
        out[kind] = {"n": len(rs), "correct": k, "acc": k / len(rs) if rs else 0, "ci": wilson(k, len(rs)),
                     "tokens": sum(r["prompt_tokens"] for r in rs) / max(1, len(rs)),
                     "seconds": sum(r["seconds"] for r in rs) / max(1, len(rs)),
                     "tool_use": sum(bool(r["tools"]) for r in rs) / max(1, len(rs)),
                     "unparsed": sum(r["choice"] is None for r in rs)}
    return out


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Paired comparison on the same questions: (only a right, only b right, two-sided exact p)."""
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    n, k = only_a + only_b, min(only_a, only_b)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return only_a, only_b, p


def report(folder: Path = RESULTS) -> None:
    """Every config's runs in `folder`: accuracy per type (first run), repeats, and paired tests."""
    runs = defaultdict(list)
    for path in sorted(folder.glob("*.json")):
        run = json.loads(path.read_text())
        if run.get("split", "test") == "test":
            runs[run["config"]].append(run)
    if not runs:
        print(f"{folder} 里还没有测试结果。")
        return
    configs = [c for c in CONFIGS if c in runs]
    first = {c: runs[c][0] for c in configs}
    kinds = sorted({k for run in first.values() for k in run["table"] if k != "全部"}) + ["全部"]
    print(f"{'题型':<26}" + "".join(f"{c:>18}" for c in configs))
    for kind in kinds:
        cells = []
        for c in configs:
            t = first[c]["table"].get(kind)
            cells.append(f"{t['acc'] * 100:5.1f}% ({t['correct']}/{t['n']})" if t else "")
        print(f"{kind:<26}" + "".join(f"{x:>18}" for x in cells))
    for label, key, fmt in (("平均输入 token", "tokens", "{:.0f}"), ("平均用时 s", "seconds", "{:.1f}"), ("调用了工具的比例", "tool_use", "{:.0%}")):
        print(f"{label:<24}" + "".join(f"{fmt.format(first[c]['table']['全部'][key]):>18}" for c in configs))
    for c in configs:
        lo, hi = first[c]["table"]["全部"]["ci"]
        print(f"{c}: 总正确率 95% 区间 {lo * 100:.1f}%–{hi * 100:.1f}%（{first[c]['started']}，{first[c]['table']['全部']['unparsed']} 题没读出答案）")
        if len(runs[c]) > 1:
            accs = [f"{r['table']['全部']['acc'] * 100:.1f}%" for r in runs[c]]
            a, b = runs[c][0], runs[c][1]
            ra = {r["uid"]: r["correct"] for r in a["results"]}
            rb = {r["uid"]: r["correct"] for r in b["results"]}
            common = sorted(set(ra) & set(rb))
            oa, ob, p = mcnemar([ra[u] for u in common], [rb[u] for u in common])
            print(f"   重复运行 {len(runs[c])} 次：{' / '.join(accs)}；两次之间结果不同的题 {oa + ob} 道（p = {p:.2f}）—— 这是随机噪声的大小")
    print("\n配对比较（同一批题上，一方答对、另一方答错的题数；p < 0.05 才算显著，比较多组时要更严）：")
    right = {c: {r["uid"]: r["correct"] for r in first[c]["results"]} for c in configs}
    for i, a in enumerate(configs):
        for b in configs[i + 1:]:
            common = sorted(set(right[a]) & set(right[b]))
            oa, ob, p = mcnemar([right[a][u] for u in common], [right[b][u] for u in common])
            print(f"  {a} vs {b}：只有 {a} 对 {oa} 题，只有 {b} 对 {ob} 题，p = {p:.3f}{' 显著' if p < 0.05 else ''}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", choices=sorted(CONFIGS))
    parser.add_argument("--n", type=int, default=34, help="questions per type")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--report", nargs="?", const=str(RESULTS), help="compare the runs in a results folder")
    parser.add_argument("--train", action="store_true", help="gather experience: questions outside the held-out test set")
    parser.add_argument("--tag", default="", help="suffix for the result file and the backend folder (parallel runs)")
    args = parser.parse_args()
    if args.report or not args.config:
        return report(Path(args.report) if args.report else RESULTS)

    items = training(args.n, args.seed) if args.train else sample(args.n, args.seed)
    split = "训练（不含测试题）" if args.train else "测试"
    print(f"MotionBench 开发集 · {split}：{len(items)} 题（每类 {args.n}，seed {args.seed}），配置 {args.config} {CONFIGS[args.config]}")
    failed = await download_all(items)
    print(f"视频下载：{len({i['video'] for i in items}) - len(failed)} 个可用，{len(failed)} 个失败")
    server = SERVER.with_name(f"server-{args.tag}") if args.tag else SERVER
    uploads = server / "uploads.json"
    jobs = json.loads(uploads.read_text()) if uploads.exists() else {}
    server.mkdir(parents=True, exist_ok=True)
    with Backend(env={**COMMON, **CONFIGS[args.config], "GONGJING_DATA_DIR": str(server)}) as backend:
        async with httpx.AsyncClient(base_url=backend.base, timeout=60) as api, httpx.AsyncClient() as hub:
            gate = asyncio.Semaphore(args.concurrency)

            async def prepare(item):
                if item["video"] in failed:
                    return None
                async with gate:
                    try:
                        return await upload(api, hub, item, jobs, uploads)
                    except httpx.HTTPError as exc:
                        print(f"  ✗ 上传失败 {item['video']}: {type(exc).__name__}")
                        return None

            ids = await asyncio.gather(*(prepare(i) for i in items))
            print(f"视频就绪：{sum(1 for i in ids if i)}/{len(items)}")
            done = 0

            async def one(item, job_id):
                nonlocal done
                if job_id is None:
                    return {**item, "choice": None, "correct": False, "ok": False, "error": "上传失败", "tools": [], "seconds": 0, "prompt_tokens": 0}
                async with gate:
                    r = await ask(api, job_id, item["question"])
                    if not r["ok"] and r["error"] and any(w in r["error"] for w in ("繁忙", "超时", "无法连接")):
                        await asyncio.sleep(20)
                        r = await ask(api, job_id, item["question"])
                done += 1
                if done % 20 == 0:
                    print(f"  {done}/{len(items)}")
                return {**item, **r, "correct": r["choice"] == item["answer"]}

            results = await asyncio.gather(*(one(i, j) for i, j in zip(items, ids)))
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%d %H:%M")
    run = {"config": args.config, "env": CONFIGS[args.config], "n": args.n, "seed": args.seed, "started": started,
           "split": "train" if args.train else "test", "tag": args.tag,
           "table": table(results), "results": results}
    folder = RESULTS / "train" if args.train else RESULTS
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{args.config}{'-' + args.tag if args.tag else ''}.json"
    (folder / name).write_text(json.dumps(run, ensure_ascii=False, indent=1))
    if args.train:
        t = run["table"]["全部"]
        print(f"训练集 {args.config}：{t['acc'] * 100:.1f}%（{t['correct']}/{t['n']}），结果 {folder / name}")
    else:
        report()


if __name__ == "__main__":
    asyncio.run(main())
