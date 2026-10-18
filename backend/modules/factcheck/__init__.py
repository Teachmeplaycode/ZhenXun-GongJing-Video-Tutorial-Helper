"""科普核查报告模块（Issue #2）。

对养生/科普类视频生成核查报告：逐条列出可核实的说法（带时间点）→ 用权威来源核实
→ 每条给出「正确 / 部分正确 / 错误 / 无法核实」和出处 → 标出夸大用语。

报告 JSON 结构定义见 report.py 的模块 docstring，该结构同时是与 Issue #3（反诈识别）
模块的共享契约。
"""
from __future__ import annotations

from .report import (
    DISCLAIMER,
    MODULE,
    VERSION,
    build_claim,
    build_report,
    build_source,
    clock,
    summarize,
)
from .run import run_factcheck
from .sources import is_trusted, kind_of, label, match

__all__ = [
    "DISCLAIMER",
    "MODULE",
    "VERSION",
    "build_claim",
    "build_report",
    "build_source",
    "clock",
    "is_trusted",
    "kind_of",
    "label",
    "match",
    "run_factcheck",
    "summarize",
]
