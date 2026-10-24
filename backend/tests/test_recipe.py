"""抄作业: a node tutorial's finished graph, kept to what holds together."""
import json

from modules import recipe


GRAPH = {"software": "Blender", "version": "4.1", "goal": "噪波场",
         "trees": [{"name": "几何节点", "nodes": [
             {"id": "n1", "name": "噪波纹理", "en": "Noise Texture", "time": 120, "params": [{"name": "缩放", "value": "5", "time": 123}]},
             {"id": "n2", "name": "设置位置", "time": 9999, "params": []},
             {"id": "", "name": "没有编号"}],
             "links": [{"from": "n1", "out": "颜色", "to": "n2", "in": "偏移", "time": 130},
                       {"from": "n1", "out": "系数", "to": "n9", "in": "x"},   # n9 doesn't exist
                       {"from": "n2", "out": "几何", "to": "n2", "in": "几何"}]},  # to itself
                   {"name": "空的", "nodes": [], "links": []}],
         "version_notes": [{"text": "4.0 起改名", "source": "评论"}, {"text": "", "source": "视频"}],
         "unsure": [{"text": "缩放看不清", "time": 300}], "tips": ["先连颜色"]}


def test_parse_keeps_real_links_and_times_inside_the_video():
    got = recipe.parse("好的，结果如下：\n" + json.dumps(GRAPH, ensure_ascii=False) + "\n以上", 600)
    assert [t["name"] for t in got["trees"]] == ["几何节点"]
    nodes = got["trees"][0]["nodes"]
    assert [n["id"] for n in nodes] == ["n1", "n2"] and nodes[1]["time"] is None  # 9999 s is past the end
    assert got["trees"][0]["links"] == [{"from": "n1", "out": "颜色", "to": "n2", "in": "偏移", "time": 130.0}]
    assert got["version_notes"] == [{"text": "4.0 起改名", "source": "评论"}]
    assert recipe.parse("没有 JSON", 600) is None and recipe.parse('{"trees": []}', 600) is None


def test_digest_reads_as_nodes_then_links():
    text = recipe.digest(recipe.parse(json.dumps(GRAPH, ensure_ascii=False), 600))
    assert "- 噪波纹理（Noise Texture） [画面 02:00]：缩放=5" in text and "噪波纹理.颜色 → 设置位置.偏移" in text
    assert "不确定：缩放看不清（回看 05:00）" in text


def test_the_video_is_read_in_windows_of_a_few_minutes():
    assert recipe.windows(1196) == [(0.0, 239.2), (239.2, 478.4), (478.4, 717.6), (717.6, 956.8), (956.8, 1196.0)]
    assert recipe.windows(60) == [(0.0, 60.0)] and recipe.windows(0) == [(0.0, 0.0)]


def test_nodes_are_checked_against_the_blender_catalog():
    got = recipe.normalize({"trees": [{"name": "材质", "nodes": [
        {"id": "n1", "name": "原理化BSDF", "en": "", "params": [], "time": None},
        {"id": "n2", "name": "自创节点", "en": "Made Up Node", "params": [], "time": None}], "links": []}]})
    bsdf, made_up = got["trees"][0]["nodes"]
    assert bsdf["ref"] == "ShaderNodeBsdfPrincipled" and bsdf["en"] == "Principled BSDF"
    assert bsdf["inputs"][0] == {"name": "基础色", "en": "Base Color", "type": "Color", "default": [0.8, 0.8, 0.8, 1.0]}
    assert made_up["ref"] is None and "inputs" not in made_up


def test_the_skill_is_asked_for_by_the_question():
    assert recipe.WANTS.search("给我最终的节点图，我直接抄作业")
    assert recipe.WANTS.search("把所有参数列出来")
    assert not recipe.WANTS.search("第三步点的是哪个按钮")


def test_connect_keeps_links_whose_sockets_exist_and_fit_marking_them_inferred():
    import asyncio

    tree = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "噪波纹理", "en": "", "params": [], "time": None},
        {"id": "b", "name": "设置位置", "en": "", "params": [], "time": None},
        {"id": "c", "name": "网格立方体", "en": "Cube", "params": [], "time": None}], "links": []}]})["trees"][0]
    answer = json.dumps({"links": [
        {"from": "a", "out": "颜色", "to": "b", "in": "偏移", "sure": False, "why": "噪波常用来偏移"},   # colour → vector: fits
        {"from": "a", "out": "系数", "to": "b", "in": "几何数据", "sure": False},                        # a number into geometry: no
        {"from": "c", "out": "不存在的口", "to": "b", "in": "几何数据", "sure": True},                    # no such socket
        {"from": "c", "out": "网格", "to": "b", "in": "几何数据", "sure": True}]}, ensure_ascii=False)

    async def complete(messages, max_tokens=0):
        return answer

    got = asyncio.run(recipe.connect(tree, "", complete))
    assert [(x["from"], x["out"], x["to"], x["in"], x["inferred"]) for x in got] == [
        ("a", "颜色", "b", "偏移", True), ("c", "网格", "b", "几何数据", False)]


def test_link_ends_and_axis_settings_land_on_the_real_sockets():
    got = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "锥形", "en": "Cone", "params": [], "time": None},
        {"id": "b", "name": "变换几何体", "en": "Transform Geometry", "time": None, "params": [
            {"name": "X旋转", "value": "180°", "time": 10}, {"name": "Z移动", "value": "unsure", "time": 11}]}],
        "links": [{"from": "a", "out": "网格", "to": "b", "in": "几何体", "time": None}]}]})
    tree = got["trees"][0]
    assert tree["links"][0]["in"] == "几何数据"  # Blender's Chinese for Geometry; the video said 几何体
    params = {p["name"]: p["value"] for p in tree["nodes"][1]["params"]}
    assert params["旋转"] == "180°, 0.0, 0.0" and params["移动"] == "0.0, 0.0, 待确认"


def test_a_2_9x_node_is_drawn_from_the_legacy_table_and_its_replacement_named():
    got = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "点旋转", "en": "", "params": [], "time": None}], "links": []}], "version_notes": []})
    node = got["trees"][0]["nodes"][0]
    assert node["ref"] == "GeometryNodePointRotate" and node["legacy"] == "2.93"
    assert [x["name"] for x in node["inputs"]][:2] == ["几何数据", "轴"]
    assert got["version_notes"][0]["source"] == "节点目录" and "「点旋转」→ 旋转实例" in got["version_notes"][0]["text"]


def test_trees_of_one_name_are_joined_and_twin_nodes_kept_once():
    got = recipe.merge_same({"trees": [
        {"name": "几何节点：Geometry Nodes（主体）", "nodes": [{"id": "n1", "name": "点旋转", "params": []}, {"id": "n2", "name": "混合属性", "params": []}],
         "links": [{"from": "n2", "out": "几何数据", "to": "n1", "in": "几何数据"}]},
        {"name": "几何节点：Geometry Nodes（续）", "nodes": [{"id": "n1", "name": "点旋转", "params": []}, {"id": "n2", "name": "设置材质", "params": []}],
         "links": [{"from": "n1", "out": "几何数据", "to": "n2", "in": "几何数据"}]}]})
    assert len(got["trees"]) == 1
    tree = got["trees"][0]
    assert [n["name"] for n in tree["nodes"]] == ["点旋转", "混合属性", "设置材质"]
    assert ("n1", tree["nodes"][2]["id"]) in {(l["from"], l["to"]) for l in tree["links"]}  # the second tree's link moved onto the kept 点旋转


def test_trees_that_differ_by_more_than_a_note_stay_apart():
    got = recipe.merge_same({"trees": [{"name": "材质：方块 A", "nodes": [{"id": "a", "name": "x", "params": []}], "links": []},
                                       {"name": "材质：方块 B", "nodes": [{"id": "a", "name": "x", "params": []}], "links": []}]})
    assert len(got["trees"]) == 2


def test_operation_titles_and_zone_pairs_are_read_as_blender_has_them():
    got = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "循环", "en": "Repeat", "params": [{"name": "最大值", "value": "4", "time": 1}], "time": None},
        {"id": "b", "name": "等于", "en": "", "params": [], "time": None},
        {"id": "c", "name": "模拟", "en": "", "params": [], "time": None},
        {"id": "d", "name": "模拟", "en": "Simulation", "params": [], "time": None}], "links": []}], "version_notes": []})
    a, b, c, d = got["trees"][0]["nodes"]
    assert (a["ref"], a["title"]) == ("ShaderNodeMath", "循环") and a["params"][0] == {"name": "运算", "value": "循环", "time": None}
    assert (b["ref"], b["title"]) == ("FunctionNodeCompare", "等于")
    assert (c["ref"], d["ref"]) == ("GeometryNodeSimulationInput", "GeometryNodeSimulationOutput")


def test_the_group_output_gets_the_one_geometry_left_dangling():
    tree = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "i", "name": "组输入", "en": "", "params": [], "time": None},
        {"id": "s", "name": "模拟", "en": "", "params": [], "time": None},
        {"id": "o", "name": "模拟", "en": "", "params": [], "time": None},
        {"id": "g", "name": "组输出", "en": "", "params": [], "time": None}],
        "links": [{"from": "i", "out": "几何数据", "to": "s", "in": "几何数据", "time": None},
                  {"from": "s", "out": "几何数据", "to": "o", "in": "几何数据", "time": None}]}]})["trees"][0]
    added = recipe.close_ends(tree)
    assert [(x["from"], x["to"], x["inferred"]) for x in added] == [("o", "g", True)]


def test_links_and_nodes_read_in_two_pictures_settle_the_graph():
    def reading(links):
        names = {"组输入", "切换", "合并几何体", "变换几何体"}
        ids = {n: f"r{i}" for i, n in enumerate(sorted(names))}
        return {"trees": [{"name": "几何节点", "nodes": [{"id": ids[n], "name": n, "en": "", "params": [], "time": None} for n in sorted(names)],
                           "links": [{"from": ids[a], "out": "几何数据" if a != "切换" else "输出", "to": ids[b], "in": i, "time": None} for a, b, i in links]}]}
    seen = [reading([("切换", "合并几何体", "几何数据"), ("合并几何体", "变换几何体", "几何数据")]),
            reading([("切换", "合并几何体", "几何数据"), ("合并几何体", "变换几何体", "几何数据"), ("组输入", "合并几何体", "几何数据")])]
    final = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "a", "name": "组输入", "en": "", "params": [], "time": None},
        {"id": "b", "name": "切换", "en": "", "params": [], "time": None},
        {"id": "c", "name": "合并几何体", "en": "", "params": [], "time": None}],
        "links": [{"from": "a", "out": "几何数据", "to": "b", "in": "假", "time": None}]}]})  # a link no picture shows
    recipe.vote(final, seen)
    tree = final["trees"][0]
    names = {n["id"]: n["name"] for n in tree["nodes"]}
    got = {(names[l["from"]], names[l["to"]]) for l in tree["links"]}
    assert "变换几何体" in names.values()  # read twice, lost in the merge: back
    assert got == {("切换", "合并几何体"), ("合并几何体", "变换几何体")}  # 组输入→切换 seen nowhere: gone; 组输入→合并 once: not added


def test_a_geometry_tree_without_its_group_output_gets_one():
    tree = recipe.normalize({"trees": [{"name": "几何节点", "nodes": [
        {"id": "s", "name": "模拟", "en": "", "params": [], "time": None},
        {"id": "o", "name": "模拟", "en": "", "params": [], "time": None}],
        "links": [{"from": "s", "out": "几何数据", "to": "o", "in": "几何数据", "time": None}]}]})["trees"][0]
    added = recipe.close_ends(tree)
    assert tree["nodes"][-1]["ref"] == "NodeGroupOutput" and [(x["from"], x["to"]) for x in added] == [("o", "group_output")]


def test_addon_names_and_unknown_nodes_are_looked_up_only_with_a_source(monkeypatch):
    import asyncio

    from modules.agent import web
    terms = recipe.addon_terms({"trees": [{"nodes": [{"name": "自定义波浪", "ref": None}, {"name": "设置位置", "ref": "GeometryNodeSetPosition"}]}]},
                               ["[00:10 · 10s] 说：先打开 Node Wrangler，再装一下 Sverchok 插件", "[00:20 · 20s] 说：这个插件很好用"])
    assert terms == ["自定义波浪", "Node Wrangler", "Sverchok"]

    async def search(query, limit=8, freshness=""):
        return [web.SearchResult("Node Wrangler — Blender Extensions", "https://extensions.blender.org/add-ons/node-wrangler/", "节点工具")]

    monkeypatch.setattr(web, "search", search)

    async def says(url):
        async def complete(messages, max_tokens=0):
            return json.dumps({"plugin": "Node Wrangler", "provides": "节点快捷操作", "install": "扩展平台安装", "url": url}, ensure_ascii=False)
        return complete

    good = asyncio.run(recipe.find_plugin("Node Wrangler", asyncio.run(says("https://extensions.blender.org/add-ons/node-wrangler/"))))
    assert good["plugin"] == "Node Wrangler" and good["url"].startswith("https://extensions.blender.org")
    assert asyncio.run(recipe.find_plugin("Node Wrangler", asyncio.run(says("https://made-up.example/")))) is None  # no source among the results


def test_the_blender_version_comes_from_the_title_or_the_status_bar():
    assert recipe.blender_version("【Blender教程】纯节点！Blender4.0有机方块动画", []) == "4.0"
    assert recipe.blender_version("几何节点教程", ["场景集合 4.1.0", "移动 0.005 m", "4.1.0 Alpha"]) == "4.1.0"
    assert recipe.blender_version("几何节点教程", ["缩放 1.000"]) == ""
