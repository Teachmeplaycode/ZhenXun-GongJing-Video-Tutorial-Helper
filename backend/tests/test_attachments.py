"""Pictures attached to a question: re-encoded on upload, served only to the session's owner, and
sent to the model after the question as the person's own screenshots."""
import cv2
import numpy as np
from fastapi.testclient import TestClient

from modules.agent.run import ATTACHED_NOTE, attached_parts, build_messages
from tests.test_replay import job_for


def png(width=2400, height=1200) -> bytes:
    image = np.full((height, width, 3), 200, np.uint8)
    cv2.putText(image, "Data > Validation", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 0, 0), 6)
    return cv2.imencode(".png", image)[1].tobytes()


def test_an_attached_picture_is_kept_as_a_smaller_jpeg(tmp_path, monkeypatch):
    import app

    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setitem(app.jobs, "job1", job_for(tmp_path, "local"))
    client = TestClient(app.app)
    r = client.post("/api/link-jobs/job1/attachments", files={"file": ("shot.png", png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert (body["width"], body["height"]) == (1600, 800)  # the long side capped
    got = client.get(body["url"])
    assert got.status_code == 200 and got.content[:2] == b"\xff\xd8"
    assert client.post("/api/link-jobs/job1/attachments", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 415
    assert client.get("/api/link-jobs/job1/attachments/..%2Fx.jpg").status_code == 404


def test_the_model_gets_them_after_the_question_as_the_persons_own(tmp_path):
    shot = tmp_path / "a.jpg"
    shot.write_bytes(cv2.imencode(".jpg", np.zeros((10, 10, 3), np.uint8))[1].tobytes())
    parts = attached_parts([shot, tmp_path / "missing.jpg"])
    assert parts[0]["text"] == ATTACHED_NOTE.format(n=1)
    assert [p["type"] for p in parts] == ["text", "text", "image_url"]
    job = job_for(tmp_path)
    from modules.screentext import ScreenText
    from modules.transcript import Transcript
    job.transcript, job.screentext = Transcript(), ScreenText()
    last = build_messages(job, [], "我卡在哪了？", [], scope_all=True, images=[shot])[-1]["content"]
    assert last[1]["text"] == "问题：我卡在哪了？" and last[-1]["type"] == "image_url"
