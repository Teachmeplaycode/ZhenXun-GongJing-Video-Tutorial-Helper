"""Two edges the pre-look regression suite leaves for their own tests.

1. Without a pre-look the old shape stays: [scope, question, attachments...], the question
   immediately after the scope and every screenshot label next to its picture and its note.
2. Every attachment path missing plus a slow-motion question: no attachment note and no
   screenshot label is invented, and the question still ends the final user message.

Both cases run the real run_agent against a mocked HTTP transport, so no network or account
configuration is involved.
"""
import asyncio
import json
import re
from pathlib import Path

import httpx

import modules.agent.run as run_module
from modules.agent.locate import Match
from modules.agent.run import run_agent
from modules.frames import FrameJob
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


def shots(tmp_path, n):
    paths = []
    for i in range(1, n + 1):
        p = tmp_path / f"attach{i}.jpg"
        p.write_bytes(b"\xff\xd8shot")
        paths.append(p)
    return paths


def parts_kinds(parts):
    """What each part of the final user message is, images named by the label before them."""
    out, pending = [], None
    for p in parts:
        if p["type"] == "image_url":
            out.append(f"{pending or 'orphan'}_image")
            pending = None
            continue
        t = str(p.get("text", ""))
        if t.startswith("范围："):
            out.append("scope")
        elif t.startswith("问题："):
            out.append("question")
        elif t.startswith("用户随问题附上了"):
            out.append("attach_note")
        elif re.fullmatch(r"你的截图 \d+", t):
            out.append("attach_label")
            pending = "attach"
        elif t.startswith("按画面文字和画面相似度自动比对"):
            out.append("located")
        elif t.startswith("复看 · "):
            out.append("zoom_label")
            pending = "zoom"
        elif (t.startswith("用户提问前刚在时间轴上手动慢放了")
              or t.startswith("问题要求慢放的这一段已经复看好了")):
            out.append("zoom_lead")
        else:
            out.append("other")
    return out


def handler_recording(seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=sse_body(
            {"choices": [{"delta": {"content": "看过了"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
        ))
    return handler


def test_no_prelook_keeps_the_old_attachment_order(tmp_path, monkeypatch):
    """No slow-motion question and no hand replay: the pre-look branch never runs."""
    job = make_job(tmp_path / "job")
    images = shots(tmp_path, 2)

    async def locate_shots(job_, images_):
        return {str(p): [Match(job_.slots[0], 0.9, 0.8, 0.5, shared=["数据", "验证"])]
                for p in images_ if Path(p).is_file()}
    monkeypatch.setattr(run_module, "locate_shots", locate_shots)

    seen = []
    events = collect(run_agent(job, client_for(handler_recording(seen)), "这一步该怎么点？", images=images))
    assert events[-1]["type"] == "run.completed", events[-1]
    assert seen and seen[0]["messages"], "nothing reached the model"
    parts = seen[0]["messages"][-1]["content"]
    assert parts_kinds(parts) == [
        "scope", "question", "attach_note",
        "attach_label", "attach_image", "located",
        "attach_label", "attach_image", "located",
    ]
    assert parts[1]["text"] == "问题：这一步该怎么点？"
    assert sum(1 for p in parts if str(p.get("text", "")).startswith("问题：")) == 1
    assert not any(kind.startswith("zoom") for kind in parts_kinds(parts))


def test_missing_attachments_with_slowmo_add_no_attachment_note(tmp_path, monkeypatch):
    """Every attachment path is gone: attached_parts yields nothing, so the prompt must not
    claim the user attached pictures, and the question must still come last."""
    import modules.frames.replay as slowmo

    async def grab_clip(stream, p, folder, timeout=45):
        from modules.frames import GrabResult
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(1, p.count + 1):
            (folder / f"{i:02d}.jpg").write_bytes(b"\xff\xd8replay")
        return GrabResult(True)
    monkeypatch.setattr(slowmo, "grab_clip", grab_clip)

    async def no_locate(job_, images_):
        return {}
    monkeypatch.setattr(run_module, "locate_shots", no_locate)

    job = make_job(tmp_path / "job")
    missing = [tmp_path / "gone1.jpg", tmp_path / "gone2.jpg"]
    assert not any(p.is_file() for p in missing)

    seen = []
    events = collect(run_agent(job, client_for(handler_recording(seen)),
                               "慢放 00:30 到 00:32 看他做了什么", images=missing))
    assert events[-1]["type"] == "run.completed", events[-1]
    assert seen and seen[0]["messages"], "nothing reached the model"
    parts = seen[0]["messages"][-1]["content"]
    kinds = parts_kinds(parts)
    assert not any(kind.startswith(("attach", "located")) for kind in kinds), kinds
    assert kinds[0] == "scope" and kinds[-1] == "question"
    assert sum(1 for kind in kinds if kind == "question") == 1
    assert kinds.count("zoom_lead") == 1
    assert kinds.count("zoom_label") >= 2
    assert kinds.index("zoom_lead") < kinds.index("zoom_label") < kinds.index("question")
    assert not any("你的截图" in str(p.get("text", "")) for p in parts)