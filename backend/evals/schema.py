"""评测集 cases.json 的格式校验。

视频类别（6 类）和题型（5 种）是 Issue #7 的目标维度。本模块只做结构校验，
不运行模型、不编造内容；缺口统计见 scripts/eval_gap.py。

用法：
    from evals.schema import validate, CATEGORIES, QTYPES
    errors = validate(json.loads(path.read_text()))   # 空列表即合法
"""
from __future__ import annotations

import json
from pathlib import Path

CATEGORIES = {
    "lecture": "课程讲座",
    "tutorial": "软件教程",
    "news_review": "新闻测评",
    "sports": "运动",
    "vlog": "生活 vlog",
    "ad_shopping": "广告带货",
}

QTYPES = {
    "locate": "定位",
    "visual_detail": "画面细节",
    "action_count": "动作与计数",
    "summary": "总结",
    "verify": "核实",
}

TARGET_VIDEOS = 30
TARGET_CASES = 150
TARGET_PER_CATEGORY = 5

# Fields consumed by scripts/eval.py (including this module's classification metadata).
# Optional execution controls remain optional: web/papers default True; absent/empty frames mean all.
CASE_FIELDS = frozenset({"id", "video", "question", "rubric", "qtype", "checks", "frames", "web", "papers"})


def validate(spec: dict) -> list[str]:
    """返回错误列表，空表示合法。只检查结构，不检查内容真假。"""
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["顶层不是对象"]
    videos = spec.get("videos")
    cases = spec.get("cases")
    if not isinstance(videos, dict):
        errors.append("缺少 videos 对象")
        videos = {}
    if not isinstance(cases, list):
        errors.append("缺少 cases 数组")
        cases = []

    for key, v in videos.items():
        if not isinstance(key, str) or not key.strip():
            errors.append("videos 的编号应为非空字符串")
        if not isinstance(v, dict):
            errors.append(f"videos.{key} 不是对象")
            continue
        for field in ("url", "note"):
            value = v.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"videos.{key} 的 {field} 应为非空字符串")
        cat = v.get("category")
        if cat is None:
            errors.append(f"videos.{key} 缺少 category（Issue #7 要求按类别统计）")
        elif not isinstance(cat, str) or cat not in CATEGORIES:
            errors.append(f"videos.{key} 的 category={cat} 不在 {list(CATEGORIES)}")

    seen_ids: set[str] = set()
    for c in cases:
        if not isinstance(c, dict):
            errors.append("cases 里有非对象元素")
            continue
        errors.extend(f"{c.get('id') or '?'}.case 不支持字段 {key}" for key in c if key not in CASE_FIELDS)
        cid = c.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append("题目 id 应为非空字符串")
        elif cid in seen_ids:
            errors.append(f"题目 id 重复：{cid}")
        else:
            seen_ids.add(cid)
        vid = c.get("video")
        if not isinstance(vid, str) or not vid.strip():
            errors.append(f"{cid or '?'} 的 video 应为非空字符串")
        elif vid not in videos:
            errors.append(f"{cid or '?'} 引用了不存在的视频 {vid}")
        for field in ("question", "rubric"):
            value = c.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{cid or '?'} 的 {field} 应为非空字符串")
        qt = c.get("qtype")
        if qt is None:
            errors.append(f"{cid or '?'} 缺少 qtype（Issue #7 要求按题型统计）")
        elif not isinstance(qt, str) or qt not in QTYPES:
            errors.append(f"{cid or '?'} 的 qtype={qt} 不在 {list(QTYPES)}")
        if "frames" in c and (not isinstance(c["frames"], list)
                              or not all(type(frame) is int and frame >= 0 for frame in c["frames"])):
            errors.append(f"{cid or '?'} 的 frames 应为非负整数数组")
        for flag in ("web", "papers"):
            if flag in c and not isinstance(c[flag], bool):
                errors.append(f"{cid or '?'} 的 {flag} 应为布尔值")
        errors.extend(_validate_checks(cid or "?", c.get("checks", {})))
    return errors


def _validate_checks(cid: str, c: dict) -> list[str]:
    if not isinstance(c, dict):
        return [f"{cid}.checks 应为对象"]
    supported = {"tools_any", "tools_all", "tools_none", "contains_any", "contains_none", "timestamps"}
    errors: list[str] = [f"{cid}.checks 不支持字段 {key}" for key in c if key not in supported]
    for key in ("tools_any", "tools_all", "tools_none"):
        if key in c and (not isinstance(c[key], list)
                         or not all(isinstance(item, str) and item.strip() for item in c[key])):
            errors.append(f"{cid}.checks.{key} 应为字符串数组")
    if "contains_any" in c:
        if not isinstance(c["contains_any"], list):
            errors.append(f"{cid}.checks.contains_any 不是数组")
        else:
            for i, group in enumerate(c["contains_any"]):
                if (not isinstance(group, list) or not group
                        or not all(isinstance(s, str) and s.strip() for s in group)):
                    errors.append(f"{cid}.checks.contains_any[{i}] 应为非空数组，元素应为非空字符串")
    if "contains_none" in c and (not isinstance(c["contains_none"], list)
                                or not all(isinstance(item, str) and item.strip() for item in c["contains_none"])):
        errors.append(f"{cid}.checks.contains_none 应为字符串数组，元素应为非空字符串")
    if "timestamps" in c and not isinstance(c["timestamps"], bool):
        errors.append(f"{cid}.checks.timestamps 不是布尔值")
    return errors


def load(path: Path) -> dict:
    spec = json.loads(Path(path).read_text())
    errors = validate(spec)
    if errors:
        raise ValueError("cases.json 校验失败：\n  " + "\n  ".join(errors))
    return spec
