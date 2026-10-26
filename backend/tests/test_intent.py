"""Question kinds decided before the agent starts, and what each changes."""
import asyncio
import json

import httpx
import pytest

from modules.agent import intent
from modules.agent.run import run_agent
from modules.llm import ChatClient, LLMConfig
from tests.test_tools import make_job, sse


@pytest.fixture(autouse=True)
def no_main_model_fallback(monkeypatch):
    """These tests predate the main-model fallback; keep them on the keyword/decider paths."""
    monkeypatch.setenv("INTENT_LLM_FALLBACK", "off")

QUESTIONS = [  # (question, kind) — the keyword fallback must get these right
    ("视频里第几秒点了哪个按钮，把数据透视表改成了表格形式？", "tutorial"),
    ("为什么我照着做到这一步就报错了", "tutorial"),
    ("这个视频说得对吗", "science"),
    ("帮我把这个视频的说法都核查一遍", "science"),
    ("85 种药物这个说法可靠吗？帮我上网核实一下", "verify"),
    ("这是不是骗局", "fraud"),
    ("他让加微信领资料，会不会被骗", "fraud"),
    ("视频主要讲了什么", "content"),
]


@pytest.mark.parametrize("question,kind", QUESTIONS)
def test_keywords_decide_without_the_decision_model(question, kind):
    got = asyncio.run(intent.classify(question, None))
    assert (got.kind, got.how, got.p) == (kind, "关键词", None)


class Decider:
    def __init__(self, probs):
        self.probs = probs

    async def choice(self, state, instructions, criteria, *, task=""):
        assert set(criteria) == set(intent.CRITERIA) and task == "intent"
        from modules.decide.client import Decision
        return Decision(self.probs, "fake", 1.0)


def test_the_decision_model_decides_and_an_unsure_decision_changes_nothing():
    sure = asyncio.run(intent.classify("这个说得对吗", Decider({"science": 0.8, "verify": 0.1, "content": 0.1})))
    assert (sure.kind, sure.p, sure.skill, sure.how) == ("science", 0.8, "check_science", "决策模型")
    unsure = asyncio.run(intent.classify("嗯", Decider({"tutorial": 0.4, "content": 0.35, "chat": 0.25})))
    assert unsure.kind == "tutorial" and unsure.skill is None and unsure.note == ""

    class Broken:
        async def choice(self, *a, **k):
            raise RuntimeError("ollama is not running")
    assert asyncio.run(intent.classify("这是不是骗局", Broken())).how == "关键词"


def test_a_tutorial_question_is_answered_step_by_step(tmp_path):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "01:24 点了「报表布局」。"}, "finish_reason": "stop"}]}))
    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))

    async def go():
        return [e async for e in run_agent(make_job(tmp_path), client, "第几秒点了哪个按钮")]
    events = asyncio.run(go())
    route = next(e for e in events if e.get("call_id") == "route" and e["type"] == "tool_call.output")
    assert route["data"]["kind"] == "tutorial" and route["stdout"].startswith("过程拆解（关键词")
    assert seen[0]["messages"][-1]["content"].startswith("（回答方式）这是过程拆解类问题")


def test_a_fraud_question_runs_the_skill_first_and_the_model_answers_from_it(tmp_path, monkeypatch):
    from modules.agent import skills, tools
    from modules.agent.tools import ToolResult

    async def fake_run(name, job, llm, web=True, papers=True, **kwargs):
        yield {"type": "progress.update", "step": "反诈识别：查话术"}
        yield ("result", "反诈识别完成：综合风险高。", "风险高", 1, {"skill": "antifraud", "report": {"summary": "x"}}, False)
    monkeypatch.setattr(skills, "run", fake_run)
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "风险高 [推断]。"}, "finish_reason": "stop"}]}))
    client = ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "k"), transport=httpx.MockTransport(handler))

    async def go():
        return [e async for e in run_agent(make_job(tmp_path), client, "这是不是骗局")]
    events = asyncio.run(go())
    started = [e["tool_name"] for e in events if e["type"] == "tool_call.started"]
    assert "skill.antifraud" in started and "decision.research_intent" not in started
    first = seen[0]["messages"]
    assert first[-2]["tool_calls"][0]["function"]["name"] == "check_fraud" and first[-1]["content"] == "反诈识别完成：综合风险高。"
    assert len(seen) == 1  # answered from the skill, no further rounds forced


def test_summaries_and_reports_are_about_the_video_not_small_talk():
    # 2026-10-26: the composer's own 「整理关键片段并写成分析报告」 was routed as unrelated and refused
    from modules.agent import intent
    for q in ("整理关键片段并写成分析报告", "总结这段视频的主要内容", "帮我梳理一下知识点", "写一份学习笔记"):
        assert intent.by_keywords(q).kind == "content", q


def test_a_model_calling_a_report_unrelated_is_overruled():
    import asyncio
    from modules.agent import intent

    class Decider:
        async def choice(self, state, question, criteria, task=""):
            from types import SimpleNamespace
            return SimpleNamespace(choice="chat", probabilities={"chat": 0.8, "content": 0.2})
    got = asyncio.run(intent.classify("整理关键片段并写成分析报告", Decider()))
    assert got.kind == "content" and "改为视频内容" in got.how


def test_route_context_keeps_only_the_latest_three_turns_and_selection():
    history = [message for i in range(4) for message in (
        {"role": "user", "content": f"第{i}轮问题"}, {"role": "assistant", "content": f"第{i}轮回答"})]
    context = intent.context_for("动画 PV", description="无对白", history=history,
                                 selected_times=[12.5, 18], ranges=[(10, 20)])
    assert "动画 PV" in context and "无对白" in context
    assert "第0轮" not in context and all(f"第{i}轮" in context for i in (1, 2, 3))
    assert "12.5、18" in context and "10–20" in context
    assert len(intent.context_for("长" * 1000, description="长" * 10000,
                                 history=[{"role": "user", "content": "长" * 10000}] * 50)) <= intent.CONTEXT_CHARS


@pytest.mark.parametrize("command", ["科普核查", "反诈识别", "论文", "卡点"])
def test_historical_canonical_commands_are_described_rather_than_reissued(command):
    from modules.agent.commands import INSTRUCTIONS, compose_question
    context = intent.context_for("PV", history=[
        {"role": "user", "content": compose_question(command, "只看开头")},
        {"role": "assistant", "content": "此前任务已完成。"}])
    assert f"此前所选任务 /{command}" in context and "当时补充：只看开头" in context
    assert INSTRUCTIONS[command] not in context and "此前任务已完成" in context


@pytest.mark.parametrize("historical_kind", ["science", "fraud"])
@pytest.mark.parametrize("question", ["这个分镜的构图为什么这样？", "总结开场的画面内容", "介绍一下这个人物"])
def test_clear_content_questions_do_not_inherit_historical_skill_requests(historical_kind, question):
    class Decider:
        async def choice(self, *args, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(choice=historical_kind, probabilities={historical_kind: 0.9})
    got = asyncio.run(intent.classify(question, Decider(), context="上一轮选择科普核查或反诈识别"))
    assert got.kind == "content" and got.skill is None


@pytest.mark.parametrize("kind,skill", [("science", "check_science"), ("fraud", "check_fraud")])
def test_genuine_claim_or_risk_followups_keep_the_classified_skill(kind, skill):
    class Decider:
        async def choice(self, *args, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(choice=kind, probabilities={kind: 0.9})
    explicit = "核查这个分镜中说的健康观点" if kind == "science" else "总结这个视频是否有诈骗风险"
    for question in ("那第二个说法呢？", explicit):
        got = asyncio.run(intent.classify(question, Decider(), context="刚在逐条核查视频说法"))
        assert got.kind == kind and got.skill == skill


@pytest.mark.parametrize("question,chosen,expected", [
    ("这个分镜为什么这样切？", "chat", "content"),
    ("第几秒这个镜头从全景切到近景？", "tutorial", "content"),
    ("这个镜头的步骤和画面节奏怎么衔接？", "tutorial", "content"),
    ("Blender 里这个镜头的参数怎么设置？", "tutorial", "tutorial"),
    ("这道例题的推导步骤是什么？", "tutorial", "tutorial"),
    ("为什么这样？", "chat", "content"),
    ("现在换个话题，帮我写一首秋天的诗", "chat", "chat"),
    ("这个城市今天的天气怎么样？", "chat", "chat"),
])
def test_current_question_controls_the_task_with_recent_context(question, chosen, expected):
    states = []
    class Decider:
        async def choice(self, state, instructions, criteria, *, task=""):
            from types import SimpleNamespace
            states.append(state)
            return SimpleNamespace(choice=chosen, probabilities={chosen: 0.9})
    context = intent.context_for("示例 PV", history=[
        {"role": "user", "content": "先讲开场分镜"}, {"role": "assistant", "content": "远景建立空间。"}])
    got = asyncio.run(intent.classify(question, Decider(), context=context))
    assert got.kind == expected
    assert len(states) == 1 and question in states[0] and "先讲开场分镜" in states[0] and "示例 PV" in states[0]
    assert "当前问题改变话题时跟随新问题" in states[0]


def test_reference_correction_needs_context_and_does_not_force_tools():
    class Decider:
        async def choice(self, *args, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(choice="chat", probabilities={"chat": 0.9})
    standalone = asyncio.run(intent.classify("为什么这样？", Decider()))
    assert standalone.kind == "chat"
    followup = asyncio.run(intent.classify("为什么这样？", Decider(), context="用户刚问镜头构图"))
    assert followup.kind == "content" and followup.skill is None


@pytest.mark.parametrize("selection", ["frames", "range"])
def test_actual_run_passes_title_recent_discussion_and_selection_once(tmp_path, monkeypatch, selection):
    from modules.agent import run
    from modules.agent.tools import ToolResult
    monkeypatch.setenv("LLM_TOOLS", "off")
    monkeypatch.setattr(run.experience, "kinds", lambda: [])
    captured, calls = [], []
    async def classify(question, decider, *, context):
        captured.append((question, context))
        return intent.Intent("content", None, {}, "test")
    async def replay(self, name, args):
        assert name == "replay"
        return ToolResult("已读取所选片段", "已读取", 1)
    monkeypatch.setattr(intent, "classify", classify)
    monkeypatch.setattr(run.AgentTools, "run", replay)
    class Client:
        config = type("Config", (), {"model": "test"})()
        async def stream(self, messages, usage, **kwargs):
            calls.append(messages)
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, "stop"
            yield "低角度使人物显得更有压迫感。"
    job = make_job(tmp_path)
    job.video.title = "动画 PV"
    history = [message for i in range(4) for message in (
        {"role": "user", "content": f"问题{i}：分析这个分镜"},
        {"role": "assistant", "content": f"回答{i}：使用低角度。"})]
    options = {"frames": [1]} if selection == "frames" else {"framed": [(10, 20)]}
    async def go():
        return [e async for e in run.run_agent(job, Client(), "这段为什么用低角度？", history=history, **options)]
    events = asyncio.run(go())
    assert len(captured) == 1 and len(calls) == 1
    context = captured[0][1]
    assert "动画 PV" in context and "问题0" not in context and "问题3" in context
    assert (f"用户选中画面（秒）：{job.slots[1].time:g}" if selection == "frames" else "10–20") in context
    assert events[-1]["type"] == "run.completed"


def test_visual_question_can_answer_from_frames_without_speech_or_ocr(tmp_path, monkeypatch):
    from modules.agent import run
    from modules.transcript import Transcript
    monkeypatch.setenv("LLM_TOOLS", "off")
    monkeypatch.setattr(run.experience, "kinds", lambda: [])
    calls = []
    class Client:
        config = type("Config", (), {"model": "test"})()
        async def stream(self, messages, usage, **kwargs):
            calls.append(messages)
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, "stop"
            yield "这个镜头采用低角度构图。[画面 01:15]"
    job = make_job(tmp_path)
    job.video.title, job.transcript, job.screentext = "无对白 PV", Transcript("empty"), None
    async def go():
        return [e async for e in run.run_agent(job, Client(), "拆解这个分镜的构图与表达")]
    events = asyncio.run(go())
    assert len(calls) == 1 and any(p["type"] == "image_url" for p in calls[0][1]["content"])
    assert not any(e.get("tool_name") == "data.wait" for e in events)
    assert "低角度构图" in "".join(e["delta"] for e in events if e["type"] == "assistant.message.delta")
    route = next(e for e in events if e["type"] == "tool_call.output" and e.get("call_id") == "route")
    assert route["data"]["kind"] == "content" and events[-1]["type"] == "run.completed"


@pytest.mark.parametrize("kind,command", [("science", "科普核查"), ("fraud", "反诈识别")])
def test_actual_run_does_not_repeat_a_historical_skill_for_new_shot_analysis(tmp_path, monkeypatch, kind, command):
    from modules.agent import run
    from modules.agent.commands import compose_question
    monkeypatch.setattr(run.experience, "kinds", lambda: [])
    class Decider:
        async def choice(self, *args, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(choice=kind, probabilities={kind: 0.9})
    async def no_skill(self, name, args):
        raise AssertionError('new shot analysis must not rerun an earlier skill')
        yield
    monkeypatch.setattr(run.AgentTools, 'stream', no_skill)
    class Client:
        config = type("Config", (), {"model": "test"})()
        async def stream(self, messages, usage, **kwargs):
            usage.prompt_tokens, usage.completion_tokens, usage.finish_reason = 100, 10, "stop"
            yield "这一镜采用低角度构图。"
    history = [{"role": "user", "content": compose_question(command, "逐条查看")},
               {"role": "assistant", "content": "上个任务已完成。"}]
    async def go():
        return [e async for e in run.run_agent(make_job(tmp_path), Client(), "分析这个分镜的构图", history=history, decider=Decider())]
    events = asyncio.run(go())
    assert not any(str(e.get('tool_name', '')).startswith('skill.') for e in events)
    assert events[-1]['type'] == 'run.completed'
