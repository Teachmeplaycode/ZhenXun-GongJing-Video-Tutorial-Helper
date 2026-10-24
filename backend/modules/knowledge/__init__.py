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


@lru_cache(maxsize=1)
def blender() -> dict:
    data = json.loads(CATALOG.read_text())
    by_name: dict[str, list[dict]] = {}
    for node in data["nodes"]:
        for name in {node["label"], node["zh"], node["id"]}:
            by_name.setdefault(_key(name), []).append(node)
    return {"version": data["blender"], "nodes": data["nodes"], "by_name": by_name}


def match(name: str, en: str = "", tree: str = "") -> dict | None:
    """The Blender node these names mean: exact English, Chinese or id first, then a close spelling.
    `tree` (几何/着色器/世界/材质…) breaks ties between same-named nodes of different trees."""
    catalog = blender()
    kind = "shader" if re.search(r"着色|材质|世界|shader|material|world", tree or "", re.I) else \
        "compositor" if re.search(r"合成|compositor", tree or "", re.I) else "geometry"
    for candidate in (en, name):
        found = catalog["by_name"].get(_key(candidate))
        if found:
            return next((n for n in found if kind in n["trees"]), found[0])
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
