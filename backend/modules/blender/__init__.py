"""The person's own Blender, reached through the 帧寻 Bridge add-on (zhenxun_bridge.py in this folder).

Only on this computer: the add-on listens on 127.0.0.1:9877 and the app talks to it here, one JSON line
each way. The web demo never offers it (another person's Blender isn't on our server). Used to build a
抄作业 graph in Blender directly (run the script from modules/recipe_script.py) and to read the person's
tree back and compare it with the graph (check.py: 对答案).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

ADDON = Path(__file__).with_name("zhenxun_bridge.py")
HOST = "127.0.0.1"
TIMEOUT = 8.0


def port() -> int:
    try:
        return int(os.environ.get("BLENDER_BRIDGE_PORT", "9877"))
    except ValueError:
        return 9877


class BridgeError(RuntimeError):
    """Blender isn't reachable or refused; the message is for the person."""


async def call(cmd: str, timeout: float = TIMEOUT, **fields) -> dict:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(HOST, port()), timeout=2)
    except (OSError, asyncio.TimeoutError):
        raise BridgeError("没有连上 Blender：打开 Blender，装好并启用「帧寻 Bridge」插件（侧栏 › 帧寻 显示已连接）") from None
    try:
        writer.write((json.dumps({"cmd": cmd, **fields}, ensure_ascii=False) + "\n").encode("utf-8"))
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    except (OSError, asyncio.TimeoutError):
        raise BridgeError("Blender 没有及时回应：它可能正忙（渲染或弹窗中），稍后再试") from None
    finally:
        writer.close()
    try:
        answer = json.loads(line.decode("utf-8") or "{}")
    except ValueError:
        raise BridgeError("Blender 的回应看不懂：请更新「帧寻 Bridge」插件") from None
    if not answer.get("ok"):
        raise BridgeError(str(answer.get("error") or "Blender 拒绝了这个操作")[:600])
    return answer


async def status() -> dict:
    """{connected, blender, object} without raising."""
    try:
        got = await call("ping", timeout=3)
    except BridgeError as exc:
        return {"connected": False, "message": str(exc)}
    return {"connected": True, "blender": got.get("blender"), "object": got.get("object")}
