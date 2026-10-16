import json
import time

import pytest

from modules import log


@pytest.fixture(autouse=True)
def detach():
    yield
    log.logger.handlers.clear()  # later tests must not write into this test's folder


def records(folder):
    return [json.loads(line) for path in folder.glob("*.jsonl") for line in path.read_text().splitlines()]


def test_events_are_json_lines_with_a_console_summary(tmp_path, capsys):
    old = tmp_path / "2020-01-01.jsonl"
    old.write_text("{}\n")
    import os
    os.utime(old, (0, 0))
    log.setup(tmp_path)
    assert not old.exists()  # older than KEEP_DAYS
    log.event("answer", status="done", elapsed_ms=12300, prompt_tokens=35000, completion_tokens=800,
              tools=[{"name": "audience.danmaku", "ms": 40, "ok": True, "count": 3}])
    try:
        raise ValueError("坏了")
    except ValueError as exc:
        log.error("link.frames", exc, job_id="j1")
    rows = records(tmp_path)
    assert rows[0]["event"] == "answer" and rows[0]["prompt_tokens"] == 35000 and rows[0]["ts"] <= time.time()
    assert rows[1] == rows[1] | {"event": "error", "where": "link.frames", "type": "ValueError", "message": "坏了", "job_id": "j1"}
    assert "raise ValueError" in rows[1]["trace"]
    err = capsys.readouterr().err
    assert "[log] answer status=done 12.3s 35.0k→0.8k tokens tools=audience.danmaku" in err


def test_track_times_each_tool_call():
    from app import track

    calls = {}
    for e in [{"type": "tool_call.started", "call_id": "t1", "tool_name": "web.search", "t": 1.0},
              {"type": "tool_call.output", "call_id": "t1", "exit_code": 1, "t": 2.0},
              {"type": "tool_call.completed", "call_id": "t1", "result_count": 0, "t": 2.5},
              {"type": "tool_call.started", "call_id": "t2", "tool_name": "frames.view", "t": 3.0},
              {"type": "tool_call.completed", "call_id": "t2", "result_count": 4, "t": 3.2}]:
        track(calls, e)
    assert calls["t1"] == calls["t1"] | {"name": "web.search", "ms": 1500, "ok": False, "count": 0}
    assert calls["t2"] == calls["t2"] | {"ms": 200, "ok": True, "count": 4}


def test_stats_report_summarizes():
    from scripts.log_stats import report

    now = time.time()
    rows = [
        {"ts": now, "event": "answer", "status": "done", "elapsed_ms": 10000, "prompt_tokens": 30000, "completion_tokens": 500,
         "model": "m", "tools": [{"name": "web.search", "ms": 2000, "ok": True}]},
        {"ts": now, "event": "answer", "status": "error", "code": "timeout", "elapsed_ms": 60000, "prompt_tokens": 10000,
         "completion_tokens": 0, "tools": [{"name": "web.search", "ms": 4000, "ok": False}]},
        {"ts": now, "event": "link.resolve", "ok": False, "code": "login_expired"},
        {"ts": now, "event": "error", "where": "/api/x", "type": "KeyError", "message": "k", "trace": "tb"},
    ]
    text = report(rows, show_errors=True)
    assert "## 回答  2 次" in text and "done 1" in text and "timeout 1" in text
    assert "web.search" in text and "失败原因：login_expired 1" in text
    assert "1 个未处理" in text and "tb" in text
