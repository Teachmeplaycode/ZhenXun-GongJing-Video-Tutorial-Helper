"""The final question message when attachments meet an injected pre-look.

The pre-look injection used to move the question to the end of the message by popping its last
part — an assumption that nothing follows the question. With pictures attached the last parts are
the attachments (a label, a picture, a located note), so one of those was carried behind the
replay frames, splitting a screenshot from its label or its note. These tests run the real
run_agent against a mocked model, intercept what is actually sent, and check the grouping:

- the question appears exactly once and stays the last part;
- every screenshot label is followed by its picture, then its located note (when there is one);
- the pre-look lead is followed by the replay frames, each labelled with its time.
"""
import asyncio
import json
import re

import httpx
import pytest

import modules.agent.run as run_module
from modules.agent.locate import Match
from modules.frames import FrameJob, GrabResult
from modules.frames import replay as slowmo
from modules.agent.run import run_agent
from modules.llm import ChatClient, LLMConfig
from modules.video_source import ResolvedVideo, Stream


def make_job(tmp_path):
    v = ResolvedVideo("test", "v1", "https://x/v1", "标题", 100.0, [Stream("https://a", {}, "s")], description="简介")
    job = FrameJob("j", v, None, tmp_path, count=2)
    tmp_path.mkdir(exist_ok=True)
    for slot in job.slots:
        slot.status = "ok"
        job.frame_path(slot.index).write_bytes(b"\xff\xd8jpg")
    return job


def sse_body(*chunks):
    lines = [f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks]
    return "".join(lines) + "data: [DONE]\n\n"


def client_for(handler):
    return ChatClient(LLMConfig("https://api.deepseek.com", "deepseek-flash", "sk-test"),
                     transport=httpx.MockTransport(handler))


def collect(gen):
    async def go():
        return [e async for e in gen]
    return asyncio.run(go())


def attachments(tmp_path, n):
    paths = []
    for i in range(1, n + 1):
        p = tmp_path / f"attach{i}.jpg"
        p.write_bytes(b"\xff\xd8shot")
        paths.append(p)
    return paths


def fake_locate(which):
    """locate_shots replacement: screenshots listed in `which` (1-based) each match the first slot."""

    async def locate_shots(job, images):
        out = {}
        for i, path in enumerate(images, 1):
            if i in which:
                out[str(path)] = [Match(job.slots[0], 0.9, 0.8, 0.5, shared=["数据", "验证"])]
        return out
    return locate_shots


@pytest.fixture
def replay_grab(monkeypatch):
    calls = []

    async def grab_clip(stream, p, folder, timeout=45):
        calls.append((p.start, p.end, p.fps, p.count))
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, p.count + 1):
            (folder / f"{i:02d}.jpg").write_bytes(b"\xff\xd8replay")
        return GrabResult(True)

    monkeypatch.setattr(slowmo, "grab_clip", grab_clip)
    return calls


ATTACH_NOTE = "用户随问题附上了"
BY_HAND_LEAD = "用户提问前刚在时间轴上手动慢放了"
SLOW_LEAD = "问题要求慢放的这一段已经复看好了"


def kinds_of(parts):
    """Reduce the final user message's parts to what each one is, images by the label before them."""
    out, pending_image = [], None
    for p in parts:
        if p["type"] == "image_url":
            out.append(f"{pending_image or 'orphan'}_image")
            pending_image = None
            continue
        t = str(p.get("text", ""))
        if t.startswith("问题："):
            out.append("question")
        elif t.startswith("范围："):
            out.append("scope")
        elif t.startswith(ATTACH_NOTE):
            out.append("attach_note")
        elif re.fullmatch(r"你的截图 \d+", t):
            out.append("attach_label")
            pending_image = "attach"
        elif t.startswith("按画面文字和画面相似度自动比对"):
            out.append("located")
        elif t.startswith("复看 · "):
            out.append("zoom_label")
            pending_image = "zoom"
        elif t.startswith(BY_HAND_LEAD) or t.startswith(SLOW_LEAD):
            out.append("zoom_lead")
        else:
            out.append("other")
    return out


def expected_kinds(n_attach, located, lead_kind, n_zoom):
    seq = ["scope"]
    if n_attach:
        seq.append("attach_note")
        for i in range(1, n_attach + 1):
            seq += ["attach_label", "attach_image"]
            if i in located:
                seq.append("located")
    seq.append("zoom_lead")
    seq += ["zoom_label", "zoom_image"] * n_zoom
    seq.append("question")
    return seq


def run_case(tmp_path, monkeypatch, replay_grab, *, n_attach, located, by_hand):
    job = make_job(tmp_path / "job")
    images = attachments(tmp_path, n_attach)
    if n_attach:
        monkeypatch.setattr(run_module, "locate_shots", fake_locate(located))
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "看过了"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
        ))

    question = "这一步该怎么点？" if by_hand else "慢放 00:30 到 00:32 看他做了什么"
    events = collect(run_agent(job, client_for(handler), question,
                               framed=[(30.0, 32.0)] if by_hand else None,
                               images=images or None))
    assert events[-1]["type"] == "run.completed", events[-1]
    assert seen and seen[0]["messages"], "nothing reached the model"
    parts = seen[0]["messages"][-1]["content"]
    lead_kind = BY_HAND_LEAD if by_hand else SLOW_LEAD
    return parts, kinds_of(parts), expected_kinds(n_attach, located, lead_kind, replay_grab and 16), lead_kind


@pytest.mark.parametrize("by_hand", [True, False], ids=["hand-replay", "question-slowmo"])
def test_no_attachments_keeps_question_last(tmp_path, monkeypatch, replay_grab, by_hand):
    parts, got, want, lead = run_case(tmp_path, monkeypatch, replay_grab, n_attach=0, located=(), by_hand=by_hand)
    assert got == want


@pytest.mark.parametrize("by_hand", [True, False], ids=["hand-replay", "question-slowmo"])
def test_two_attachments_last_one_located(tmp_path, monkeypatch, replay_grab, by_hand):
    parts, got, want, lead = run_case(tmp_path, monkeypatch, replay_grab, n_attach=2, located=(1, 2), by_hand=by_hand)
    assert got == want, f"parts are: {[p.get('text', p['type'])[:30] for p in parts]}"
    assert sum(1 for p in parts if str(p.get("text", "")).startswith("问题：")) == 1


@pytest.mark.parametrize("by_hand", [True, False], ids=["hand-replay", "question-slowmo"])
def test_two_attachments_only_first_located(tmp_path, monkeypatch, replay_grab, by_hand):
    parts, got, want, lead = run_case(tmp_path, monkeypatch, replay_grab, n_attach=2, located=(1,), by_hand=by_hand)
    assert got == want, f"parts are: {[p.get('text', p['type'])[:30] for p in parts]}"
    notes = [p["text"] for p in parts if str(p.get("text", "")).startswith("按画面文字和画面相似度自动比对")]
    assert notes and "截图 1" in notes[0] and all("截图 2" not in n for n in notes)
    zoom_labels = [p["text"] for p in parts if str(p.get("text", "")).startswith("复看 · ")]
    assert len(zoom_labels) == 16 and zoom_labels[0].startswith("复看 · 00:30")
