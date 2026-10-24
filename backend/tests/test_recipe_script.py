"""抄作业 as a Blender script: it parses, builds every catalogued node, sets operations and values, links by name."""
import ast
import json
from pathlib import Path

from fastapi.testclient import TestClient

from modules import recipe, recipe_script
from tests.test_replay import job_for

ZONE = json.loads((Path(__file__).parents[2] / "front/e2e/fixtures/recipe-zone.json").read_text())  # a real Blender tutorial


def test_the_script_parses_and_builds_the_tutorials_graph():
    text = recipe_script.script(ZONE)
    ast.parse(text)
    assert "add(tree, 'GeometryNodeSimulationInput'" in text and ".pair_with_output(" in text
    assert "'operation', 'WRAP')" in text and "'use_clamp', True)" in text and 'put_at(n["n6"], 1, 3.0)' in text
    assert 'put(n["n9"], "Translation", (0.0, 0.0, 0.005))' in text
    assert "'input_type', 'GEOMETRY')" in text
    assert 'link(tree, n["n1"], "Geometry", 0,' in text  # the group input's socket, though the catalog lists none


def test_what_the_script_cant_do_is_a_comment_not_a_guess():
    r = recipe.normalize({"goal": "", "trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "点旋转", "en": "", "params": [], "time": None},
        {"id": "b", "name": "变换几何体", "en": "", "params": [{"name": "移动", "value": "0, 0, 待确认", "time": 3}], "time": None},
        {"id": "c", "name": "神秘插件节点", "en": "", "params": [], "time": None}], "links": [
        {"from": "a", "out": "几何数据", "to": "b", "in": "几何数据", "time": None}]}], "version_notes": []})
    text = recipe_script.script(r)
    ast.parse(text)
    assert "# 手动：「点旋转」Blender 2.93 的旧节点" in text and "# 手动：「神秘插件节点」不在 Blender 自带节点里" in text
    assert "# 手动：「变换几何体」的「移动」= 0, 0, 待确认" in text
    assert "GeometryNodePointRotate" not in text  # a node Blender 5.0 doesn't have is never created


def test_the_script_endpoint(tmp_path, monkeypatch):
    import app

    job = job_for(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/recipe/script").status_code == 404
    recipe.save(job.root, ZONE)
    got = client.get("/api/link-jobs/job1/recipe/script")
    assert got.status_code == 200 and got.text.startswith("# 帧寻 · 抄作业") and "python" in got.headers["content-type"]
