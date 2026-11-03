#!/usr/bin/env python3
"""Cross-platform launcher for GongJ!ng? — Windows, macOS, and Linux.

Double-click ``start.cmd`` on Windows, or run directly::

    python start.py              check, install, start, open browser
    python start.py --check      only check the environment, then exit
    python start.py --no-browser start without opening a browser
    python start.py --skip-install  skip dependency installation (for re-runs)

The backend binds 127.0.0.1 only, so the app is not reachable from other
machines.  No existing service on the chosen ports is killed; if a port is
taken the launcher reports it and exits.  Ctrl+C (or the window close button
on Windows) stops only the processes this launcher started.

The first run works without an API key: the home page opens and the settings
panel (top-bar gear icon) lets you configure a model provider.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONT = ROOT / "front"

API_PORT = int(os.environ.get("API_PORT", "8000"))
WEB_PORT = int(os.environ.get("WEB_PORT", "5173"))
HOST = "127.0.0.1"

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# ANSI colours — disabled on Windows unless the terminal supports them.
if IS_WIN and not os.environ.get("TERM"):
    BOLD = DIM = RED = GREEN = YELLOW = CYAN = RESET = ""
else:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"

failures = 0
warnings = 0
WAIT_TIMEOUT = 60


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    global warnings
    print(f"  {YELLOW}!{RESET} {msg}")
    warnings += 1


def fail(msg: str) -> None:
    global failures
    print(f"  {RED}✗{RESET} {msg}")
    failures += 1


# ── tool checks ──────────────────────────────────────────────────────────

def _run_quiet(args: list[str], timeout: float = 5) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def check_python() -> None:
    v = sys.version_info
    if v >= (3, 12):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python {v.major}.{v.minor} — 需要 3.12 或更高（https://www.python.org/downloads/）")


def check_uv() -> None:
    uv = shutil.which("uv")
    if uv:
        ver = _run_quiet(["uv", "--version"])
        ok(f"uv {ver.split()[-1] if ver else '?'}")
    else:
        if IS_WIN:
            fail("没有 uv：pip install uv，或 PowerShell iwr https://astral.sh/uv/install.ps1 | iex")
        elif IS_MAC:
            fail("没有 uv：brew install uv")
        else:
            fail("没有 uv：curl -LsSf https://astral.sh/uv/install.sh | sh")


def check_node() -> None:
    node = shutil.which("node")
    if node:
        ver = _run_quiet(["node", "--version"])
        major = int(ver.lstrip("v").split(".")[0]) if ver else 0
        if major >= 20:
            ok(f"node {ver}")
        else:
            fail(f"node {ver} — 需要 20 或更高（https://nodejs.org/）")
    else:
        fail("没有 Node.js：https://nodejs.org/ 下载 LTS 版")


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        ok("ffmpeg")
    else:
        if IS_WIN:
            fail("没有 ffmpeg（抽帧和转写都要用）：https://www.gyan.dev/ffmpeg/builds/ 下载，解压后把 bin 加到 PATH")
        elif IS_MAC:
            fail("没有 ffmpeg：brew install ffmpeg")
        else:
            fail("没有 ffmpeg：sudo apt install ffmpeg 或对应包管理器安装")


def check_tools() -> None:
    print(f"{BOLD}工具{RESET}")
    check_python()
    check_uv()
    check_node()
    check_ffmpeg()


# ── port checks ──────────────────────────────────────────────────────────

def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def check_ports() -> None:
    print(f"{BOLD}端口{RESET}")
    for port, label in [(API_PORT, "后端"), (WEB_PORT, "前端")]:
        if port_in_use(port):
            fail(f"{label} 端口 {port} 已被占用，请先关掉占用它的程序，或设置 {'API_PORT' if label == '后端' else 'WEB_PORT'} 环境变量换一个端口")
        else:
            ok(f"{label} {port} 空闲")


# ── dependency installation ──────────────────────────────────────────────

def install_deps() -> bool:
    print(f"{BOLD}依赖{RESET}")
    uv = shutil.which("uv")
    if not uv:
        fail("没有 uv，无法安装后端依赖")
        return False
    r = subprocess.run(["uv", "sync", "--quiet"], cwd=BACKEND)
    if r.returncode == 0:
        ok("后端依赖（uv sync）")
    else:
        fail("uv sync 失败")
        return False
    need_install = not (FRONT / "node_modules" / ".package-lock.json").exists()
    if not need_install:
        lock = FRONT / "package-lock.json"
        installed = FRONT / "node_modules" / ".package-lock.json"
        try:
            need_install = lock.stat().st_mtime > installed.stat().st_mtime
        except OSError:
            need_install = True
    if need_install:
        npm = shutil.which("npm")
        if not npm:
            fail("没有 npm，无法安装前端依赖")
            return False
        r = subprocess.run(["npm", "install", "--silent"], cwd=FRONT, shell=IS_WIN)
        if r.returncode == 0:
            ok("前端依赖（npm install）")
        else:
            fail("npm install 失败")
            return False
    else:
        ok("前端依赖已是最新")
    return True


# ── process management ───────────────────────────────────────────────────

children: list[subprocess.Popen] = []
cleanup_done = False


def cleanup() -> None:
    global cleanup_done
    if cleanup_done:
        return
    cleanup_done = True
    print(f"\n{DIM}正在停止…{RESET}")
    for p in children:
        try:
            if IS_WIN:
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                p.terminate()
        except (OSError, ProcessLookupError):
            pass
    for p in children:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except (OSError, ProcessLookupError):
                pass


def on_signal(signum, frame):
    raise KeyboardInterrupt


# ── health check ─────────────────────────────────────────────────────────

def wait_for_health(port: int, timeout: float = 60) -> bool:
    url = f"http://{HOST}:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    return False


# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="启动 GongJ!ng?")
    parser.add_argument("--check", action="store_true", help="只检查环境，不启动")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--skip-install", action="store_true", help="跳过依赖安装")
    args = parser.parse_args()

    print(f"\n{BOLD}GongJ!ng? 启动检查{RESET}")
    check_tools()
    check_ports()
    print()

    if failures > 0:
        print(f"{RED}{failures} 项必须先处理{RESET}（另有 {warnings} 项提示），处理后再运行")
        return 1

    if args.check:
        print(f"{GREEN}检查通过{RESET}（{warnings} 项提示）")
        return 0

    if not args.skip_install:
        if not install_deps():
            return 1
    print()

    # Start backend — no --reload on Windows (file watcher + asyncio issues).
    backend_cmd = ["uv", "run", "uvicorn", "app:app",
                   "--host", HOST, "--port", str(API_PORT),
                   "--timeout-graceful-shutdown", "3"]
    if not IS_WIN:
        backend_cmd.append("--reload")
        backend_cmd += ["--reload-include", ".env"]

    creationflags = 0
    if IS_WIN:
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    api = subprocess.Popen(backend_cmd, cwd=BACKEND, creationflags=creationflags)
    children.append(api)

    # Start frontend.
    npm_cmd = ["npm", "run", "dev"]
    web = subprocess.Popen(npm_cmd, cwd=FRONT, shell=IS_WIN, creationflags=creationflags)
    children.append(web)

    signal.signal(signal.SIGINT, on_signal)
    if not IS_WIN:
        signal.signal(signal.SIGTERM, on_signal)
    import atexit
    atexit.register(cleanup)

    # Wait for backend health, then open the browser.
    if wait_for_health(API_PORT):
        url = f"http://localhost:{WEB_PORT}"
        if not args.no_browser:
            threading.Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)), daemon=True).start()
        print(f"\n{BOLD}就绪{RESET}  打开 {BOLD}{url}{RESET}"
              f"  （后端 http://localhost:{API_PORT}；Ctrl+C 停止）\n")
    else:
        warn(f"后端在 {API_PORT} 上 {WAIT_TIMEOUT} 秒内未就绪，请查看日志")

    # Wait for either process to exit or Ctrl+C.
    try:
        while True:
            if api.poll() is not None:
                warn("后端已退出")
                break
            if web.poll() is not None:
                warn("前端已退出")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
