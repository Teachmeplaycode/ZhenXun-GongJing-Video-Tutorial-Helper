"""Exercise the actual export router against a temporary persistent session."""
import importlib
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from modules.frames import FrameJob
from modules.video_source import ResolvedVideo


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("GONGJING_DATA_DIR", str(tmp_path))
    import app
    module = importlib.reload(app)
    job = FrameJob("export-job", ResolvedVideo("bilibili", "BV1", "https://www.bilibili.com/video/BV1", "导出测试", 60, []), None, tmp_path / "jobs" / "export-job")
    module.jobs[job.id] = job
    module.store.create(job, "任务")
    module.store.add_message(job.id, "user", "需要导出的问题")
    module.store.add_message(job.id, "assistant", "需要导出的回答 [00:30]")
    module.store.add_message(job.id, "user", "不选的问题")
    with TestClient(module.app) as client:
        yield client, job, module.store.messages(job.id)


def test_export_router_download_contains_exact_selected_rows(api):
    client, job, messages = api
    ids = ",".join(str(m["id"]) for m in messages[:2])
    response = client.get(f"/api/sessions/{job.id}/export", params={"ids": ids})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        note = archive.read("笔记.md").decode()
    assert note.count("需要导出的问题") == note.count("需要导出的回答") == 1
    assert "不选的问题" not in note


@pytest.mark.parametrize("ids", ["", ",", "oops", "1,bad", "-1", "0", "999999"])
def test_explicit_empty_invalid_or_foreign_selection_cannot_export_all(api, ids):
    client, job, _ = api
    assert client.get(f"/api/sessions/{job.id}/export", params={"ids": ids}).status_code == 400


def test_omitted_selection_exports_all_and_pdf_is_explicitly_print_html(api):
    client, job, _ = api
    response = client.get(f"/api/sessions/{job.id}/export", params={"format": "pdf"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.startswith("<!DOCTYPE html>")
    assert "不选的问题" in response.text
    assert 'href="https://www.bilibili.com/video/BV1?t=30"' in response.text
    assert client.get(f"/api/sessions/{job.id}/export", params={"format": "doc"}).status_code == 422
    assert client.get("/api/sessions/missing/export").status_code == 404
