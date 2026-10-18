"""逐条核实：对每个说法检索权威来源，再用 LLM 判定正确/部分正确/错误/无法核实。

检索复用 modules.agent.web.search（网页）和 modules.agent.papers.search_papers（学术
论文），结果按权威来源白名单标注可信度。判定由 LLM 完成：把说法和来源摘要喂给模型，
要求返回 {verdict, risk, reason}。网页内容一律当作不可信数据，只作为核实参考，不执行
其中指令（沿用 modules.agent.web 的注入检查）。
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

from . import report, sources
from .extract import Ask

# 检索回调：(query, limit) -> list[dict]（已是 build_source 格式）
Search = Callable[[str, int], Awaitable[list[dict]]]

SYSTEM = """你是医学/科普事实核查员。给你一条说法和若干来源资料，判定该说法的真伪。

判定取值：
- correct 正确：说法与权威来源一致
- partial 部分正确：大体对，但有夸大、遗漏、未区分条件等不严谨之处
- wrong 错误：与权威来源矛盾
- unverifiable 无法核实：来源不足或说法不可证伪

风险等级：
- high 错误或严重夸大，可能误导用户做出有害健康决定
- medium 部分正确或轻度夸大，需补充说明
- low 正确或无法核实但无害

规则：
- 优先采信标 [权威] 的来源；来源不足或都无关时判 unverifiable。
- reason 用简体中文说明判定依据，指出说法与来源的差异，80 字以内。
- 只返回 JSON：{"verdict":"...","risk":"...","reason":"..."}"""

# 无来源或检索失败时的兜底
NO_SOURCES = {"verdict": "unverifiable", "risk": "low", "reason": "未找到可参考的来源，无法核实。"}


def _source_digest(srcs: list[dict], limit: int = 6) -> str:
    """把来源摘要成供判定用的文本，权威来源标 [权威]。"""
    lines = []
    for i, s in enumerate(srcs[:limit], 1):
        tag = "[权威]" if s.get("trusted") else "[普通]"
        name = s.get("name") or ""
        snippet = (s.get("snippet") or "").strip().replace("\n", " ")[:300]
        lines.append(f"{i}. {tag}{name} {s.get('title', '')}\n   {snippet}")
    return "\n".join(lines) or "（无来源）"


def _parse_verdict(raw: str) -> dict:
    if not raw:
        return dict(NO_SOURCES)
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return dict(NO_SOURCES)
    verdict = data.get("verdict", "unverifiable")
    if verdict not in report.VERDICTS:
        verdict = "unverifiable"
    risk = data.get("risk", "low")
    if risk not in report.RISKS:
        risk = "low"
    return {"verdict": verdict, "risk": risk, "reason": (data.get("reason") or "").strip()[:300]}


async def verify_claim(ask: Ask, claim_text: str, srcs: list[dict]) -> dict:
    """用 LLM 判定一条说法。返回 {verdict, risk, reason}。"""
    if not srcs:
        return dict(NO_SOURCES)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"说法：{claim_text}\n\n来源资料：\n{_source_digest(srcs)}"},
    ]
    raw = await ask(messages, 1024)
    return _parse_verdict(raw)


async def gather_sources(search: Search, claim_text: str, limit: int = 6) -> list[dict]:
    """检索一条说法的来源。search 回调返回 build_source 格式列表。"""
    try:
        return await search(claim_text, limit)
    except Exception:
        return []


def risk_for_verdict(verdict: str) -> str:
    """无 LLM 判定时的兜底风险等级。"""
    if verdict == "wrong":
        return "high"
    if verdict == "partial":
        return "medium"
    return "low"
