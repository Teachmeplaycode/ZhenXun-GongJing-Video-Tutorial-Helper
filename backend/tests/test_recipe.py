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
