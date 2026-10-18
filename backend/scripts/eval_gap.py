"""评测集缺口清单（Issue #7）：当前规模 vs 目标 ≥30 视频 / ≥150 题 / 每类 ≥5 视频。

只读 evals/cases.json 做统计，不运行模型、不编造内容。
视频和题目的 category/qtype 归属是基于现有 note/question/rubric 的推断，
其中一部分归属勉强，已在 TENTATIVE_VIDEOS / TENTATIVE_QTYPES 列出，需人工确认。

    uv run python scripts/eval_gap.py          # 人类可读
    uv run python scripts/eval_gap.py --json   # 结构化（供测试/CI）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.schema import (  # noqa: E402
    CATEGORIES, QTYPES, TARGET_VIDEOS, TARGET_CASES, TARGET_PER_CATEGORY, load,
)

CASES = ROOT / "evals" / "cases.json"

# 现有视频里 category 归属勉强的（不属于典型 6 类，需人工确认）
TENTATIVE_VIDEOS = {
    "av2": "东方同人音乐+插画，考古向，归 vlog 勉强",
    "short": "AI 短剧，归 vlog 勉强",
    "long-ev": "去新县城体验+卖咖啡，归 vlog 勉强",
    "long-fashion": "时尚行业访谈，归 news_review 勉强",
}

# 现有题目里 qtype 归属勉强的（问的是口播/字幕内容细节，归 visual_detail 按字面是视觉的）
TENTATIVE_QTYPES = {
    "digital-battery": "问口播数值，归 visual_detail 勉强",
    "digital-charging": "问口播内容，归 visual_detail 勉强",
    "digital-chip": "问口播内容，归 visual_detail 勉强",
    "short-retire-wait": "问口播数值，归 visual_detail 勉强",
    "tech-project": "问项目地址（简介），归 visual_detail 勉强",
    "hard-ev-county": "问口播地名，归 visual_detail 勉强",
}


def gap_report(spec: dict) -> dict:
    """返回结构化缺口数据。"""
    videos = spec["videos"]
    cases = spec["cases"]
    by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    for v in videos.values():
        cat = v.get("category")
        if cat in by_cat:
            by_cat[cat] += 1
    by_qt: dict[str, int] = {q: 0 for q in QTYPES}
    for c in cases:
        qt = c.get("qtype")
        if qt in by_qt:
            by_qt[qt] += 1
    cases_per_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    for c in cases:
        vid = c.get("video")
        cat = videos.get(vid, {}).get("category")
        if cat in cases_per_cat:
            cases_per_cat[cat] += 1

    return {
        "videos": len(videos),
        "videos_target": TARGET_VIDEOS,
        "videos_short": max(0, TARGET_VIDEOS - len(videos)),
        "cases": len(cases),
        "cases_target": TARGET_CASES,
        "cases_short": max(0, TARGET_CASES - len(cases)),
        "videos_per_category": by_cat,
        "videos_per_category_target": TARGET_PER_CATEGORY,
        "categories_below_target": [c for c in CATEGORIES if by_cat[c] < TARGET_PER_CATEGORY],
        "cases_per_category": cases_per_cat,
        "cases_per_qtype": by_qt,
        "tentative_video_categories": TENTATIVE_VIDEOS,
        "tentative_qtypes": TENTATIVE_QTYPES,
        "meets_target": len(videos) >= TARGET_VIDEOS and len(cases) >= TARGET_CASES
                        and all(by_cat[c] >= TARGET_PER_CATEGORY for c in CATEGORIES),
    }


def print_gap(spec: dict) -> None:
    g = gap_report(spec)
    print(f"评测集缺口清单（Issue #7）")
    print(f"  视频：{g['videos']}/{g['videos_target']}（还差 {g['videos_short']}）")
    print(f"  题目：{g['cases']}/{g['cases_target']}（还差 {g['cases_short']}）")
    print(f"\n每类视频数（目标每类 ≥{g['videos_per_category_target']}）：")
    for c in CATEGORIES:
        n = g["videos_per_category"][c]
        mark = "✓" if n >= g["videos_per_category_target"] else "✗"
        print(f"  {mark} {CATEGORIES[c]:<8} {n}/{g['videos_per_category_target']}（题目 {g['cases_per_category'][c]}）")
    print(f"\n每题型题数：")
    for q in QTYPES:
        print(f"  {QTYPES[q]:<8} {g['cases_per_qtype'][q]}")
    print(f"\n不达标的类别：{g['categories_below_target'] or '无'}")
    print(f"是否达标：{'是' if g['meets_target'] else '否（需人工补充视频和题目）'}")
    if g["tentative_video_categories"]:
        print(f"\n待人工确认的视频类别归属（{len(g['tentative_video_categories'])}）：")
        for k, why in g["tentative_video_categories"].items():
            print(f"  · {k}：{why}")
    if g["tentative_qtypes"]:
        print(f"\n待人工确认的题目题型归属（{len(g['tentative_qtypes'])}，其余题目 qtype 同为推断）：")
        for k, why in g["tentative_qtypes"].items():
            print(f"  · {k}：{why}")
    print(f"\n注：现有视频/题目由 agent 标注 category/qtype，视频和标准答案仍需人工确认（Issue #7 协作约定）。")


def main() -> None:
    parser = argparse.ArgumentParser(description="评测集缺口清单")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = parser.parse_args()
    spec = load(CASES)
    if args.json:
        print(json.dumps(gap_report(spec), ensure_ascii=False, indent=2))
    else:
        print_gap(spec)


if __name__ == "__main__":
    main()
