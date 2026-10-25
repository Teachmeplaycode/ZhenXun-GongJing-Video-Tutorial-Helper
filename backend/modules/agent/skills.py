"""Skills: whole analyses the agent can decide to run as one step of an answer.

A skill is a tool too, but a heavy one: it runs one of the project's own analysis modules over the
whole video and returns a report. The agent picks it when the question calls for it ("这个说法对吗",
"是不是骗局"); the composer's quick tasks ask for it by name. While it runs, its progress shows as
the step's status; when it ends, the model gets a short digest to answer from (verdicts, moments,
links, so its answer can cite them) and the page shows the full report as the step's result.

  check_science  科普核查  modules/factcheck: claims extracted from speech and on-screen text,
                           each checked against authoritative web pages and papers
  copy_result    抄作业    modules/recipe: a node tutorial's finished graph (nodes, settings, links),
                           with other versions' differences from the comments, to copy at once
  check_fraud    反诈识别  modules/antifraud: scam phrasing, contact details and QR codes for
                           drawing people off-platform, institution records, a model's overall view

Their reports are the same as before; the separate side-panel tabs that ran them are gone.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..frames import FrameJob


@dataclass
class Skill:
    name: str
    title: str
    trace: str          # step name in the answer's trace
    description: str    # for the model: what it does and when to use it
    needs_web: bool = False


SKILLS = [
    Skill("check_science", "科普核查", "skill.factcheck",
          "科普核查技能：把视频里关于健康、医学、营养、科学的说法逐条抽出来，联网查权威网页和论文，给出每条"
          "「正确 / 部分正确 / 错误 / 无法核实」的判定、风险和出处。用户问「说得对吗」「靠谱吗」「有没有科学依据」"
          "「帮我核查/辟谣」或要求科普核查时用。要跑一两分钟；问的只是某一句话时，用 web_search 更快。", needs_web=True),
    Skill("copy_result", "抄作业", "skill.recipe",
          "抄作业技能：把节点类教程（Blender 几何节点/着色器节点、ComfyUI 工作流、UE 蓝图等）最终做出来的节点图完整整理出来："
          "每个节点、改过的参数、每条连线，再按评论区和弹幕补上不同版本的做法，标出看不清要回看的地方。"
          "用户要「最终的节点图/连接图/所有参数」「直接给我答案抄」「照着连总是错」时用。要跑半分钟到一分钟。"),
    Skill("check_fraud", "反诈识别", "skill.antifraud",
          "反诈识别技能：检查视频里的诈骗风险：高收益承诺、冒充机构、制造紧迫感等话术，微信号、电话、网址、二维码"
          "等引流方式，提到的机构有没有公开登记，再给出综合风险判断。用户问「是不是骗局」「能不能信」「有没有风险」"
          "「会不会被骗」或要求反诈识别时用。"),
]
BY_NAME = {s.name: s for s in SKILLS}
TRACE = {s.name: s.trace for s in SKILLS}
VERDICT = {"correct": "正确", "partial": "部分正确", "wrong": "错误", "unverifiable": "无法核实"}
RISK = {"high": "高", "medium": "中", "low": "低"}


def definitions(web: bool = True) -> list[dict]:
    from modules import recipe
    return [{"type": "function", "function": {
        "name": s.name, "description": s.description,
        "parameters": {"type": "object", "properties": {}, "required": []}}}
        for s in SKILLS if (web or not s.needs_web) and (s.name != "copy_result" or recipe.enabled())]


def clock(seconds) -> str:
    t = max(0, int(seconds or 0))
    return f"{t // 60:02d}:{t % 60:02d}"


def science_digest(report: dict) -> str:
    """The fact-check report as the model reads it: each claim with its verdict, moment and sources."""
    claims = report.get("claims") or []
    if not claims:
        return f"科普核查完成：{report.get('message') or '没有抽出可核实的说法'}。"
    lines = [f"科普核查完成，共 {len(claims)} 条说法（判定来自检索到的资料，引用资料时用 [资料 链接]）："]
    for i, c in enumerate(claims, 1):
        when = (c.get("timestamp") or {}).get("start")
        source = "原声" if (c.get("evidence") or {}).get("source") == "transcript" else "画面文字"
        lines.append(f"{i}. [{source} {clock(when)}] {c.get('claim', '')} —— {VERDICT.get(c.get('verdict'), '无法核实')}"
                     f"，风险{RISK.get(c.get('risk'), '低')}：{c.get('reason', '')}")
        for s in (c.get("sources") or [])[:3]:
            if s.get("url"):
                lines.append(f"   出处：{s.get('name') or s.get('title', '')} {s['url']}")
    return "\n".join(lines)


def fraud_digest(report: dict) -> str:
    score, assessment = report.get("score") or {}, report.get("assessment") or {}
    risk = RISK.get(assessment.get("risk") or score.get("level"), "未知")
    lines = [f"反诈识别完成：综合风险{risk}。{report.get('summary', '')}"]
    if assessment.get("reason"):
        lines.append(f"模型判断：{assessment['reason']}")
    for c in (report.get("claims") or [])[:12]:
        stamp = c.get("timestamp") or {}
        when = f"[{'原声' if (c.get('evidence') or {}).get('source') == 'transcript' else '画面文字'} {clock(stamp.get('start'))}] " \
            if stamp.get("end") else ""
        lines.append(f"- {when}{c.get('claim', '')}（{c.get('verdict_label') or c.get('verdict', '')}，风险{c.get('risk_label', '')}）"
                     f"：{c.get('reason', '')}")
    if report.get("limitations"):
        lines.append("局限：" + "；".join(str(x) for x in report["limitations"][:3]))
    return "\n".join(lines)


async def run(name: str, job: FrameJob, llm, *, web: bool = True, papers: bool = True, grab=None, viewers=None) -> AsyncIterator[dict | tuple]:
    """Progress events ({"type": "progress.update", ...}) while the skill runs, then one
    ("result", text, summary, count, data, error) tuple for the caller to turn into a ToolResult."""
    if name == "check_science":
        from modules.factcheck.run import run_factcheck
        report, error, done, total = None, "", 0, 0
        async for event in run_factcheck(job, llm, web=web, papers=papers):
            kind = event.get("type")
            if kind == "factcheck.claims_extracted":
                total = event.get("count", 0)
                yield {"type": "progress.update", "step": f"科普核查：抽出 {total} 条说法，逐条查资料"}
            elif kind == "factcheck.claim.verifying":
                yield {"type": "progress.update", "step": f"科普核查 {done + 1}/{total or '?'}：{str(event.get('claim', ''))[:30]}"}
            elif kind == "factcheck.claim.done":
                done += 1
            elif kind == "factcheck.completed":
                report = event.get("report") or {}
            elif kind == "factcheck.error":
                error = event.get("message") or "核查失败"
        if report is None:
            yield ("result", f"科普核查没有完成：{error}", error or "未完成", 0, None, True)
            return
        summary = report.get("summary") or {}
        brief = f"{summary.get('total', 0)} 条说法 · 错误 {summary.get('wrong', 0)} · 部分正确 {summary.get('partial', 0)}"
        yield ("result", science_digest(report), brief, summary.get("total", 0), {"skill": "factcheck", "report": report}, False)
    elif name == "copy_result":
        from modules import recipe

        async def keyframes_only(t, path, width):
            return False
        async for item in recipe.run(job, llm, grab or keyframes_only, viewers):
            yield item
    elif name == "check_fraud":
        from modules.antifraud.review import analyze_reviewed
        yield {"type": "progress.update", "step": "反诈识别：查话术、引流方式、二维码和机构登记"}
        try:
            report = (await analyze_reviewed(job, client=llm, job_id=job.id)).as_dict()
        except Exception as exc:  # noqa: BLE001 — reported to the model, not raised
            yield ("result", f"反诈识别没有完成：{type(exc).__name__}", "未完成", 0, None, True)
            return
        level = (report.get("assessment") or {}).get("risk") or (report.get("score") or {}).get("level")
        brief = f"风险{RISK.get(level, '未知')} · 线索 {len(report.get('rule_hits') or []) + len(report.get('drainage_signals') or [])} 条"
        yield ("result", fraud_digest(report), brief, len(report.get("claims") or []), {"skill": "antifraud", "report": report}, False)
    else:
        yield ("result", f"没有名为 {name} 的技能", "未知技能", 0, None, True)
