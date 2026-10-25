"""对答案: the person's node tree, read from their Blender, against the 抄作业 graph.

Nodes are matched by type, and by operation for Math-like nodes (a Wrap Math isn't an Add Math); several
of one type pair up in order. Then: nodes the answer has and the person doesn't, nodes the person has
extra, links missing or extra (by node type and socket name, so names and positions don't matter), and
settings that differ from what the tutorial set (the values the answer could read; 待确认 ones aren't
judged). Every finding says what to do in the person's words.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .. import knowledge
from .. import recipe_script

TOLERANCE = 1e-3


def _op_id(node: dict) -> str:
    """The operation id the answer's node is set to (运算=循环 → WRAP), '' when none."""
    ref = knowledge.blender()["by_id"].get(node.get("ref") or "")
    if not ref:
        return ""
    for p in node.get("params") or []:
        found = recipe_script._option(ref, p)
        if found and found[0] == "operation":
            return found[1]
    return ""


def _key_answer(node: dict) -> str:
    op = _op_id(node)
    return f"{node.get('ref')}:{op}" if op else str(node.get("ref"))


def _key_theirs(node: dict) -> str:
    return f"{node['bl_idname']}:{node['operation']}" if node.get("operation") and node["bl_idname"] in knowledge.TITLED_BY_OPERATION else node["bl_idname"]


def _close(a, b) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    try:
        return math.isclose(float(a), float(b), rel_tol=TOLERANCE, abs_tol=TOLERANCE)
    except (TypeError, ValueError):
        return a == b


def _show(value) -> str:
    if isinstance(value, (list, tuple)):
        return "(" + ", ".join(_show(v) for v in value) + ")"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def compare(tree: dict, theirs: dict) -> dict:
    """One answer tree against the person's exported tree (zhenxun_bridge.export_tree)."""
    ours = [n for n in tree["nodes"] if n.get("ref")]
    unknown = [n["name"] for n in tree["nodes"] if not n.get("ref")]
    pool: dict[str, list[dict]] = defaultdict(list)
    for n in theirs["nodes"]:
        if n["bl_idname"] != "NodeFrame":
            pool[_key_theirs(n)].append(n)
    pair: dict[str, dict] = {}  # answer node id → their node
    missing = []
    for n in ours:
        key = _key_answer(n)
        candidates = pool.get(key)
        if not candidates:  # an operation on one side only (the answer didn't say; Blender's default is 相加): same type will do
            candidates = next((group for k, group in pool.items() if group and k.split(":")[0] == str(n["ref"])), None)
        if candidates:
            pair[n["id"]] = candidates.pop(0)
        else:
            missing.append(n)
    extra = [n for group in pool.values() for n in group]
    title = {n["id"]: n.get("title") or n["name"] for n in tree["nodes"]}

    # links, by the matched node on their side and the English socket name
    used: dict = {}
    want = []
    by_id = {n["id"]: n for n in tree["nodes"]}
    for l in tree["links"]:
        if l["from"] not in pair or l["to"] not in pair:
            continue
        a = recipe_script._socket_ref(by_id[l["from"]], "outputs", l["out"], used)
        b = recipe_script._socket_ref(by_id[l["to"]], "inputs", l["in"], used)
        if a and b:
            want.append(((pair[l["from"]]["name"], a[0], pair[l["to"]]["name"], b[0]), l))
    have = {(x["from"], x["out"], x["to"], x["in"]) for x in theirs["links"]}
    wanted_keys = {k for k, _ in want}
    # two answer links into one socket that takes a single link (the answer contradicts itself): one present is enough
    filled = {(k[2], k[3]) for k in wanted_keys if k in have}
    multi = {"GeometryNodeJoinGeometry"}  # its Geometry input takes many
    kinds = {n["name"]: n["bl_idname"] for n in theirs["nodes"]}
    links_missing = [l for k, l in want if k not in have and not ((k[2], k[3]) in filled and kinds.get(k[2]) not in multi)]
    wanted = {k for k, _ in want}
    matched_names = {n["name"] for n in pair.values()}
    links_extra = [x for x in theirs["links"] if (x["from"], x["out"], x["to"], x["in"]) not in wanted
                   and x["from"] in matched_names and x["to"] in matched_names]

    # settings the tutorial changed and the answer could read
    settings = []
    for n in ours:
        mine = pair.get(n["id"])
        if not mine:
            continue
        sockets = {s["name"]: s for s in n.get("inputs") or []}
        theirs_inputs = mine.get("inputs") or []
        for p in n.get("params") or []:
            slot = recipe_script.MATH_SLOTS.get(p["name"].lower()) if n.get("ref") in ("ShaderNodeMath", "ShaderNodeVectorMath") else None
            if slot is not None:  # Wrap's 最大值 / 最小值: Math's second and third Value
                number = recipe_script._number(str(p["value"])) if "待确认" not in str(p["value"]) else None
                got = theirs_inputs[slot] if slot < len(theirs_inputs) else None
                if number is not None and got and not got.get("linked") and "value" in got and not _close(number, got["value"]):
                    settings.append({"node": title[n["id"]], "setting": p["name"], "want": _show(number), "got": _show(got["value"]), "time": p.get("time")})
                continue
            s = sockets.get(p["name"])
            if s is None:
                continue
            value = recipe_script._value(s, p["value"])
            if value is None:
                continue
            en = s.get("en") or s["name"]
            got = next((x for x in theirs_inputs if x["name"] == en and not x.get("linked")), None)
            if got is None or "value" not in got:
                continue
            if not _close(value, got["value"]):
                settings.append({"node": title[n["id"]], "setting": p["name"], "want": _show(value), "got": _show(got["value"]), "time": p.get("time")})

    findings = []
    for n in missing:
        findings.append({"kind": "missing_node", "node": n["id"], "text": f"少了节点「{title[n['id']]}」：Shift+A 搜「{n['name']}」添加",
                         "time": n.get("time")})
    for l in links_missing:
        findings.append({"kind": "missing_link", "text": f"缺一根线：{title[l['from']]}.{l['out']} → {title[l['to']]}.{l['in']}",
                         "from": l["from"], "to": l["to"], "time": l.get("time")})
    for s in settings:
        findings.append({"kind": "setting", "text": f"「{s['node']}」的「{s['setting']}」应为 {s['want']}，你的是 {s['got']}", "time": s["time"]})
    for x in links_extra:
        findings.append({"kind": "extra_link", "text": f"多了一根线：{x['from']}.{x['out']} → {x['to']}.{x['in']}（教程里没有，检查是不是接错口了）"})
    for n in extra:
        findings.append({"kind": "extra_node", "text": f"多了节点「{n.get('label') or n['name']}」（教程里没有，不影响就可以留着）"})
    wrong = len(missing) + len(links_missing) + len(settings)
    return {"tree": tree["name"], "theirs": theirs.get("name"), "matched": len(pair), "nodes": len(ours),
            "links": len(want), "findings": findings, "unknown": unknown,
            "done": wrong == 0, "summary": "全部对上了" if wrong == 0 else
            f"还差 {len(missing)} 个节点、{len(links_missing)} 根线、{len(settings)} 处参数"}
