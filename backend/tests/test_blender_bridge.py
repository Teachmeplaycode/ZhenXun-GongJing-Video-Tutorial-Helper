"""The person's own Blender: 对答案 against real exports from Blender 5.0, and the local-only endpoints."""
import json
import socket
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from modules import recipe
from modules.blender import check
from tests.test_replay import job_for

HERE = Path(__file__).parent
ZONE = json.loads((HERE.parents[1] / "front/e2e/fixtures/recipe-zone.json").read_text())
FULL = json.loads((HERE / "fixtures/blender_export_full.json").read_text())      # the script's tree, read back from Blender
BROKEN = json.loads((HERE / "fixtures/blender_export_broken.json").read_text())  # Transform deleted, 组输入→真 cut, Wrap max 5


def test_a_tree_built_from_the_answer_checks_out():
    got = check.compare(ZONE["trees"][0], FULL)
    assert got["done"] and got["matched"] == got["nodes"] == 10 and got["findings"] == []


def test_mistakes_are_named_in_the_persons_words():
    got = check.compare(ZONE["trees"][0], BROKEN)
    texts = [f["text"] for f in got["findings"]]
    assert "少了节点「变换几何体」：Shift+A 搜「变换几何体」添加" in texts
    assert "缺一根线：组输入.几何数据 → 切换.真" in texts
    assert "「循环」的「最大值」应为 3，你的是 5" in texts
    assert not got["done"] and got["summary"].startswith("还差 1 个节点")


class FakeBlender:
    """The add-on's protocol: one JSON line in, one out."""
    def __init__(self, answers):
        self.answers, self.seen = answers, []
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(4)
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                request = json.loads(conn.makefile().readline())
                self.seen.append(request)
                conn.sendall((json.dumps(self.answers[request["cmd"]], ensure_ascii=False) + "\n").encode())


def test_endpoints_apply_and_check_through_the_bridge(tmp_path, monkeypatch):
    import app

    job = job_for(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)
    recipe.save(job.root, ZONE)
    fake = FakeBlender({"ping": {"ok": True, "blender": "5.0.1", "object": "Cube"},
                        "run_script": {"ok": True, "output": "帧寻：节点已生成\n"},
                        "export_tree": {**BROKEN, "ok": True}})
    monkeypatch.setenv("BLENDER_BRIDGE_PORT", str(fake.port))
    client = TestClient(app.app)
    assert client.get("/api/blender/status").json() == {"available": True, "connected": True, "blender": "5.0.1", "object": "Cube"}
    applied = client.post("/api/link-jobs/job1/recipe/apply", json={}).json()
    assert applied["ok"] and "节点已生成" in applied["output"]
    assert fake.seen[-1]["cmd"] == "run_script" and "GeometryNodeSimulationInput" in fake.seen[-1]["code"]
    checked = client.post("/api/link-jobs/job1/recipe/check", json={"tree": 0}).json()
    assert fake.seen[-1] == {"cmd": "export_tree", "target": "geometry"} and len(checked["findings"]) >= 3
    assert client.get("/api/blender/addon").text.startswith('"""帧寻 Bridge')


def test_without_blender_or_on_the_web_demo(tmp_path, monkeypatch):
    import app

    job = job_for(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)
    recipe.save(job.root, ZONE)
    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    port = free.getsockname()[1]
    free.close()  # nothing listens there
    monkeypatch.setenv("BLENDER_BRIDGE_PORT", str(port))
    client = TestClient(app.app)
    status = client.get("/api/blender/status").json()
    assert status["connected"] is False and "帧寻 Bridge" in status["message"]
    assert client.post("/api/link-jobs/job1/recipe/check", json={}).status_code == 409
    monkeypatch.setattr(app.visitors, "enabled", lambda: True)
    assert client.get("/api/blender/status").json()["available"] is False


def test_a_math_node_without_an_operation_in_the_answer_matches_blenders_default():
    tree = {"name": "几何节点", "nodes": [{"id": "m", "name": "运算", "ref": "ShaderNodeMath", "params": [], "inputs": [], "outputs": []}], "links": []}
    theirs = {"name": "t", "nodes": [{"name": "Math", "bl_idname": "ShaderNodeMath", "operation": "ADD", "inputs": [], "outputs": []}], "links": []}
    assert check.compare(tree, theirs)["done"]
