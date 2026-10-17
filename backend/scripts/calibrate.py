"""Learn how far the instruments can be trusted, from practice questions with known answers — no model calls.

    uv run python scripts/calibrate.py [--limit 0] [--out data/bench/calibration.json]

Runs measure_motion's analysis offline on every MotionBench camera-motion and repetition-count question in
the training pool (never the test or validation questions) and counts what the right answer was for each
reading: for the camera, the answers given each reading ("轻微晃动" → shake 45%, still 30% …); for counts, how
the true count relates to the number of motion peaks (median ratio and its spread). The table goes into a
JSON file that measure_motion reads (CALIBRATION_FILE) and quotes next to each reading. More practice
questions → a better table: experience as numbers that can be checked, not advice that can be misapplied.
Readings are cached in data/bench/readings.jsonl, so a rerun only measures new questions.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from bench import BENCH, TEST_N, TEST_SEED, sample, video_file  # noqa: E402
from modules.frames import instruments  # noqa: E402
from modules.frames.instruments import reading_labels  # noqa: E402
from modules.video_source import Stream  # noqa: E402

READINGS = BENCH / "readings.jsonl"
CAMERA_LABELS = ("static", "shake", "left", "right", "up", "down", "in", "out")
NAMES = {"static": "静止", "shake": "晃动", "left": "向左", "right": "向右", "up": "向上", "down": "向下", "in": "推近", "out": "拉远"}


def camera_labels(text: str) -> set[str]:
    """What an option says the camera does (MotionBench options are English)."""
    t = text.lower()
    out = set()
    if re.search(r"still|static|stationary|steady|fixed|no (camera )?movement|does not move|remains", t):
        out.add("static")
    if re.search(r"shak|jitter|wobbl|trembl|handheld", t):
        out.add("shake")
    if re.search(r"pan\w* (to the )?left|moves? (to the )?left|shifts? (to the )?left|turns? left|right to left", t):
        out.add("left")
    if re.search(r"pan\w* (to the )?right|moves? (to the )?right|shifts? (to the )?right|turns? right|left to right", t):
        out.add("right")
    if re.search(r"tilt\w* up|upward|moves? up|pans? up|rais", t):
        out.add("up")
    if re.search(r"tilt\w* down|downward|moves? down|pans? down|lower", t):
        out.add("down")
    if re.search(r"zoom\w* in|push\w* in|closer|moves? (closer|forward|toward)|dolly in|approach", t):
        out.add("in")
    if re.search(r"zoom\w* out|pull\w* (out|back)|farther|wider|moves? (back|away)", t):
        out.add("out")
    return out


def pool(kinds: set[str]) -> list[dict]:
    """Every dev question of these types outside the test and validation sets."""
    from bench import validation
    held = {i["uid"] for i in sample(TEST_N, TEST_SEED)} | {i["uid"] for i in validation(60, 31)}
    return [i for i in sample(10_000, 0) if i["type"] in kinds and i["uid"] not in held]


async def measure(items: list[dict]) -> dict[str, dict]:
    cached = {}
    if READINGS.exists():
        for line in READINGS.read_text().splitlines():
            r = json.loads(line)
            cached[r["uid"]] = r
    todo = [i for i in items if i["uid"] not in cached]
    print(f"{len(items)} 道练习题，{len(cached)} 道已有读数，需要测 {len(todo)} 道")
    sem = asyncio.Semaphore(4)
    work = BENCH / "readings-work"
    async with httpx.AsyncClient() as hub:
        async def one(item):
            async with sem:
                try:
                    path = await video_file(hub, item["video"])
                except (httpx.HTTPError, KeyError):
                    return None
                d = item["duration"]
                fps = min(instruments.MAX_FPS, instruments.MAX_FRAMES / max(0.5, min(d, instruments.MAX_SPAN)))
                folder = work / item["uid"]
                files = await instruments.decode(Stream(str(path), {}, "file"), 0, min(d, instruments.MAX_SPAN), fps, folder)
                if len(files) < 3:
                    return None
                r = await asyncio.to_thread(instruments.analyze, files, 0.0, fps, folder / "out")
                for f in folder.rglob("*"):
                    if f.is_file():
                        f.unlink()
                row = {"uid": item["uid"], "camera": r.camera, "peaks": len(r.peaks), "period": r.period,
                       "span": round(r.end - r.start, 2)}
                with READINGS.open("a") as out:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                cached[item["uid"]] = row
                return row

        done = 0
        for chunk in range(0, len(todo), 40):
            await asyncio.gather(*(one(i) for i in todo[chunk:chunk + 40]))
            done += len(todo[chunk:chunk + 40])
            print(f"  {done}/{len(todo)}")
    return cached


def camera_table(items: list[dict], readings: dict) -> dict:
    by_reading: dict[str, Counter] = defaultdict(Counter)
    total = Counter()
    for it in items:
        if it["type"] != "Camera Motion" or it["uid"] not in readings:
            continue
        options = dict(re.findall(r"^([A-F])\. (.*)$", it["question"], re.M))
        truth = camera_labels(options.get(it["answer"], ""))
        if not truth:
            continue  # the right option isn't about one of the labels (e.g. "follows the cyclist")
        got = reading_labels(readings[it["uid"]]["camera"]) or {"unknown"}
        key = "+".join(sorted(got))
        total[key] += 1
        for label in truth:
            by_reading[key][label] += 1
    table = {}
    for key, n in total.items():
        if n < 5:
            continue  # too few to say anything
        table[key] = {"n": n, "truth": {label: round(c / n, 2) for label, c in by_reading[key].most_common()}}
    agree = sum(by_reading[k][label] for k in table for label in k.split("+") if label in by_reading[k])
    return {"n": sum(total.values()), "readings": table,
            "agreement": round(agree / max(1, sum(t["n"] for t in table.values())), 2)}


def count_table(items: list[dict], readings: dict) -> dict:
    ratios, hits = [], Counter()
    for it in items:
        if it["type"] != "Repetition Count" or it["uid"] not in readings:
            continue
        options = {k: int(v) for k, v in re.findall(r"^([A-F])\. (\d+)\s*$", it["question"], re.M)}
        peaks = readings[it["uid"]]["peaks"]
        if it["answer"] not in options or peaks < 2:
            continue
        truth = options[it["answer"]]
        ratios.append(truth / peaks)
        hits["n"] += 1
        for name, factor in (("half", 0.5), ("raw", 1.0)):
            pick = min(options, key=lambda k: abs(options[k] - peaks * factor))
            hits[name] += pick == it["answer"]
        hits["chance"] += 1 / len(options)
    if not ratios:
        return {}
    q = statistics.quantiles(ratios, n=4)
    median = statistics.median(ratios)
    for it in items:  # how often "peaks × median ratio" picks the right option
        if it["type"] == "Repetition Count" and it["uid"] in readings and readings[it["uid"]]["peaks"] >= 2:
            options = {k: int(v) for k, v in re.findall(r"^([A-F])\. (\d+)\s*$", it["question"], re.M)}
            if it["answer"] in options:
                pick = min(options, key=lambda k: abs(options[k] - readings[it["uid"]]["peaks"] * median))
                hits["median"] += pick == it["answer"]
    n = hits["n"]
    return {"n": n, "ratio_median": round(median, 2), "ratio_q1": round(q[0], 2), "ratio_q3": round(q[2], 2),
            "pick_with_median": round(hits["median"] / n, 2), "pick_with_half": round(hits["half"] / n, 2),
            "pick_with_peaks": round(hits["raw"] / n, 2), "chance": round(hits["chance"] / n, 2)}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="use only the first N practice questions per type (to see how the table grows)")
    parser.add_argument("--out", type=Path, default=BENCH / "calibration.json")
    args = parser.parse_args()
    items = pool({"Camera Motion", "Repetition Count"})
    if args.limit:
        by = defaultdict(list)
        for it in items:
            by[it["type"]].append(it)
        items = [it for group in by.values() for it in group[:args.limit]]
    readings = await measure(items)
    table = {"made": time.strftime("%Y-%m-%d %H:%M"), "source": "MotionBench dev, training pool (no test / validation questions)",
             "camera": camera_table(items, readings), "count": count_table(items, readings)}
    args.out.write_text(json.dumps(table, ensure_ascii=False, indent=1))
    cam, cnt = table["camera"], table["count"]
    print(f"\n镜头：{cam['n']} 道可归类的练习题，读数和答案一致约 {cam['agreement']:.0%}")
    for key, row in sorted(cam["readings"].items(), key=lambda kv: -kv[1]["n"]):
        dist = "、".join(f"{NAMES.get(k, k)} {v:.0%}" for k, v in row["truth"].items())
        print(f"  仪器说 {'+'.join(NAMES.get(k, k) for k in key.split('+'))}（{row['n']} 题）→ 正确答案：{dist}")
    if cnt:
        print(f"计数：{cnt['n']} 道练习题；真实次数 ÷ 峰值数 中位 {cnt['ratio_median']}（一半落在 {cnt['ratio_q1']}–{cnt['ratio_q3']}）")
        print(f"  按中位比例选：{cnt['pick_with_median']:.0%}；按一半选：{cnt['pick_with_half']:.0%}；直接用峰值数：{cnt['pick_with_peaks']:.0%}；随机：{cnt['chance']:.0%}")
    print(f"已写入 {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
