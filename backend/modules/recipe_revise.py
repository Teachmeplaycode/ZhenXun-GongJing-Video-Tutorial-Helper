"""AI 修改: the 抄作业 graph fixed with the model, round after round, the way a person with Blender would.

One pass over a tutorial misses nodes (a custom node group, a link off-screen). Here the model gets the graph,
what is still wrong with it (problems(): nodes nothing reaches, sockets that don't exist, geometry that goes
nowhere), the tutorial's speech and screen text, and tools: look at a few seconds again (sharp, the editor
cropped), read what was said, look a node up in Blender's catalog, edit the graph, and — when the person's
Blender is connected (modules/blender) — build it there and see whether every link is valid and geometry
comes out. It stops when it says it is done or after MAX_ROUNDS. Each revision keeps the version before it.
"""
from __future__ import annotations

import base64
import dataclasses
import json
import time
from pathlib import Path

from . import knowledge, recipe, recipe_script
from . import steps as step_cards

MAX_ROUNDS = 14
VIEW_MAX = 3
LOOK_BUDGET = 4  # view_frames / read_material calls before only edit, lookup and check are left: it must act
LOOKUP_BUDGET = 8
VERSIONS = "recipe_versions"

SYSTEM = """你在修改一个 Blender 节点教程的「抄作业」节点图，目标是让它和视频里最终的节点图一模一样、在 Blender 里能直接跑出视频的效果。
做法：先根据「还有的问题」和画面直接用 edit 修能确定的部分（一次可以给多个操作）；不确定的地方再用 view_frames 看那几秒的高清画面（节点编辑器会裁出来放大），用 read_material 读那段语音和画面文字；
用 edit 修改（加节点、删节点、改参数、连线、断线），每次修改后会告诉你还剩哪些问题；连上了 Blender 时用 check_blender 真的建一遍，看连线是否有效、有没有输出几何，还会给你一张效果图：和视频里的成品效果对比，不像就继续找错。
规则：节点名用 Blender 中文界面的名字（不认识就 lookup_software）；口名照抄节点真实的输入输出口；作者自制的节点组用 Blender 自带节点实现同样的功能（比如「选择法向」= 法向 + 矢量运算点乘 + 比较）；
看不到、听不到的不要编，留着并在最后说明。改完了就直接回复一段中文总结（改了什么、还有什么需要用户确认），不要再调用工具。"""

TOOLS = [
    {"type": "function", "function": {"name": "view_frames", "description": f"看视频某几秒的高清画面（最多 {VIEW_MAX} 个时间点），节点编辑器会自动裁出来放大",
                                      "parameters": {"type": "object", "properties": {"times": {"type": "array", "items": {"type": "number"}, "description": "秒数"}}, "required": ["times"]}}},
    {"type": "function", "function": {"name": "read_material", "description": "读某段时间的语音和画面文字",
                                      "parameters": {"type": "object", "properties": {"start": {"type": "number"}, "end": {"type": "number"}}, "required": ["start", "end"]}}},
    {"type": "function", "function": {"name": "lookup_software", "description": "查 Blender 自带节点/运算：英文名、节点树、输入输出口；查不到说明不是自带的",
                                      "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "edit", "description": "修改节点图。ops 是操作列表，每个操作是下列之一："
                                      "{op:add_node,id,name,en?,params?:[{name,value}]}、{op:remove_node,id}、{op:set_param,id,name,value}、"
                                      "{op:add_link,from,out,to,in}、{op:remove_link,from,out,to,in}。节点 id 自己起，不要和已有的重复",
                                      "parameters": {"type": "object", "properties": {"ops": {"type": "array", "items": {"type": "object"}}}, "required": ["ops"]}}},
    {"type": "function", "function": {"name": "check_blender", "description": "在用户连接的 Blender 里按当前节点图建一遍，返回无效连线、建不出来的节点和输出几何的大小",
                                      "parameters": {"type": "object", "properties": {}}}},
]


def _title(n: dict) -> str:
    return n.get("title") or n["name"]


def problems(tree: dict) -> list[str]:
    """What is still wrong with a tree, in words the model and the person read alike."""
    out = []
    by_id = {n["id"]: n for n in tree["nodes"]}
    linked_in = {(l["to"], l["in"]) for l in tree["links"]}
    touched = {l["from"] for l in tree["links"]} | {l["to"] for l in tree["links"]}
    for n in tree["nodes"]:
        if not n.get("ref"):
            out.append(f"「{_title(n)}」({n['id']}) 不是 Blender 自带节点：换成自带节点实现，或确认是插件节点")
        if n["id"] not in touched and len(tree["nodes"]) > 1:
            out.append(f"「{_title(n)}」({n['id']}) 一根线都没连")
        elif n["id"] in touched and n["id"] not in {l["from"] for l in tree["links"]} and n.get("outputs") \
                and n.get("ref") not in ("NodeGroupOutput", "GeometryNodeViewer"):
            out.append(f"「{_title(n)}」({n['id']}) 的输出没有接到任何地方：视频里接到哪就补上，确实没用就删掉")
    for n in tree["nodes"]:  # a setting the node doesn't have but another does: likely the wrong node
        ref = knowledge.blender()["by_id"].get(n.get("ref") or "")
        if not ref or str(n["ref"]).startswith(("NodeGroup", "GeometryNodeSimulation", "GeometryNodeRepeat")):
            continue
        labels = {x for o in (ref.get("options") or {}).values() for x in (o["zh"], o["label"])} | {"运算", "Operation"}
        for p in n.get("params") or []:
            if p["name"] in labels or p["name"] in recipe_script.FLAGS or any(p["name"] in (s["name"], s.get("en")) for s in n.get("inputs") or []) \
                    or (n["ref"] in ("ShaderNodeMath", "ShaderNodeVectorMath") and p["name"].lower() in recipe_script.MATH_SLOTS):
                continue
            if not recipe_script.NUMBER.search(str(p["value"])):  # a word (类型=NURBS) is a property the catalog may not list
                continue
            where = knowledge.settings_named(p["name"])
            if where:
                out.append(f"「{_title(n)}」({n['id']}) 没有「{p['name']}」这个设置，可能认错了节点：有这个设置的是 {'、'.join(where[:5])}")
    for l in tree["links"]:
        a, b = by_id.get(l["from"]), by_id.get(l["to"])
        if a and a.get("ref") and not any(l["out"] in (s["name"], s.get("en")) for s in a.get("outputs") or []) \
                and not str(a.get("ref")).startswith(("NodeGroup", "GeometryNodeSimulation", "GeometryNodeRepeat")):
            out.append(f"连线 {_title(a)}.{l['out']} 的输出口不存在（可用：{'、'.join(s['name'] for s in a.get('outputs') or [])}）")
        if b and b.get("ref") and not any(l["in"] in (s["name"], s.get("en")) for s in b.get("inputs") or []) \
                and not str(b.get("ref")).startswith(("NodeGroup", "GeometryNodeSimulation", "GeometryNodeRepeat")):
            out.append(f"连线 → {_title(b)}.{l['in']} 的输入口不存在（可用：{'、'.join(s['name'] for s in b.get('inputs') or [])}）")
    for l in tree["links"]:  # geometry is only taken by a geometry socket, and gives nothing else
        a, b = by_id.get(l["from"]), by_id.get(l["to"])
        out_s = next((s for s in (a or {}).get("outputs") or [] if l["out"] in (s["name"], s.get("en"))), None)
        in_s = next((s for s in (b or {}).get("inputs") or [] if l["in"] in (s["name"], s.get("en"))), None)
        if out_s and in_s and out_s["type"].startswith("Geometry") != in_s["type"].startswith("Geometry"):
            out.append(f"连线 {_title(a)}.{l['out']} → {_title(b)}.{l['in']} 类型接不上：几何数据只能接几何数据口"
                       f"（{_title(b)}.{l['in']} 要的是{'几何数据' if in_s['type'].startswith('Geometry') else '数值/矢量/字段'}）")
    for n in tree["nodes"]:
        geo_in = [s for s in n.get("inputs") or [] if s["type"].startswith("Geometry")]
        if geo_in and n.get("ref") not in ("NodeGroupOutput",) and not any((n["id"], s["name"]) in linked_in for s in geo_in):
            out.append(f"「{_title(n)}」({n['id']}) 的几何数据输入没有接任何东西")
    feeds: dict[str, set] = {}
    for l in tree["links"]:
        feeds.setdefault(l["from"], set()).add(l["to"])
    looped = []  # links on a loop: following links from the target comes back to the source
    for l in tree["links"]:
        seen, todo = set(), [l["to"]]
        while todo:
            x = todo.pop()
            if x == l["from"]:
                looped.append(l)
                break
            if x not in seen:
                seen.add(x)
                todo += list(feeds.get(x, ()))
    if looped:
        name = lambda i: f"{_title(by_id[i])}({i})" if i in by_id else i  # noqa: E731
        out.append("这些连线连成了回路（几何节点不能有回路，拆掉不该有的那根）：" + "；".join(f"{name(l['from'])} → {name(l['to'])}" for l in looped[:8]))
    end = next((n for n in tree["nodes"] if n.get("ref") == "NodeGroupOutput"), None)
    if end and end["id"] not in {l["to"] for l in tree["links"]}:
        out.append("组输出没有接任何东西")
    return out


def apply_ops(tree: dict, ops: list[dict]) -> list[str]:
    """Edit the tree in place; one line per change (or why it was refused)."""
    done = []
    ids = {n["id"] for n in tree["nodes"]}
    for op in ops if isinstance(ops, list) else []:
        kind = op.get("op")
        if kind == "add_node":
            nid = str(op.get("id") or f"r{len(ids) + 1}")
            while nid in ids:
                nid += "x"
            tree["nodes"].append({"id": nid, "name": str(op.get("name") or "")[:30], "en": str(op.get("en") or "")[:40], "time": None,
                                  "params": [{"name": str(p.get("name")), "value": str(p.get("value")), "time": None} for p in op.get("params") or []]})
            ids.add(nid)
            done.append(f"加节点「{op.get('name')}」({nid})")
        elif kind == "remove_node" and op.get("id") in ids:
            tree["nodes"] = [n for n in tree["nodes"] if n["id"] != op["id"]]
            tree["links"] = [l for l in tree["links"] if op["id"] not in (l["from"], l["to"])]
            ids.discard(op["id"])
            done.append(f"删节点 {op['id']}")
        elif kind == "set_param" and op.get("id") in ids:
            node = next(n for n in tree["nodes"] if n["id"] == op["id"])
            param = next((p for p in node["params"] if p["name"] == op.get("name")), None)
            if param:
                param["value"] = str(op.get("value"))
            else:
                node["params"].append({"name": str(op.get("name")), "value": str(op.get("value")), "time": None})
            if op.get("name") in ("运算", "Operation"):
                node.pop("title", None)  # titled by its operation: the new one
            done.append(f"「{_title(node)}」的「{op.get('name')}」= {op.get('value')}")
        elif kind == "add_link" and op.get("from") in ids and op.get("to") in ids:
            link = {"from": op["from"], "out": str(op.get("out") or ""), "to": op["to"], "in": str(op.get("in") or ""), "time": None}
            if link not in tree["links"]:
                tree["links"].append(link)
            done.append(f"连线 {op['from']}.{op.get('out')} → {op['to']}.{op.get('in')}")
        elif kind == "remove_link":
            before = len(tree["links"])
            exact_hit = [l for l in tree["links"] if l["from"] == op.get("from") and l["to"] == op.get("to")
                         and (not op.get("out") or l["out"] == op.get("out")) and (not op.get("in") or l["in"] == op.get("in"))]
            hit = exact_hit or [l for l in tree["links"] if l["from"] == op.get("from") and l["to"] == op.get("to")]  # socket names off
            tree["links"] = [l for l in tree["links"] if l not in hit]
            done.append(f"断开 {op.get('from')} → {op.get('to')}" if len(tree["links"]) < before else f"没找到要断开的线 {op.get('from')} → {op.get('to')}")
        else:
            done.append(f"没执行：{json.dumps(op, ensure_ascii=False)[:120]}")
    # names, sockets and settings back onto the catalog (a new 「运算」 becomes Math, 几何体 becomes 几何数据)
    for n in tree["nodes"]:
        if not n.get("ref"):
            for key in ("inputs", "outputs", "ref", "title"):
                n.pop(key, None)
    recipe.normalize({"trees": [tree], "version_notes": []})
    return done


def describe(tree: dict) -> str:
    """The tree as the model edits it: ids, names, settings, links."""
    nodes = [{"id": n["id"], "name": _title(n), "en": n.get("en", ""), "params": {p["name"]: p["value"] for p in n["params"]},
              "inputs": [s["name"] for s in n.get("inputs") or []][:12], "outputs": [s["name"] for s in n.get("outputs") or []][:8]}
             for n in tree["nodes"]]
    links = [f"{l['from']}.{l['out']} → {l['to']}.{l['in']}" for l in tree["links"]]
    return json.dumps({"name": tree["name"], "nodes": nodes, "links": links}, ensure_ascii=False)


def save_version(root: Path, found: dict) -> None:
    folder = root / VERSIONS
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{int(time.time() * 1000)}.json").write_text(json.dumps(found, ensure_ascii=False))


def undo(root: Path) -> dict | None:
    folder = root / VERSIONS
    versions = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not versions:
        return None
    last = versions[-1]
    found = json.loads(last.read_text())
    recipe.save(root, found)
    last.unlink()
    return found


def model_client():
    """RECIPE_MODEL picks a stronger model for this than the chat's (the same key and endpoint); RECIPE_THINKING=1
    turns on DeepSeek's thinking (tried on the contour tutorial: three times slower, not better)."""
    from modules.llm import LLMConfig, create_client
    from modules.settings import settings

    config = LLMConfig.from_env()
    if settings().get("RECIPE_MODEL"):
        config = dataclasses.replace(config, model=settings()["RECIPE_MODEL"])
    return create_client(dataclasses.replace(config, thinking=settings().get("RECIPE_THINKING") == "1"))


def _image(path: Path) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()}}


async def revise(job, found: dict, index: int, instruction: str, llm, tools, blender_check=None) -> dict:
    """Run the loop on tree `index` of the saved graph `found`; returns the new graph and what happened.
    `tools`: AgentTools (sharp frames); `blender_check(tree) -> str`: builds the tree in the person's Blender."""
    from modules.llm import Usage, assistant_message, exact, tool_message

    tree = json.loads(json.dumps(found["trees"][index]))
    transcript = job.transcript.segments if job.transcript else []
    screen = job.screentext.segments if job.screentext else []
    cards = (step_cards.load(job.root) or {}).get("steps") or []
    folder = job.root / "recipe"
    crops = sorted(folder.glob("crop-*.jpg"))[-4:] if folder.is_dir() else []
    intro = [{"type": "text", "text": f"视频：{job.video.title}\n用户的要求：{instruction or '把漏掉的节点和连线补全，和视频最终节点图一致'}\n\n"
                                      f"当前节点图：{describe(tree)}\n\n还有的问题：\n" + ("\n".join(problems(tree)) or "（没检查出明显问题）")
                                      + ("\n\n看不清的地方：\n" + "\n".join(f"{u['text']}（{u.get('time')} 秒）" for u in found.get("unsure") or []) if found.get("unsure") else "")
                                      + ("\n\n操作步骤：\n" + "\n".join(f"[{int(s['time'])}s] {s['action']}" for s in cards) if cards else "")}]
    if crops:
        intro.append({"type": "text", "text": "之前抄录用过的几张节点编辑器画面："})
        intro += [_image(p) for p in crops]
    messages = [{"role": "system", "content": SYSTEM + "\n" + recipe.BLENDER_RULES}, {"role": "user", "content": intro}]
    changes, checks, summary, trace = [], [], "", []
    looked = lookups = 0
    pushed = shown_end = False
    circling = 0  # times it went back and forth: the third time it stops editing and sums up
    preview = ""  # the last picture Blender rendered, shown to the person too
    seen_edits: dict[str, int] = {}  # an edit made before: going back and forth
    asked: dict[str, str] = {}  # a call made before → its answer (models repeat themselves)
    for round_no in range(MAX_ROUNDS):
        usage = Usage()
        hidden = (("view_frames", "read_material") if looked >= LOOK_BUDGET else ()) + (("lookup_software",) if lookups >= LOOKUP_BUDGET else ())
        offered = [t for t in TOOLS if t["function"]["name"] not in hidden]
        if circling >= 3:
            messages.append({"role": "user", "content": "你已经来回改了好几次同样的地方，先停下：不要再调用工具，直接总结改了什么、哪里还拿不准。"})
            offered, pushed = None, True
        with exact():
            text = "".join([d async for d in llm.stream(messages, usage, max_tokens=16000, tools=offered)])
        if not usage.tool_calls:
            left = problems(tree)
            unchecked = blender_check and changes and not (trace and "check_blender" in trace[-1])
            if (left or unchecked) and not pushed:  # stopping with work left: once, say so
                pushed = True
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": "先别结束：" + ("还有这些问题：\n" + "\n".join(left) if left else "")
                              + ("\n改完还没在 Blender 里检查，用 check_blender 看一下" if unchecked else "")
                              + "\n能解决的继续用 edit 改；确实解决不了的，在总结里说明原因。"}]
                continue
            summary = text.strip()
            break
        messages.append(assistant_message(text, usage.tool_calls, usage.reasoning))
        pictures = []
        for call in usage.tool_calls:
            args = call.arguments or {}
            trace.append(f"{round_no + 1}. {call.name} {json.dumps(args, ensure_ascii=False)[:160]}")
            looked += call.name in ("view_frames", "read_material")
            lookups += call.name == "lookup_software"
            key = call.name + json.dumps(args, ensure_ascii=False, sort_keys=True)
            if call.name in ("lookup_software", "read_material", "view_frames") and key in asked:
                messages.append(tool_message(call, "这个已经查过了，结果同上，不要重复查询，直接用 edit 修改。"))
                continue
            if call.name == "edit":
                done = apply_ops(tree, args.get("ops") or [])
                changes += done
                result = "已执行：\n" + "\n".join(done) + "\n\n还有的问题：\n" + ("\n".join(problems(tree)) or "（没有了）")
                again = [d for d in done if seen_edits.get(d, 0) >= 1]
                for d in done:
                    seen_edits[d] = seen_edits.get(d, 0) + 1
                if len(again) >= 2:
                    circling += 1
                    result += ("\n\n注意：你在来回做同样的修改（" + "；".join(again[:3]) + "），这样不会解决问题。换个思路："
                               "先看 check_blender 说的无效原因（回路、隐藏的口、类型），回路要拆掉一根线，隐藏的口要换成当前运算下可用的口。")
            elif call.name == "view_frames":
                got = []
                for t in [float(x) for x in (args.get("times") or [])[:VIEW_MAX] if isinstance(x, (int, float))]:
                    path = folder / f"{int(t * 10):07d}.jpg"
                    folder.mkdir(parents=True, exist_ok=True)
                    if path.is_file() or await tools.sharp(t, path, recipe.SHARP_WIDTH):
                        near = recipe.crop_editor(path, folder / f"crop-{int(t * 10):07d}.jpg")
                        pictures += [{"type": "text", "text": f"{round(t)} 秒的画面"}, _image(near)]
                        got.append(round(t))
                result = f"画面见下一条消息：{got}" if got else "没能读到这些时间的画面"
            elif call.name == "read_material":
                a, b = float(args.get("start") or 0), float(args.get("end") or 0)
                lines = step_cards.timed_lines([x for x in transcript if a <= x.start <= b], [x for x in screen if a <= x.start <= b])
                result = "\n".join(lines) or "这段没有语音和画面文字"
            elif call.name == "lookup_software":
                hit = knowledge.lookup(str(args.get("name") or ""))
                result = json.dumps(hit, ensure_ascii=False) if hit else "Blender 自带的节点和运算里没有这个名字"
            elif call.name == "check_blender":
                result, png = await blender_check(tree) if blender_check else ("没有连接 Blender，跳过", "")
                checks.append(result)
                preview = png or preview
                if png and not shown_end and (job.video.duration or 0) > 20:  # the finished look, once, to compare with
                    shown_end = True
                    end_at = round(job.video.duration * 0.92)
                    path = folder / f"end-{end_at}.jpg"
                    folder.mkdir(parents=True, exist_ok=True)
                    if path.is_file() or await tools.sharp(end_at, path, recipe.SHARP_WIDTH):
                        pictures += [{"type": "text", "text": f"视频接近结尾（{end_at} 秒）的画面，通常是成品效果："}, _image(path)]
                if png:
                    pictures += [{"type": "text", "text": "Blender 按当前节点图做出来的效果（Workbench 渲染，选中的物体作输入）。"
                                  "和视频里的成品效果比一比：形状不对就说明节点或连线还有错，对照视频再改"},
                                 {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}}]
                    result += "\n效果图见下一条消息"
            else:
                result = f"没有工具 {call.name}"
            asked[key] = result
            messages.append(tool_message(call, result[:6000]))
        nudge = {"type": "text", "text": "看完了就用 edit 一次把能确定的修改都做了（可以一次给多个操作），再根据剩下的问题继续。"
                  if looked < LOOK_BUDGET else "查看画面的次数用完了：现在用 edit 修改，改完用 check_blender 检查（如果连了 Blender），然后总结。"}
        if pictures:
            messages.append({"role": "user", "content": pictures + [nudge]})
        elif any(c.name in ("view_frames", "read_material") for c in usage.tool_calls) and not any(c.name == "check_blender" for c in usage.tool_calls):
            messages.append({"role": "user", "content": [nudge]})
    else:
        summary = "改到了最多轮数，先停在这里；可以再让 AI 接着改。"
    save_version(job.root, found)
    new = {**found, "trees": [tree if i == index else t for i, t in enumerate(found["trees"])]}
    recipe.save(job.root, new)
    return {"summary": summary, "changes": changes, "checks": checks[-1:], "problems": problems(tree), "recipe": new, "trace": trace,
            "preview": preview}
