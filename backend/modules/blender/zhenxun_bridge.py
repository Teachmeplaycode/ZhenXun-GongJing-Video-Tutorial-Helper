"""帧寻 Bridge: a Blender add-on that lets the 帧寻 app on this computer read and build node trees.

Install: Blender → 编辑 → 偏好设置 → 插件 → 从磁盘安装 → this file → tick it. It listens on
127.0.0.1:9877 only (never the network) and shows its state in the sidebar (N) of the 3D view and the
node editor, tab 「帧寻」. The protocol is one JSON object per line each way, after the pattern of
blender-mcp (MIT): requests are queued and run on Blender's main thread by a timer, since bpy must not
be touched from another thread.

  ping                       → {"blender": "5.0.1", "object": name or null}
  export_tree [target owned] → the node tree 帧寻 built (its modifier / material named `owned`), else the
                               active object's geometry-nodes modifier or material, or the world
  run_script code            → runs a script 帧寻 generated (抄作业 → 应用到 Blender), with its output
"""
from __future__ import annotations

import io
import json
import queue
import socket
import threading
import traceback
from contextlib import redirect_stdout

import bpy

bl_info = {
    "name": "帧寻 Bridge",
    "author": "帧寻 GongJ!ng?",
    "version": (0, 2, 0),
    "blender": (4, 0, 0),
    "location": "3D 视图 / 节点编辑器 › 侧栏（N）› 帧寻",
    "description": "让本机的帧寻读取和建立节点：抄作业一键应用、对答案",
    "category": "Interface",
}

HOST, PORT = "127.0.0.1", 9877
_jobs: queue.Queue = queue.Queue()
_state = {"server": None, "thread": None, "last": "", "requests": 0}


# ---- what the app asks for ---------------------------------------------------------------------
def _plain(value):
    """A socket value as JSON: numbers, booleans, strings, vectors and colours as lists."""
    if isinstance(value, (bool, int, float, str)) or value is None:
        return round(value, 6) if isinstance(value, float) else value
    try:
        return [round(float(x), 6) for x in value]
    except TypeError:
        return getattr(value, "name", None)  # an object, material, collection: its name


def _tree(target: str = "", owned: str = ""):
    """The tree to read: what 帧寻 built under `owned` (its modifier or material) first, else the last
    帧寻 modifier, else the object's first geometry-nodes modifier / active material, else the world."""
    obj = bpy.context.object
    if target in ("", "geometry") and obj is not None:
        mods = [m for m in obj.modifiers if m.type == "NODES" and m.node_group is not None]
        mine = [m for m in mods if m.name == owned] or [m for m in mods if m.name.startswith("帧寻·")]
        if mine or mods:
            return (mine[-1] if mine else mods[0]).node_group, "geometry"
    if target in ("", "material") and obj is not None:
        mat = bpy.data.materials.get(owned) if owned else None
        mat = mat if mat is not None and mat.node_tree is not None else getattr(obj, "active_material", None)
        if mat is not None and mat.node_tree is not None:
            return mat.node_tree, "material"
    if target in ("", "world") and bpy.context.scene.world and bpy.context.scene.world.node_tree:
        return bpy.context.scene.world.node_tree, "world"
    return None, ""


def export_tree(target: str = "", owned: str = "") -> dict:
    tree, kind = _tree(target, owned)
    if tree is None:
        return {"ok": False, "error": "没有找到节点树：选中一个带几何节点修改器或材质的物体再试"}
    nodes = []
    for n in tree.nodes:
        entry = {"name": n.name, "bl_idname": n.bl_idname, "label": n.label, "location": [round(n.location.x), round(n.location.y)],
                 "inputs": [], "outputs": [s.name for s in n.outputs if s.enabled]}
        for key in ("operation", "data_type", "input_type", "mode", "blend_type", "use_clamp"):
            if hasattr(n, key):
                entry[key] = _plain(getattr(n, key))
        for s in n.inputs:
            if not s.enabled:
                continue
            item = {"name": s.name, "identifier": s.identifier, "type": s.type, "linked": s.is_linked}
            if hasattr(s, "default_value") and not s.is_linked:
                item["value"] = _plain(s.default_value)
            entry["inputs"].append(item)
        nodes.append(entry)
    links = [{"from": l.from_node.name, "out": l.from_socket.name, "to": l.to_node.name, "in": l.to_socket.name,
              "valid": l.is_valid} for l in tree.links]
    return {"ok": True, "kind": kind, "name": tree.name, "nodes": nodes, "links": links}


def run_script(code: str) -> dict:
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            exec(compile(code, "zhenxun_recipe", "exec"), {"__name__": "__zhenxun__"})
    except Exception:  # noqa: BLE001 — reported back, Blender keeps running
        return {"ok": False, "error": traceback.format_exc()[-800:], "output": out.getvalue()[-2000:]}
    return {"ok": True, "output": out.getvalue()[-2000:]}


def handle(request: dict) -> dict:
    cmd = request.get("cmd")
    if cmd == "ping":
        obj = bpy.context.object
        return {"ok": True, "blender": bpy.app.version_string, "object": obj.name if obj else None}
    if cmd == "export_tree":
        return export_tree(str(request.get("target") or ""), str(request.get("owned") or ""))
    if cmd == "run_script":
        return run_script(str(request.get("code") or ""))
    return {"ok": False, "error": f"不认识的命令：{cmd}"}


# ---- the local socket, answered on Blender's main thread --------------------------------------
def _serve(server: socket.socket) -> None:
    while _state["server"] is server:
        try:
            conn, _ = server.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(30)
            data = b""
            try:
                while not data.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                request = json.loads(data.decode("utf-8") or "{}")
            except (OSError, ValueError):
                continue
            reply: queue.Queue = queue.Queue()
            _jobs.put((request, reply))
            try:
                answer = reply.get(timeout=60)
            except queue.Empty:
                answer = {"ok": False, "error": "Blender 正忙，没能及时处理"}
            try:
                conn.sendall((json.dumps(answer, ensure_ascii=False) + "\n").encode("utf-8"))
            except OSError:
                pass


def _tick():
    while not _jobs.empty():
        request, reply = _jobs.get()
        try:
            answer = handle(request)
        except Exception:  # noqa: BLE001
            answer = {"ok": False, "error": traceback.format_exc()[-800:]}
        _state["requests"] += 1
        _state["last"] = str(request.get("cmd"))
        reply.put(answer)
    return 0.1 if _state["server"] is not None else None


def start() -> str:
    if _state["server"] is not None:
        return "已在运行"
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((HOST, PORT))
    except OSError as exc:
        return f"端口 {PORT} 被占用：{exc}"
    server.listen(4)
    _state["server"] = server
    _state["thread"] = threading.Thread(target=_serve, args=(server,), daemon=True)
    _state["thread"].start()
    bpy.app.timers.register(_tick, persistent=True)
    return "已连接"


def stop() -> None:
    server, _state["server"] = _state["server"], None
    if server is not None:
        try:
            server.close()
        except OSError:
            pass


# ---- the sidebar ----------------------------------------------------------------------------
class ZHENXUN_OT_toggle(bpy.types.Operator):
    bl_idname = "zhenxun.toggle"
    bl_label = "连接 / 断开帧寻"

    def execute(self, context):
        if _state["server"] is None:
            self.report({"INFO"}, f"帧寻：{start()}")
        else:
            stop()
            self.report({"INFO"}, "帧寻：已断开")
        return {"FINISHED"}


def _draw(self, context):
    on = _state["server"] is not None
    col = self.layout.column()
    col.label(text=f"状态：{'已连接帧寻（本机 ' + str(PORT) + '）' if on else '未连接'}", icon="LINKED" if on else "UNLINKED")
    if on and _state["last"]:
        col.label(text=f"最近：{_state['last']} · 共 {_state['requests']} 次")
    col.operator("zhenxun.toggle", text="断开" if on else "连接帧寻")
    col.label(text="在帧寻的节点画布里点「应用到 Blender」「对答案」")


class ZHENXUN_PT_view3d(bpy.types.Panel):
    bl_label = "帧寻"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "帧寻"
    draw = _draw


class ZHENXUN_PT_nodes(bpy.types.Panel):
    bl_label = "帧寻"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "帧寻"
    draw = _draw


CLASSES = (ZHENXUN_OT_toggle, ZHENXUN_PT_view3d, ZHENXUN_PT_nodes)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    start()  # local only: connected as soon as it is enabled


def unregister():
    stop()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
