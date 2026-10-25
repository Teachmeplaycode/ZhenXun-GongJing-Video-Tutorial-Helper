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

    monkeypatch.setenv("RECIPE_ENABLED", "1")  # 抄作业 is off by default

    job = job_for(tmp_path)
    monkeypatch.setitem(app.jobs, "job1", job)
    client = TestClient(app.app)
    assert client.get("/api/link-jobs/job1/recipe/script").status_code == 404
    recipe.save(job.root, ZONE)
    got = client.get("/api/link-jobs/job1/recipe/script")
    assert got.status_code == 200 and got.text.startswith("# 帧寻 · 抄作业") and "python" in got.headers["content-type"]


def test_applying_again_reuses_the_帧寻_modifier_instead_of_adding_one():
    text = recipe_script.script(ZONE)
    assert 'mod = obj.modifiers.get("帧寻·几何节点.007") or obj.modifiers.new("帧寻·几何节点.007", \'NODES\')' in text
    assert recipe_script.owned_name("材质：有机方块 这里很长很长很长") == "帧寻·材质：有机方块 这里很长很长"


def test_vector_math_slots_take_vectors():
    found = {"trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "矢量运算", "params": [{"name": "运算", "value": "吸附", "time": 1}, {"name": "增量", "value": "0, 0, 0.2", "time": 1}]},
        {"id": "b", "name": "矢量运算", "params": [{"name": "运算", "value": "循环", "time": 1}, {"name": "最大值", "value": "2", "time": 1}]}],
        "links": []}]}
    recipe.normalize(found)
    text = recipe_script.script(found)
    assert 'put_at(n["a"], 1, [0.0, 0.0, 0.2])' in text and 'put_at(n["b"], 1, [2.0, 2.0, 2.0])' in text


def test_recipe_is_off_by_default(tmp_path, monkeypatch):
    import app

    monkeypatch.delenv("RECIPE_ENABLED", raising=False)
    monkeypatch.setattr(app.recipe, "enabled", lambda: False)
    client = TestClient(app.app)
    for method, path in (("get", "/api/link-jobs/abc/recipe"), ("get", "/api/link-jobs/abc/recipe/script"),
                         ("post", "/api/link-jobs/abc/recipe/revise"), ("get", "/api/blender/status")):
        r = getattr(client, method)(path)
        assert r.status_code == 404 and "已关闭" in r.json()["detail"]
