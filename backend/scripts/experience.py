"""Distill lessons from the agent's own answers on training questions (known answers) into an experience file.

    uv run python scripts/experience.py data/bench/results/train/<run>.json [more runs…]
        [--out data/bench/experience.json] [--previous data/bench/experience-r1.json]

For each question type, the runs' records — question, options, the correct answer, what the agent chose,
which tools it called with what arguments, what they returned, how it reasoned at the end — are laid side
by side, right and wrong, and the model is asked what an agent should do differently: when to use which
tool, how to read the instruments, which misreadings recur. Lessons must rest on the records. With
--previous, the earlier lessons are revised rather than written from scratch. Never feed it test runs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.llm import LLMConfig, Usage, create_client  # noqa: E402

# Benchmark types → kinds of question an app user would ask too, so the lessons aren't MotionBench-specific.
KINDS = {
    "Camera Motion": "镜头怎么运动",
    "Repetition Count": "动作重复了几次",
    "Action Order": "动作的先后顺序",
    "Location-related Motion": "运动的方向和位置变化",
    "Motion Recognition": "在做什么动作（细微动作）",
    "Motion-related Objects": "动作涉及的物体",
}
PER_KIND = 30          # records shown per kind
MAX_LESSONS = 6

PROMPT = """你在复盘一个视频理解 agent 的答题记录。它只能看到少量静态关键帧，可以调用工具：view_frames（在一段时间里多取几帧）、replay（慢放复看几秒，每秒多帧）、measure_motion（仪器测量：镜头运动、运动强度曲线、峰值、周期、运动区域、热力图）。

问题类型：{kind}
下面是这类问题的 {n} 条记录（其中答对 {right} 条），每条包括题目、正确答案、agent 的选择、它调用的工具和读数、它最后的推理。
{previous}
请总结 3–{max} 条经验，让 agent 以后答这类问题更准。要求：
- 每条都要能从这些记录里找到支持（对比答对和答错的记录：答错时少做了什么、误读了什么；答对时做对了什么）；不要写空泛的话（如"仔细观察"）。
- 写成可以直接执行的做法：什么时候用哪个工具、取多长时间段、怎样解读仪器读数（例如峰值数和动作次数的关系、"轻微晃动"和"静止"怎么区分）、哪些常见误判要避免。
- 不要提具体某道题的内容，经验要能用到别的视频上。
- 只输出 JSON：{{"lessons": ["……", "……"]}}

记录：
{records}"""


def record(r: dict) -> str:
    calls = []
    for c in r.get("trace") or []:
        out = re.sub(r"\s+", " ", c.get("output", ""))[:300]
        calls.append(f"  · {c['tool']} {json.dumps(c.get('args') or {}, ensure_ascii=False)} → {out}")
    tail = re.sub(r"\s+", " ", r.get("reply", ""))[-260:]
    return (f"[{'对' if r['correct'] else '错'}] 题目：{r['question']}\n正确答案 {r['answer']}，agent 选 {r['choice']}\n"
            + ("工具：\n" + "\n".join(calls) if calls else "工具：没有调用") + f"\n推理结尾：{tail}")


async def distill(llm, kind: str, rows: list[dict], previous: list[str]) -> list[str]:
    rows = sorted(rows, key=lambda r: r["correct"])[:PER_KIND]  # wrong ones first: they teach the most
    prev = ("\n已有的经验（在此基础上修订：保留被记录支持的，改掉不对的，补上缺的）：\n" + "\n".join(f"- {p}" for p in previous) + "\n") if previous else ""
    prompt = PROMPT.format(kind=kind, n=len(rows), right=sum(r["correct"] for r in rows), previous=prev, max=MAX_LESSONS,
                           records="\n\n".join(record(r) for r in rows))
    text = "".join([d async for d in llm.stream([{"role": "user", "content": prompt}], Usage(), max_tokens=1500)])
    match = re.search(r"\{.*\}", text, re.S)
    try:
        lessons = json.loads(match.group(0))["lessons"] if match else []
    except (ValueError, KeyError):
        lessons = []
    return [str(x).strip() for x in lessons if str(x).strip()][:MAX_LESSONS]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "bench" / "experience.json")
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()

    rows, sources = defaultdict(list), []
    for path in args.runs:
        run = json.loads(path.read_text())
        if run.get("split") != "train":
            raise SystemExit(f"{path} 不是训练集的结果：经验只能从训练题里总结")
        sources.append(path.name)
        for r in run["results"]:
            if r.get("ok", True) and r.get("choice"):
                rows[r["type"]].append(r)
    previous = json.loads(args.previous.read_text())["lessons"] if args.previous else {}
    llm = create_client(LLMConfig.from_env())
    try:
        kinds = [k for k in KINDS if rows.get(k)]
        results = await asyncio.gather(*(distill(llm, KINDS[k], rows[k], previous.get(KINDS[k], [])) for k in kinds))
    finally:
        await llm.aclose()
    lessons = {KINDS[k]: ls for k, ls in zip(kinds, results) if ls}
    out = {"lessons": lessons, "meta": {"made": time.strftime("%Y-%m-%d %H:%M"), "from": sources,
                                         "records": {KINDS[k]: len(rows[k]) for k in kinds},
                                         "accuracy": {KINDS[k]: round(sum(r["correct"] for r in rows[k]) / len(rows[k]), 3) for k in kinds},
                                         "previous": args.previous.name if args.previous else None}}
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    for kind, ls in lessons.items():
        print(f"\n【{kind}】")
        for item in ls:
            print(f"- {item}")
    print(f"\n已写入 {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
