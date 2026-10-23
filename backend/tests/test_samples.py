"""Sample sessions on the public site: anyone opens them and asks; nobody but the owner changes them."""
from fastapi.testclient import TestClient

from tests.test_visitors import api, session, visitor  # noqa: F401 (the public-demo fixture)


def test_anyone_opens_a_sample_but_it_stays_its_owners(api, monkeypatch):  # noqa: F811
    app, store = api
    owner, me = visitor(app)
    session(app, store, "tut1", me, monkeypatch)
    session(app, store, "private1", me, monkeypatch)
    store.add_message("tut1", "user", "管理员问过的")
    store.add_message("tut1", "assistant", "管理员看到的回答")
    monkeypatch.setenv("SAMPLE_SESSIONS", "tut1, gone1")

    judge = TestClient(app.app)
    assert [s["id"] for s in judge.get("/api/samples").json()["samples"]] == ["tut1"]  # a missing id is left out
    opened = judge.get("/api/sessions/tut1").json()
    assert opened["sample"] is True and opened["messages"] == []  # opens clean
    assert judge.get("/api/link-jobs/tut1/transcript").status_code == 200
    assert judge.get("/api/sessions/private1").status_code == 404  # only the named ones
    assert judge.get("/api/sessions").json()["sessions"] == []  # not in their history

    assert judge.delete("/api/sessions/tut1").status_code == 403
    assert judge.post("/api/link-jobs/tut1/retry").status_code == 403
    assert judge.post("/api/link-jobs/tut1/studio", json={"text": "我要 GIF", "start": 1, "end": 3}).json() == {"ok": True, "saved": False}
    assert [m["content"] for m in store.messages("tut1")] == ["管理员问过的", "管理员看到的回答"]  # untouched

    mine = owner.get("/api/sessions/tut1").json()
    assert [m["content"] for m in mine["messages"]] == ["管理员问过的", "管理员看到的回答"]
    assert owner.post("/api/link-jobs/tut1/studio", json={"text": "我要 GIF", "start": 1, "end": 3}).json() == {"ok": True}


def test_without_samples_nothing_opens_up(api, monkeypatch):  # noqa: F811
    app, store = api
    _, me = visitor(app)
    session(app, store, "tut1", me, monkeypatch)
    monkeypatch.delenv("SAMPLE_SESSIONS", raising=False)
    judge = TestClient(app.app)
    assert judge.get("/api/samples").json() == {"samples": []}
    assert judge.get("/api/sessions/tut1").status_code == 404
