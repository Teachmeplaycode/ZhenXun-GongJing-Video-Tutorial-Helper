"""夸大用语检测：标出视频里绝对化、夸大疗效、恐吓式等不严谨的表述。

养生/科普视频里常见的夸大手法：把"可能""部分"说成"一定""全部"，用恐吓语气
("千万别""会致命")，或夸大疗效("包治""根治""奇迹")。核查报告对每条说法标出
这些词，帮助"子女帮父母查"的用户识别不严谨的表述。
"""
from __future__ import annotations

import re

# 绝对化用语：把概率性结论说成必然
ABSOLUTE = [
    "一定", "必定", "绝对", "百分之百", "100%", "肯定会", "必然",
    "所有人都", "每个人都会", "无一例外", "永远", "再也不",
]

# 夸大疗效 / 神化
EXAGGERATED_CURE = [
    "包治", "根治", "治愈", "断根", "药到病除", "神药", "奇迹",
    "万能", "百病", "防癌", "抗癌", "排毒", "清血管", "溶血栓",
    "提高免疫力", "增强免疫力", "彻底清除", "一招", "一个动作",
]

# 恐吓式用语
ALARMIST = [
    "千万别", "千万不要", "绝对不能", "会致命", "会死人", "会中毒",
    "会致癌", "会毁掉", "会要命", "会出大事", "后果不堪设想",
    "赶紧", "马上", "立刻", "不然就晚了", "再不知道就晚了",
]

# 模糊权威背书
VAGUE_AUTHORITY = [
    "专家说", "医生说", "研究表明", "科学家发现", "据研究", "研究发现",
    "医学界", "公认", "众所周知",
]


def _find_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        if term in text:
            found.append(term)
    return found


def detect(text: str) -> dict:
    """检测一段文字里的夸大用语。

    返回 {"detected": bool, "terms": [命中的词], "categories": [类别], "note": 说明}。
    """
    if not text:
        return {"detected": False, "terms": [], "categories": [], "note": ""}
    hits: list[tuple[str, str]] = []  # (term, category)
    for term in _find_terms(text, ABSOLUTE):
        hits.append((term, "absolute"))
    for term in _find_terms(text, EXAGGERATED_CURE):
        hits.append((term, "cure"))
    for term in _find_terms(text, ALARMIST):
        hits.append((term, "alarmist"))
    for term in _find_terms(text, VAGUE_AUTHORITY):
        hits.append((term, "vague_authority"))
    if not hits:
        return {"detected": False, "terms": [], "categories": [], "note": ""}
    # 去重保序
    seen, terms, categories = set(), [], []
    for term, cat in hits:
        if term not in seen:
            seen.add(term)
            terms.append(term)
        if cat not in categories:
            categories.append(cat)
    note = _note(categories)
    return {"detected": True, "terms": terms, "categories": categories, "note": note}


def _note(categories: list[str]) -> str:
    parts = []
    if "absolute" in categories:
        parts.append("绝对化用语")
    if "cure" in categories:
        parts.append("夸大疗效")
    if "alarmist" in categories:
        parts.append("恐吓式表述")
    if "vague_authority" in categories:
        parts.append("模糊权威背书")
    return "、".join(parts)
