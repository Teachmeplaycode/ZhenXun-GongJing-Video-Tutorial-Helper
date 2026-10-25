"""AI 修改 (modules/recipe_revise.py): what it calls a problem, how edits land, the loop with a scripted model."""
import asyncio
import json
from types import SimpleNamespace

from modules import recipe, recipe_revise
from modules.llm import ToolCall


def tree(nodes, links):
    t = {"name": "几何节点", "nodes": [{"id": i, "name": name, "params": params, "time": None} for i, name, params in nodes],
         "links": [{"from": a, "out": o, "to": b, "in": i, "time": None} for a, o, b, i in links]}
    recipe.normalize({"trees": [t], "version_notes": []})
    return t


def test_problems_name_a_misread_node_an_unused_output_and_a_loop():
    t = tree([("gin", "组输入", []), ("cap", "捕捉属性", [{"name": "增量", "value": "0, 0, 0.2", "time": 1}]),
              ("set", "设置位置", []), ("ext", "挤出网格", []), ("join", "合并几何体", []), ("fill", "填充曲线", []),
              ("gout", "组输出", [])],
             [("gin", "几何数据", "set", "几何数据"), ("set", "几何数据", "ext", "网格"), ("ext", "网格", "join", "几何数据"),
              ("join", "几何数据", "set", "几何数据"), ("join", "几何数据", "gout", "几何数据"), ("gin", "几何数据", "fill", "曲线")])
    found = "\n".join(recipe_revise.problems(t))
    assert "「捕捉属性」(cap) 没有「增量」这个设置" in found and "吸附" in found
    assert "「填充曲线」(fill) 的输出没有接到任何地方" in found
    assert "回路" in found


def test_a_word_setting_the_catalog_may_not_list_is_not_a_problem():
    t = tree([("sp", "设置样条线类型", [{"name": "类型", "value": "NURBS", "time": 1}])], [])
    assert not any("没有「类型」" in p for p in recipe_revise.problems(t))


def test_operation_sockets_dot_product_gives_a_value_and_snap_labels_its_increment():
    t = tree([("dot", "矢量运算", [{"name": "运算", "value": "点乘", "time": 1}]),
              ("snap", "矢量运算", [{"name": "运算", "value": "吸附", "time": 1}]),
              ("cmp", "比较", [])],
             [("dot", "值", "cmp", "A")])
    by = {n["id"]: n for n in t["nodes"]}
    assert [s["name"] for s in by["dot"]["outputs"]] == ["值"]
    assert [s["name"] for s in by["snap"]["inputs"]] == ["矢量", "增量"]
    assert not any("dot" in p or "点乘" in p for p in recipe_revise.problems(t))


def test_apply_ops_edits_and_renames_onto_the_catalog():
    t = tree([("gin", "组输入", []), ("gout", "组输出", [])], [])
    done = recipe_revise.apply_ops(t, [{"op": "add_node", "id": "tr", "name": "变换"},
                                       {"op": "add_link", "from": "gin", "out": "几何数据", "to": "tr", "in": "几何"},
                                       {"op": "add_link", "from": "tr", "out": "几何数据", "to": "gout", "in": "几何数据"},
                                       {"op": "set_param", "id": "tr", "name": "缩放", "value": "2"},
                                       {"op": "remove_link", "from": "nope", "to": "gout"},
                                       {"op": "fly"}])
    assert done[0] == "加节点「变换」(tr)" and done[-2].startswith("没找到要断开的线") and done[-1].startswith("没执行")
    node = next(n for n in t["nodes"] if n["id"] == "tr")
    assert node["ref"] == "GeometryNodeTransform"
    assert {"from": "gin", "out": "几何数据", "to": "tr", "in": "几何数据", "time": None} in t["links"]
    assert recipe_revise.problems(t) == []


class Script:
    """A model that answers with the tool calls it is given, in turn, then a summary."""

    def __init__(self, turns):
        self.turns, self.seen = list(turns), []

    async def stream(self, messages, usage, max_tokens=0, tools=None):
        self.seen.append(messages[-1])
        turn = self.turns.pop(0) if self.turns else "改好了"
        if isinstance(turn, str):
            yield turn
            return
        usage.tool_calls = [ToolCall(f"c{i}", name, args) for i, (name, args) in enumerate(turn)]
        yield ""


def test_revise_edits_checks_in_blender_saves_and_undoes(tmp_path):
    t = tree([("gin", "组输入", []), ("tr", "变换几何体", []), ("gout", "组输出", [])], [("gin", "几何数据", "tr", "几何数据")])
    found = {"trees": [t], "unsure": []}
    recipe.save(tmp_path, found)
    job = SimpleNamespace(root=tmp_path, transcript=None, screentext=None, video=SimpleNamespace(title="t", duration=10))
    built = []

    async def blender_check(tr):
        built.append(len(tr["links"]))
        return "建出 3 个节点、2 根线\n没有无效连线", "cG5n"

    llm = Script([[("edit", {"ops": [{"op": "add_link", "from": "tr", "out": "几何数据", "to": "gout", "in": "几何数据"}]})],
                  [("check_blender", {})],
                  "补上了变换几何体到组输出的线。"])
    r = asyncio.run(recipe_revise.revise(job, found, 0, "", llm, tools=None, blender_check=blender_check))
    assert r["summary"] == "补上了变换几何体到组输出的线。" and r["problems"] == [] and built == [2]
    assert r["preview"] == "cG5n" and r["changes"] == ["连线 tr.几何数据 → gout.几何数据"]
    assert any(x.get("type") == "image_url" for x in llm.seen[2]["content"])  # the render went to the model
    assert len(recipe.load(tmp_path)["trees"][0]["links"]) == 2
    assert recipe_revise.undo(tmp_path) is not None and len(recipe.load(tmp_path)["trees"][0]["links"]) == 1
    assert recipe_revise.undo(tmp_path) is None


def test_stopping_with_problems_left_is_pushed_back_once(tmp_path):
    t = tree([("gin", "组输入", []), ("gout", "组输出", [])], [])
    found = {"trees": [t], "unsure": []}
    job = SimpleNamespace(root=tmp_path, transcript=None, screentext=None, video=SimpleNamespace(title="t", duration=10))
    llm = Script(["好了", "还是好了"])
    r = asyncio.run(recipe_revise.revise(job, found, 0, "", llm, tools=None))
    assert "先别结束" in json.dumps(llm.seen[1], ensure_ascii=False) and r["summary"] == "还是好了"
