"""What the software itself says: node catalogs the model's readings are checked against.

blender_nodes.json (scripts/blender_catalog.py) lists every geometry, shader and compositor node of
Blender 5.0 with its sockets and defaults, in English and in Blender's own Chinese. A node the model
names (噪波纹理, Noise Texture, "noise texture") is matched to its entry, so the drawing shows every
socket the real node has and a name that isn't a Blender node is left as the model said it.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

CATALOG = Path(__file__).with_name("blender_nodes.json")
LEGACY = Path(__file__).with_name("blender_legacy.json")  # 2.93's attribute / point nodes, gone since 3.0
CLOSE = 0.92  # similarity a fuzzy name needs to count as that node (Mesh to SDF Volume ≠ Mesh to Volume at 0.89)
TREES = {"geometry": "几何节点", "shader": "着色器", "compositor": "合成器"}


def _key(text: str) -> str:
    return re.sub(r"[\s_\-()（）·.]+", "", (text or "").lower())


@lru_cache(maxsize=1)
def legacy() -> dict:
    data = json.loads(LEGACY.read_text())
    by_name: dict[str, list[dict]] = {}
    for node in data["nodes"]:
        for name in {node["label"], node["zh"], node["id"], *node.get("aliases", [])}:
            by_name.setdefault(_key(name), []).append(node)
    return {"version": data["blender"], "nodes": data["nodes"], "by_name": by_name}


# Nodes whose title in the editor is the chosen operation (循环, 取模, 等于…), not the node's name.
TITLED_BY_OPERATION = ("ShaderNodeMath", "ShaderNodeVectorMath", "FunctionNodeCompare", "FunctionNodeBooleanMath",
                       "FunctionNodeIntegerMath")
# A zone is two nodes both titled like this in the editor; the first one met is the input.
ZONES = {"模拟": ("GeometryNodeSimulationInput", "GeometryNodeSimulationOutput"),
         "simulation": ("GeometryNodeSimulationInput", "GeometryNodeSimulationOutput"),
         "重复": ("GeometryNodeRepeatInput", "GeometryNodeRepeatOutput"),
         "repeat": ("GeometryNodeRepeatInput", "GeometryNodeRepeatOutput"),
         "逐元素": ("GeometryNodeForeachGeometryElementInput", "GeometryNodeForeachGeometryElementOutput")}


@lru_cache(maxsize=1)
def blender() -> dict:
    data = json.loads(CATALOG.read_text())
    by_name: dict[str, list[dict]] = {}
    by_id = {n["id"]: n for n in data["nodes"]}
    operations: dict[str, tuple[dict, dict]] = {}
    for node in data["nodes"]:
        for name in {node["label"], node["zh"], node["id"]}:
            by_name.setdefault(_key(name), []).append(node)
    for nid in TITLED_BY_OPERATION:  # earlier ones win: 相加 is Math's before Vector Math's
        for item in ((by_id.get(nid) or {}).get("options") or {}).get("operation", {}).get("items", []):
            for name in (item["zh"], item["name"]):
                operations.setdefault(_key(name), (by_id[nid], item))
    return {"version": data["blender"], "nodes": data["nodes"], "by_name": by_name, "by_id": by_id, "operations": operations}


def operation(name: str) -> tuple[dict, dict] | None:
    """(node, operation item) when a title is an operation's name: 循环 → Math set to Wrap."""
    key = _key(name)
    if not key or key in blender()["by_name"]:  # a node's own name (混合 is Mix) wins
        return None
    return blender()["operations"].get(key)


def match(name: str, en: str = "", tree: str = "") -> dict | None:
    """The Blender node these names mean: exact English, Chinese or id first, then a close spelling.
    `tree` (几何/着色器/世界/材质…) breaks ties between same-named nodes of different trees."""
    catalog = blender()
    kind = "shader" if re.search(r"着色|材质|世界|shader|material|world", tree or "", re.I) else \
        "compositor" if re.search(r"合成|compositor", tree or "", re.I) else "geometry"
    for candidate in (en, name):
        found = catalog["by_name"].get(_key(candidate))
        if found and any(kind in n["trees"] for n in found):
            return next(n for n in found if kind in n["trees"])
    for candidate in (name, en):  # 「变换」 in a geometry tree is 变换几何体, not the compositor's 变换
        k = _key(candidate)
        if len(k) >= 2:
            longer = [n for n in catalog["nodes"] if kind in n["trees"] and _key(n["zh"]).startswith(k)]
            if longer:  # one that takes geometry first (变换 → 变换几何体, not 变换点), then the shortest
                return min(longer, key=lambda n: (not any(x["type"].startswith("Geometry") for x in n["inputs"]), len(n["zh"])))
    for candidate in (en, name):
        found = catalog["by_name"].get(_key(candidate))
        if found:
            return found[0]
    for candidate in (en, name):  # a 2.9x tutorial's node that Blender has since replaced
        found = legacy()["by_name"].get(_key(candidate))
        if found and kind == "geometry":
            return found[0]
    best, score = None, 0.0
    for candidate in (en, name):
        k = _key(candidate)
        if len(k) < 3:
            continue
        for key, nodes in catalog["by_name"].items():
            s = SequenceMatcher(None, k, key).ratio()
            if s > score:
                best, score = nodes[0], s
    return best if score >= CLOSE else None


def vocabulary(kinds=("geometry", "shader")) -> str:
    """Node names as Blender's Chinese interface shows them, with the English: for the model to name nodes by."""
    return "、".join(f"{n['zh']}({n['label']})" for n in blender()["nodes"] if set(n["trees"]) & set(kinds))


def lookup(name: str) -> dict | None:
    """What Blender itself says about a name the person or the video used: an operation (循环 is Math
    set to Wrap), a node of 5.0 (its tree, sockets), a 2.9x node and what replaced it; None when Blender
    has no such thing built in (likely an add-on or extension)."""
    op = operation(name)
    if op:
        node, item = op
        return {"kind": "operation", "zh": item["zh"], "en": item["name"], "node": node["zh"], "node_en": node["label"], "id": node["id"]}
    key = _key(name)
    found = blender()["by_name"].get(key) or legacy()["by_name"].get(key)
    if not found:
        found = [n] if (n := match(name, name)) else []
    if not found:
        return None
    n = found[0]
    out = {"kind": "legacy" if n.get("era") else "node", "zh": n["zh"], "en": n["label"], "id": n["id"],
           "trees": [TREES.get(t, t) for t in n["trees"]],
           "inputs": [s["zh"] for s in n["inputs"]], "outputs": [s["zh"] for s in n["outputs"]]}
    if n.get("era"):
        out |= {"era": n["era"], "replaced_by": n["replaced_by"]}
    return out
