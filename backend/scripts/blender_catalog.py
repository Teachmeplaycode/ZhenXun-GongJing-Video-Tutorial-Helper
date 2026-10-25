"""Rebuild modules/knowledge/blender_nodes.json: every geometry, shader and compositor node Blender has,
its sockets and their defaults, with Chinese names from Blender's own translation (zh_HANS.po).

    uv venv -p 3.11 /tmp/bpy && uv pip install -p /tmp/bpy/bin/python bpy        # Blender as a Python module
    /tmp/bpy/bin/python scripts/blender_catalog.py dump /tmp/nodes.json
    curl -L -o /tmp/zh_HANS.po https://projects.blender.org/blender/blender/raw/branch/main/locale/po/zh_HANS.po
    python scripts/blender_catalog.py zh /tmp/nodes.json /tmp/zh_HANS.po modules/knowledge/blender_nodes.json
    /tmp/bpy/bin/python scripts/blender_catalog.py ops modules/knowledge/blender_nodes.json /tmp/zh_HANS.po

`ops` adds, to each operation of Math, Vector Math, Compare…, the sockets that operation shows: Snap's
second vector is 「增量」, Dot Product gives a 「值」 — the node's own sockets are Add's only.
"""
from __future__ import annotations

import json
import re
import sys


OPTION_ENUMS = ("operation", "data_type", "mode", "input_type", "blend_type", "clamp_type", "interpolation_type")


def dump(out: str) -> None:
    import bpy

    def default(sock):
        v = getattr(sock, "default_value", None)
        if v is None:
            return None
        try:
            if hasattr(v, "__len__") and not isinstance(v, str):
                return [round(x, 4) for x in v]
            return round(v, 4) if isinstance(v, float) else v
        except Exception:  # noqa: BLE001 — a socket whose value can't be read has no default here
            return None

    def sockets(items):
        return [{"name": s.name, "zh": s.name, "type": s.bl_idname.replace("NodeSocket", ""), "default": default(s)}
                for s in items if s.enabled and s.bl_idname != "NodeSocketVirtual"]

    nodes: dict[str, dict] = {}
    for tree_type, kind in {"GeometryNodeTree": "geometry", "ShaderNodeTree": "shader", "CompositorNodeTree": "compositor"}.items():
        tree = bpy.data.node_groups.new("t", tree_type)
        for name in dir(bpy.types):
            cls = getattr(bpy.types, name)
            if not (isinstance(cls, type) and issubclass(cls, bpy.types.Node)) or name in ("Node", "NodeInternal"):
                continue
            try:
                node = tree.nodes.new(name)
            except Exception:  # noqa: BLE001 — not a node of this tree
                continue
            entry = nodes.setdefault(name, {"id": name, "label": node.bl_label, "zh": node.bl_label, "trees": [],
                                            "inputs": sockets(node.inputs), "outputs": sockets(node.outputs)})
            options = {p.identifier: {"label": p.name, "zh": p.name, "items": [{"id": i.identifier, "name": i.name, "zh": i.name} for i in p.enum_items]}
                       for p in node.bl_rna.properties
                       if p.type == "ENUM" and not p.is_readonly and p.identifier in OPTION_ENUMS}
            if options:  # a Math node's title is its operation (循环, 取模…): these are how it is recognised
                entry["options"] = options
            entry["trees"].append(kind)
            tree.nodes.remove(node)
    with open(out, "w") as f:
        json.dump({"blender": bpy.app.version_string, "nodes": sorted(nodes.values(), key=lambda n: n["id"])}, f, ensure_ascii=False)
    print(len(nodes), "nodes")


def parse_po(path: str) -> dict[str, dict[str, str]]:
    """msgid → {context: msgstr}, fuzzy entries left out."""
    table: dict[str, dict[str, str]] = {}
    entry: dict[str, str] = {}
    field = None

    def flush():
        if entry.get("msgid") and entry.get("msgstr") and "fuzzy" not in entry.get("flags", ""):
            table.setdefault(entry["msgid"], {})[entry.get("msgctxt") or "*"] = entry["msgstr"]

    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            flush()
            entry, field = {}, None
        elif line.startswith("#,"):
            entry["flags"] = line
        elif line.startswith("#"):
            continue
        elif m := re.match(r'(msgctxt|msgid|msgstr) "(.*)"$', line):
            field = m.group(1)
            entry[field] = m.group(2)
        elif line.startswith('"') and field:
            entry[field] += line[1:-1]
    flush()
    return table


def add_chinese(nodes_path: str, po_path: str, out: str) -> None:
    table = parse_po(po_path)

    def zh(text: str) -> str:
        options = table.get(text) or {}
        for context in ("*", "NodeTree", "Operator", "ID"):
            if context in options:
                return options[context]
        return next(iter(options.values()), text)

    data = json.load(open(nodes_path))
    for node in data["nodes"]:
        node["zh"] = zh(node["label"])
        for s in node["inputs"] + node["outputs"]:
            s["zh"] = zh(s["name"])
        for option in (node.get("options") or {}).values():
            option["zh"] = zh(option["label"])
            for item in option["items"]:
                item["zh"] = zh(item["name"])
    with open(out, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(sum(n["zh"] == n["label"] for n in data["nodes"]), "of", len(data["nodes"]), "labels without a translation")


PER_OPERATION = ("ShaderNodeMath", "ShaderNodeVectorMath", "FunctionNodeCompare", "FunctionNodeBooleanMath",
                 "FunctionNodeIntegerMath")


def operation_sockets(catalog: str, po_path: str) -> None:
    import bpy

    table = parse_po(po_path)

    def zh(text: str) -> str:
        options = table.get(text) or {}
        return next((options[c] for c in ("*", "NodeTree") if c in options), next(iter(options.values()), text))

    def sockets(items):  # the same name twice (Math's 值, 值, 值) stays in order: links count on it
        return [{"name": s.name, "zh": zh(s.name), "type": s.bl_idname.replace("NodeSocket", "")}
                for s in items if s.enabled and s.bl_idname != "NodeSocketVirtual"]

    data = json.load(open(catalog))
    tree = bpy.data.node_groups.new("t", "GeometryNodeTree")
    for entry in data["nodes"]:
        if entry["id"] not in PER_OPERATION or "operation" not in (entry.get("options") or {}):
            continue
        node = tree.nodes.new(entry["id"])
        for item in entry["options"]["operation"]["items"]:
            for data_type in ("", "FLOAT", "RGBA"):  # Compare's 更亮/更暗 are colour operations only
                try:
                    if data_type:
                        node.data_type = data_type
                    node.operation = item["id"]
                    break
                except TypeError:
                    continue
            item["inputs"], item["outputs"] = sockets(node.inputs), sockets(node.outputs)
        tree.nodes.remove(node)
    with open(catalog, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print("per-operation sockets for", ", ".join(PER_OPERATION))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if args[0] == "dump":
        dump(args[1])
    elif args[0] == "ops":
        operation_sockets(args[1], args[2])
    else:
        add_chinese(*args[1:4])
