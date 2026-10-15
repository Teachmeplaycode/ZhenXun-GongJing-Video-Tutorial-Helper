"""Run the link dataset in ../datas against the live resolvers (needs network).

    uv run python scripts/check_links.py [--frames N] [--only CASE_ID] [--platform bilibili] [--record]

--record writes each frame run into the case's `observed` block (cases that already have one are
kept unless --overwrite is given).

Exit code 1 when any case disagrees with its `expect` block.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.frames import FrameJob  # noqa: E402
from modules.video_source import ResolveError, default_registry  # noqa: E402

DATAS = ROOT.parent / "datas"
STRICT = ("video_id", "part", "part_count")
SOFT = ("title", "author")


def load_cases(platform: str | None, only: str | None) -> tuple[list[tuple[str, dict]], dict[Path, dict]]:
    """Cases to run, plus the parsed files so --record can write observations back."""
    cases, files = [], {}
    for path in sorted(DATAS.glob("*/links.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if platform and data.get("platform") != platform:
            continue
        files[path] = data
        cases += [(data["platform"], c) for c in data["cases"] if not only or c["id"] == only]
    return cases, files


def compare(expect: dict, video) -> tuple[list[str], list[str]]:
    actual = {
        "video_id": video.video_id, "part": video.part, "part_count": len(video.parts),
        "duration": video.duration, "title": video.title, "author": video.author,
    }
    errors = [f"{k}: 期望 {expect[k]!r}，实际 {actual[k]!r}" for k in STRICT if k in expect and expect[k] != actual[k]]
    if "duration" in expect and abs(expect["duration"] - actual["duration"]) > 1:
        errors.append(f"duration: 期望 {expect['duration']}，实际 {actual['duration']}")
    warnings = [f"{k} 已变化：{actual[k]!r}" for k in SOFT if k in expect and expect[k] != actual[k]]
    return errors, warnings


async def run(args) -> int:
    registry = default_registry()
    failures = 0
    cases, files = load_cases(args.platform, args.only)
    recorded = 0
    if not cases:
        print("没有匹配的用例")
        return 1
    try:
        for platform, case in cases:
            expect = case["expect"]
            started = time.monotonic()
            try:
                resolver, video = await registry.resolve(case["input"])
            except ResolveError as exc:
                elapsed = time.monotonic() - started
                if expect.get("ok") is False and exc.code == expect.get("code"):
                    print(f"PASS  {case['id']}  预期错误 {exc.code}（{elapsed:.1f}s）")
                else:
                    failures += 1
                    print(f"FAIL  {case['id']}  {exc.code}: {exc.message}")
                continue
            elapsed = time.monotonic() - started
            if expect.get("ok") is False:
                failures += 1
                print(f"FAIL  {case['id']}  期望错误 {expect.get('code')}，实际解析成功")
                continue
            errors, warnings = compare(expect, video)
            line = f"{'FAIL' if errors else 'PASS'}  {case['id']}  {video.video_id} P{video.part} {video.duration:.0f}s · {len(video.streams)} 个地址（{elapsed:.1f}s）"
            if args.frames and not errors:
                with tempfile.TemporaryDirectory() as tmp:
                    job = FrameJob(case["id"], video, resolver, Path(tmp), count=args.frames)
                    t = time.monotonic()
                    await job.run()
                    cov = job.coverage()
                    total_sec = round(time.monotonic() - t, 1)
                    line += f" · 抽帧 {cov['ok']}/{cov['total']}（{total_sec}s）"
                    if cov["missing"]:
                        line += f" 缺失 {cov['missing_ranges']} {cov['reasons']}"
                    if args.record and (args.overwrite or "observed" not in case):
                        case["observed"] = {"date": date.today().isoformat(), "frames_ok": cov["ok"],
                                            "frames_total": cov["total"], "total_sec": total_sec,
                                            **({"missing_ranges": cov["missing_ranges"], "reasons": cov["reasons"]} if cov["missing"] else {})}
                        recorded += 1
            print(line)
            for message in errors:
                print(f"      × {message}")
            for message in warnings:
                print(f"      ! {message}")
            failures += bool(errors)
    finally:
        await registry.aclose()
        if recorded:
            for path, data in files.items():
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"已写入 {recorded} 条实测记录")
    print(f"\n{len(cases) - failures}/{len(cases)} 通过")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="用 datas/ 下的链接数据集验证解析器")
    parser.add_argument("--frames", type=int, default=0, help="每条成功用例额外抽取的帧数（0 表示只解析）")
    parser.add_argument("--only", help="只运行指定 id 的用例")
    parser.add_argument("--platform", help="只运行指定平台")
    parser.add_argument("--record", action="store_true", help="把抽帧实测结果写回数据集的 observed")
    parser.add_argument("--overwrite", action="store_true", help="与 --record 一起使用时覆盖已有的 observed")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
