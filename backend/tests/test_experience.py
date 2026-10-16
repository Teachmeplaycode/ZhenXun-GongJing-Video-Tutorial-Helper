"""Experience: lessons distilled from past answers reach the system prompt; test runs never feed them."""
import json
import sys
from pathlib import Path

import pytest

from modules.agent import experience

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_no_file_adds_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(experience, "settings", lambda: {})
    assert experience.guide() == ""
    monkeypatch.setattr(experience, "settings", lambda: {"EXPERIENCE_FILE": str(tmp_path / "missing.json")})
    assert experience.guide() == ""


def test_lessons_are_listed_by_kind(monkeypatch, tmp_path):
    path = tmp_path / "exp.json"
    path.write_text(json.dumps({"lessons": {"动作重复了几次": ["峰值数常是次数的两倍", "先 replay 再数"]}}, ensure_ascii=False))
    monkeypatch.setattr(experience, "settings", lambda: {"EXPERIENCE_FILE": str(path)})
    text = experience.guide()
    assert "以往答题积累的经验" in text and "【动作重复了几次】\n- 峰值数常是次数的两倍\n- 先 replay 再数" in text


def test_distilling_refuses_test_runs(tmp_path, monkeypatch):
    import experience as distill_script

    run = tmp_path / "run.json"
    run.write_text(json.dumps({"split": "test", "results": []}))
    monkeypatch.setattr(sys, "argv", ["experience.py", str(run), "--out", str(tmp_path / "out.json")])
    with pytest.raises(SystemExit, match="不是训练集"):
        import asyncio
        asyncio.run(distill_script.main())


def test_a_record_shows_what_was_looked_at():
    import experience as distill_script

    text = distill_script.record({"correct": False, "question": "How many times?\nA. 2\nB. 4", "answer": "B", "choice": "A",
                                  "trace": [{"tool": "frames.motion", "args": {"start": "0", "end": "5"}, "output": "峰值 8 个"}],
                                  "reply": "我数到 2 次。答案：A"})
    assert text.startswith("[错] 题目：How many times?") and "正确答案 B，agent 选 A" in text
    assert "frames.motion" in text and "峰值 8 个" in text and "答案：A" in text
