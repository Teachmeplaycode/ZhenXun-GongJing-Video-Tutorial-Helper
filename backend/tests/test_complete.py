"""Tab completion: the continuation only, short, and rate-limited per person."""
from fastapi.testclient import TestClient

from modules import complete
from tests.test_replay import job_for


def test_the_continuation_is_trimmed_to_what_comes_next():
    assert complete.clean("数据透视表是在哪一步改成表格形式的？", "数据透视表") == "是在哪一步改成表格形式的？"
    assert complete.clean("“改成表格形式？”\n解释", "数据透视表") == "改成表格形式？"
    assert len(complete.clean("很" * 80, "x")) == complete.MAX_CHARS


def test_the_route_asks_the_model_and_limits_the_rate(tmp_path, monkeypatch):
    import app

    class Model:
        async def stream(self, messages, usage, **kw):
            assert "已输入：第二种方法" in messages[-1]["content"]
            yield "是怎么加字幕的？"

    monkeypatch.setitem(app.jobs, "job1", job_for(tmp_path, "local"))
    monkeypatch.setattr(app.complete_service, "get_client", lambda: Model())
    monkeypatch.setattr(app.complete_service, "last_question", lambda job_id: "")
    monkeypatch.setattr(app.complete_service, "calls", __import__("collections").defaultdict(list))
    client = TestClient(app.app)
    assert client.post("/api/link-jobs/job1/complete", json={"text": "第二种方法"}).json() == {"completion": "是怎么加字幕的？"}
    assert client.post("/api/link-jobs/job1/complete", json={"text": "第二种方法"}).json() == {"completion": ""}  # too soon
    assert client.post("/api/link-jobs/job1/complete", json={"text": "第"}).json() == {"completion": ""}  # too short to guess
