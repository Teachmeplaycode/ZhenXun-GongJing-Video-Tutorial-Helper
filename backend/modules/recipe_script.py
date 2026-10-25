"""抄作业 as a Blender script: paste it into Blender's Scripting tab and run, and the node tree is built.

From a graph normalized against the catalog (modules/recipe.py, modules/knowledge): every node with a
catalog id is created by its type, set to its operation (循环 → WRAP), its changed settings written by
the socket's English name (vectors as X / Y / Z, ° turned to radians, m dropped), linked socket to socket,
zones paired. What the script can't do it says in a comment instead of guessing: a node Blender 5.0
doesn't have (2.9x nodes, add-on nodes), a value the video didn't show (待确认), a menu socket.
Geometry trees become node groups (and the active object's modifier); shader trees a material; a world
tree the scene's world.
"""
from __future__ import annotations

import json
import math
import re

from . import knowledge

GAP_X, GAP_Y = 300, 220
# Math's second and third Value carry the operation's own labels in the editor (Wrap: 最大值 / 最小值).
MATH_SLOTS = {"最大值": 1, "max": 1, "最小值": 2, "min": 2, "值2": 1, "b": 1, "值3": 2, "c": 2, "增量": 1, "increment": 1}
FLAGS = {"钳制": "use_clamp", "clamp": "use_clamp"}  # tick boxes that are node properties, not sockets
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
TRUE = re.compile(r"^(勾选|是|开|✓|true|yes|on)$", re.I)
FALSE = re.compile(r"^(不勾选|未勾选|否|关|✗|false|no|off)$", re.I)


def _kind(tree_name: str) -> str:
    if re.search(r"世界|world", tree_name, re.I):
        return "world"
    if re.search(r"材质|着色|shader|material", tree_name, re.I):
        return "material"
    if re.search(r"合成|compositor", tree_name, re.I):
        return "compositor"
    return "geometry"


def _number(text: str) -> float | None:
    m = NUMBER.search(text or "")
    if not m:
        return None
    value = float(m.group())
    return math.radians(value) if "°" in text else value


def _value(socket: dict, text: str):
    """A setting read off the video as Python for default_value; None when it can't be written."""
    kind = socket.get("type", "")
    text = str(text).strip()
    if not text or "待确认" in text:
        return None
    if kind.startswith(("Bool",)):
        return True if TRUE.match(text) else False if FALSE.match(text) else None
    if kind.startswith(("Float", "Int")):
        n = _number(text)
        return None if n is None else (int(round(n)) if kind.startswith("Int") else n)
    if kind.startswith(("Vector", "Rotation")):
        parts = [p for p in re.split(r"[,，;；]", text) if p.strip()]
        if len(parts) == 1 and kind.startswith("Vector") and _number(parts[0]) is not None and not re.search(r"[XYZ]\s*[:：=]", text, re.I):
            return (_number(parts[0]),) * 3  # 「尺寸 2 m」: the same on every axis
        named = {a: re.search(rf"{a}\s*[:：=]\s*([^,，;；\s]+)", text, re.I) for a in "XYZ"}
        if all(named.values()):
            parts = [named[a].group(1) for a in "XYZ"]
        numbers = [_number(p) for p in parts[:3]]
        return tuple(numbers) if len(numbers) == 3 and None not in numbers else None
    return None  # menus, strings, colours, objects: set by hand


def _layout(tree: dict, saved: dict) -> dict:
    """Positions: the ones dragged on the canvas, else columns by the longest chain of links into each node."""
    if saved:
        return {k: (v[0], -v[1]) for k, v in saved.items()}
    into = {n["id"]: [l["from"] for l in tree["links"] if l["to"] == n["id"]] for n in tree["nodes"]}
    depth: dict[str, int] = {}

    def visit(i, seen=()):
        if i in depth:
            return depth[i]
        if i in seen:
            return 0
        depth[i] = max((visit(f, (*seen, i)) + 1 for f in into.get(i, [])), default=0)
        return depth[i]

    rows: dict[int, int] = {}
    pos = {}
    for n in tree["nodes"]:
        c = visit(n["id"])
        pos[n["id"]] = (c * GAP_X, -rows.get(c, 0) * GAP_Y)
        rows[c] = rows.get(c, 0) + 1
    return pos


def socket_names() -> dict[str, str]:
    """Every socket's Chinese name → its English one, over the whole catalog (几何数据 → Geometry): for the
    nodes whose sockets appear only once built (group input/output, zones)."""
    out: dict[str, str] = {}
    for node in knowledge.blender()["nodes"]:
        for s in node["inputs"] + node["outputs"]:
            out.setdefault(s["zh"], s["name"])
    return out


def _socket_ref(node: dict, side: str, name: str, used: dict) -> tuple[str, int] | None:
    """(English name, which one of that name) for a socket the graph names in Chinese or English; a second
    link to 「值」 on a Math node goes to its second Value; a group's or zone's socket by the catalog-wide name."""
    sockets = node.get(side) or []
    names = [s for s in sockets if s["name"] == name or s.get("en") == name]
    if not names:
        if str(node.get("ref") or "").startswith(("NodeGroup", "GeometryNodeSimulation", "GeometryNodeRepeat", "GeometryNodeForeach")):
            en = socket_names().get(name) or (name if name.isascii() else None)
            return (en, 0) if en else None
        return None
    en = names[0].get("en") or names[0]["name"]
    same = [s for s in sockets if (s.get("en") or s["name"]) == en]
    if len(same) > 1 and sum(1 for s in same if s["name"] == names[0]["name"]) == 1:  # 吸附's 增量: the second 矢量, by its label
        return en, same.index(names[0])
    k = used.get((node["id"], side, en), 0)
    count = len(same)
    if side == "inputs":
        used[(node["id"], side, en)] = k + 1
    return en, min(k, count - 1) if side == "inputs" else 0


def _option(ref: dict, param: dict) -> tuple[str, str] | None:
    """(property, id) for a setting that is one of the node's options: 运算=循环 → ("operation", "WRAP")."""
    for prop, option in (ref.get("options") or {}).items():
        if param["name"] in (option["zh"], option["label"]) or (prop == "operation" and param["name"] in ("运算", "Operation")):
            item = next((i for i in option["items"] if param["value"] in (i["zh"], i["name"])), None)
            if item:
                return prop, item["id"]
    return None


def owned_name(tree_name: str) -> str:
    """The name the script gives what it makes in Blender (the modifier, the material): applying again
    replaces it instead of piling up another, and 对答案 finds it among the person's own (zhenxun_bridge)."""
    return "帧寻·" + re.sub(r"\s+", " ", tree_name).strip()[:14]


def script(recipe: dict) -> str:
    catalog = knowledge.blender()
    lines = [
        f"# 帧寻 · 抄作业：{recipe.get('goal') or ''}",
        f"# 视频里用的是 {recipe.get('software') or 'Blender'} {recipe.get('version') or ''}；节点按 Blender {catalog['version']} 的目录生成，4.x / 5.0 可用。",
        "# 用法：Blender → Scripting → 新建文本 → 粘贴 → 运行脚本。几何节点会加到当前选中物体的修改器上。",
        "# 「# 手动」开头的注释是脚本没法替你做、需要照着视频手动补的地方。",
        "import bpy",
        "import math",
        "",
        "def sock(collection, name, index=0):",
        "    found = [s for s in collection if s.name == name or s.identifier == name]",
        "    return found[index] if len(found) > index else None",
        "",
        "def add(tree, kind, x, y, title):",
        "    try:",
        "        node = tree.nodes.new(kind)",
        "    except RuntimeError as error:  # not a node of this Blender: say so and go on",
        "        print('手动：没能添加「' + title + '」', error)",
        "        return None",
        "    node.location = (x, y)",
        "    return node",
        "",
        "def put(node, name, value, index=0):",
        "    s = sock(node.inputs, name, index) if node is not None else None",
        "    if s is not None and hasattr(s, 'default_value'):",
        "        s.default_value = value",
        "",
        "def put_at(node, index, value):",
        "    if node is not None and len(node.inputs) > index:",
        "        node.inputs[index].default_value = value",
        "",
        "def attr(node, key, value):",
        "    if node is not None and hasattr(node, key):",
        "        setattr(node, key, value)",
        "",
        "def link(tree, a, out, ai, b, into, bi):",
        "    if a is not None and b is not None:",
        "        x, y = sock(a.outputs, out, ai), sock(b.inputs, into, bi)",
        "        if x is not None and y is not None:",
        "            tree.links.new(x, y)",
        "",
    ]
    layouts = recipe.get("layout") or {}
    for t_index, tree in enumerate(recipe.get("trees") or []):
        kind = _kind(tree["name"])
        name = json.dumps(tree["name"], ensure_ascii=False)
        lines.append(f"# ---- {tree['name']} ----")
        if kind == "compositor":
            lines.append("# 手动：合成器节点树没有生成，请照着画布手动添加。")
            continue
        owned = json.dumps(owned_name(tree["name"]), ensure_ascii=False)
        if kind == "geometry":  # the 帧寻 modifier is reused: applying again swaps its node group, adds nothing
            lines += [f"tree = bpy.data.node_groups.new({name}, 'GeometryNodeTree')",
                      "tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')",
                      "tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')",
                      "obj = bpy.context.object",
                      "if obj is not None:",
                      f"    mod = obj.modifiers.get({owned}) or obj.modifiers.new({owned}, 'NODES')",
                      "    mod.node_group = tree"]
        elif kind == "material":  # the 帧寻 material is rebuilt in place and made the active one
            lines += [f"mat = bpy.data.materials.get({owned}) or bpy.data.materials.new({owned})", "mat.use_nodes = True",
                      "tree = mat.node_tree", "tree.nodes.clear()",
                      "obj = bpy.context.object",
                      "if obj is not None and hasattr(obj.data, 'materials'):",
                      "    if mat.name not in obj.data.materials:",
                      "        obj.data.materials.append(mat)",
                      "    obj.active_material_index = list(obj.data.materials).index(mat)"]
        else:
            lines += ["world = bpy.context.scene.world or bpy.data.worlds.new('World')", "bpy.context.scene.world = world",
                      "world.use_nodes = True", "tree = world.node_tree", "tree.nodes.clear()"]
        lines.append("n = {}")
        pos = _layout(tree, layouts.get(str(t_index)) or {})
        made = set()
        zones: dict[str, list[str]] = {}
        for node in tree["nodes"]:
            ref = catalog["by_id"].get(node.get("ref") or "")
            key = json.dumps(node["id"])
            if ref is None:
                why = f"Blender {node['legacy']} 的旧节点，新版本用 {node.get('replaced_by')}" if node.get("legacy") else "不在 Blender 自带节点里（可能来自插件）"
                lines.append(f"# 手动：「{node['name']}」{why}，没有生成。")
                continue
            made.add(node["id"])
            x, y = pos.get(node["id"], (0, 0))
            lines.append(f"n[{key}] = add(tree, '{ref['id']}', {round(x)}, {round(y)}, {json.dumps(node['name'], ensure_ascii=False)})")
            if ref["id"].endswith(("SimulationInput", "RepeatInput", "ForeachGeometryElementInput")):
                zones.setdefault(ref["id"].replace("Input", ""), []).append(node["id"])
            if ref["id"].endswith(("SimulationOutput", "RepeatOutput", "ForeachGeometryElementOutput")):
                zones.setdefault(ref["id"].replace("Output", ""), []).append(node["id"])
            sockets = {s["name"]: s for s in node.get("inputs") or []}
            for p in node.get("params") or []:
                option = _option(ref, p)
                if option:
                    lines.append(f"attr(n[{key}], '{option[0]}', '{option[1]}')")
                    continue
                flag = FLAGS.get(p["name"].lower())
                if flag and ref["id"] == "ShaderNodeMath" and (TRUE.match(str(p["value"]).strip()) or FALSE.match(str(p["value"]).strip())):
                    lines.append(f"attr(n[{key}], '{flag}', {bool(TRUE.match(str(p['value']).strip()))})")
                    continue
                slot = MATH_SLOTS.get(p["name"].lower()) if ref["id"] in ("ShaderNodeMath", "ShaderNodeVectorMath") else None
                number = _number(str(p["value"])) if "待确认" not in str(p["value"]) else None
                if slot is not None and number is not None:
                    if ref["id"] == "ShaderNodeVectorMath":  # its inputs are vectors: 0, 0, 0.2 (one number fills all three)
                        parts = [float(x) for x in NUMBER.findall(str(p["value"]))]
                        number = parts * 3 if len(parts) == 1 else (parts + [0.0, 0.0])[:3]
                    lines.append(f"put_at(n[{key}], {slot}, {number!r})")
                    continue
                if p["name"] not in sockets and p["name"].isascii() and number is not None:  # a socket shown only in some modes (Epsilon)
                    lines.append(f"put(n[{key}], {json.dumps(p['name'])}, {number!r})")
                    continue
                s = sockets.get(p["name"]) or next((x for x in node.get("inputs") or [] if x.get("en") == p["name"]), None)
                value = _value(s, p["value"]) if s else None
                if value is None:
                    lines.append(f"# 手动：「{node['name']}」的「{p['name']}」= {p['value']}")
                    continue
                lines.append(f"put(n[{key}], {json.dumps(s.get('en') or s['name'])}, {value!r})")
        for node in tree["nodes"]:  # a Switch that carries geometry is set to it (its default type may differ)
            if node["id"] in made and node.get("ref") == "GeometryNodeSwitch":
                ends = [l for l in tree["links"] if node["id"] in (l["from"], l["to"])]
                if any("几何" in (l["out"] + l["in"]) or "Geometry" in (l["out"] + l["in"]) for l in ends):
                    lines.append(f"attr(n[{json.dumps(node['id'])}], 'input_type', 'GEOMETRY')")
        refs = {n["id"]: n.get("ref") or "" for n in tree["nodes"]}
        for pair in zones.values():
            if len(pair) == 2:
                first, second = sorted(pair, key=lambda i: not refs[i].endswith("Input"))  # input pairs with output
                a, b = json.dumps(first), json.dumps(second)
                lines.append(f"if n[{a}] is not None and n[{b}] is not None: n[{a}].pair_with_output(n[{b}])")
        by_id = {n["id"]: n for n in tree["nodes"]}
        used: dict = {}
        for l in tree["links"]:
            if l["from"] not in made or l["to"] not in made:
                continue
            a = _socket_ref(by_id[l["from"]], "outputs", l["out"], used)
            b = _socket_ref(by_id[l["to"]], "inputs", l["in"], used)
            if a is None or b is None:
                lines.append(f"# 手动：连线 {by_id[l['from']]['name']}.{l['out']} → {by_id[l['to']]['name']}.{l['in']}")
                continue
            note = "  # 推断的连线，请对照视频确认" if l.get("inferred") else ""
            lines.append(f"link(tree, n[{json.dumps(l['from'])}], {json.dumps(a[0])}, {a[1]}, n[{json.dumps(l['to'])}], {json.dumps(b[0])}, {b[1]}){note}")
        lines.append("")
    lines.append("print('帧寻：节点已生成')")
    return "\n".join(lines) + "\n"
