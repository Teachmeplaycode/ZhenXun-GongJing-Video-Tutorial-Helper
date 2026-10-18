"""反诈识别模块：话术比对、引流信息提取（含二维码）、风险等级与证据时间点。

主入口是 pipeline.analyze / pipeline.analyze_job；规则库、提取器、评分器也可单独使用。
报告结构（report.AntifraudReport）对齐暂定 schema：原始说法、证据时间点、风险等级/结论、
理由、来源、状态。#2 科普核查报告 schema 合并前，本模块保持内部边界独立可用。
"""
from . import extract, pipeline, qrcode, report, rules, score
from .pipeline import analyze, analyze_job
from .report import AntifraudReport, Evidence, Reason
from .rules import Rule, RuleHit, RuleLibrary

__all__ = [
    "analyze",
    "analyze_job",
    "AntifraudReport",
    "Evidence",
    "Reason",
    "Rule",
    "RuleHit",
    "RuleLibrary",
    "extract",
    "qrcode",
    "report",
    "rules",
    "score",
    "pipeline",
]
