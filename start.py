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
import hashlib
import json
import time
import urllib.request
import webbrowser
from pathlib import Path

from scripts.launcher_processes import ProcessGroup

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONT = ROOT / "front"

API_PORT = 8000
WEB_PORT = 5173
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
    except (OSError, subprocess.TimeoutExpired):
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
        ok(f"uv {ver.split()[1] if len(ver.split()) > 1 else '?'}")
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
        try:
            major = int(ver.lstrip("v").split(".")[0]) if ver else 0
        except ValueError:
            major = 0
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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return True
    return False


def check_ports() -> None:
    print(f"{BOLD}端口{RESET}")
    for port, label in [(API_PORT, "后端"), (WEB_PORT, "前端")]:
        if port_in_use(port):
            fail(f"{label} 端口 {port} 已被占用，请先关掉占用它的程序，或设置 {'API_PORT' if label == '后端' else 'WEB_PORT'} 环境变量换一个端口")
        else:
            ok(f"{label} {port} 空闲")


# ── dependency installation ──────────────────────────────────────────────

def backend_python() -> Path:
    return BACKEND / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")


def child_environment() -> dict[str, str]:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1",
            "API_PORT": str(API_PORT), "WEB_PORT": str(WEB_PORT),
            "VITE_API_BASE": "", "VITE_BASE": "/", "PUBLIC_DEMO": "off"}


def install_deps() -> bool:
    print(f"{BOLD}依赖{RESET}")
    env = child_environment()
    command = ["uv", "sync", "--frozen", "--python", "3.12"]
    if not IS_MAC:
        command += ["--extra", "cloud"]
    if subprocess.run(command, cwd=BACKEND, env=env).returncode:
        fail("后端依赖安装失败，请检查网络后重试")
        return False
    ok("后端依赖（锁定版本，Windows/Linux 含语音转写和 OCR）")
    lock_hash = hashlib.sha256((FRONT / "package-lock.json").read_bytes() + (FRONT / "package.json").read_bytes()).hexdigest()
    marker = FRONT / "node_modules" / ".zhenxun-lock.sha256"
    installed = marker.read_text(encoding="ascii").strip() if marker.exists() else ""
    if installed != lock_hash:
        if (FRONT / "node_modules").is_symlink():
            fail("前端使用共享依赖链接，请先独立安装，或验收时用 --skip-install")
            return False
        npm = shutil.which("npm")
        if not npm or subprocess.run([npm, "ci"], cwd=FRONT, env=env, shell=IS_WIN).returncode:
            fail("前端依赖安装失败，请检查 Node.js 和网络后重试")
            return False
        marker.write_text(lock_hash, encoding="ascii")
    ok("前端依赖（package-lock.json）")
    # The QR login flows need a browser; this is idempotent when already cached.
    if subprocess.run([str(backend_python()), "-m", "playwright", "install", "--only-shell", "chromium"],
                      cwd=BACKEND, env=env).returncode:
        warn("浏览器组件下载失败，扫码和网页查证暂不可用，可稍后重新启动补装")
    return True


processes = ProcessGroup()


def cleanup() -> None:
    processes.stop()


def on_signal(signum, frame):
    raise KeyboardInterrupt


# ── health check ─────────────────────────────────────────────────────────

def wait_for_health(port: int, timeout: float = 60, *, frontend: bool = False) -> bool:
    path = "/" if frontend else "/api/health"
    url = f"http://{HOST}:{port}{path}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in processes.children):
            return False
        try:
            with opener.open(url, timeout=1) as response:
                data = response.read()
                if response.status == 200 and (b"<html" in data.lower() if frontend else json.loads(data).get("ok") is True):
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    return False


# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    global API_PORT, WEB_PORT, failures, warnings, processes
    failures = warnings = 0
    processes = ProcessGroup()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="启动帧寻本地版")
    parser.add_argument("--check", action="store_true", help="只检查环境，不启动")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--skip-install", action="store_true", help="使用已安装的依赖，不联网安装")
    args = parser.parse_args()
    print(f"\n{BOLD}GongJ!ng? 帧寻本地启动检查{RESET}", flush=True)
    try:
        API_PORT = int(os.environ.get("API_PORT", "8000"))
        WEB_PORT = int(os.environ.get("WEB_PORT", "5173"))
        if not (1 <= API_PORT <= 65535 and 1 <= WEB_PORT <= 65535 and API_PORT != WEB_PORT):
            raise ValueError
    except ValueError:
        fail("API_PORT 和 WEB_PORT 必须是 1–65535 之间不同的整数端口")
        return 1
    check_tools()
    check_ports()
    if failures:
        print(f"{failures} 项必须先处理，处理后再运行", flush=True)
        return 1
    if args.check:
        print("检查通过", flush=True)
        return 0
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    if IS_WIN:
        signal.signal(signal.SIGBREAK, on_signal)
    import atexit
    atexit.register(cleanup)
    try:
        if not args.skip_install and not install_deps():
            return 1
        if not backend_python().is_file() or not (FRONT / "node_modules").is_dir():
            fail("尚未安装依赖，请去掉 --skip-install 后重试")
            return 1
        env = child_environment()
        backend_cmd = [str(backend_python()), "-m", "uvicorn", "app:app", "--host", HOST,
                       "--port", str(API_PORT), "--timeout-graceful-shutdown", "3"]
        processes.start(backend_cmd, cwd=BACKEND, env=env)
        npm = shutil.which("npm")
        if not npm:
            fail("找不到 npm，请重新安装 Node.js LTS")
            return 1
        processes.start([npm, "run", "dev", "--", "--host", HOST], cwd=FRONT, env=env, shell=IS_WIN)
        if not wait_for_health(API_PORT, WAIT_TIMEOUT) or not wait_for_health(WEB_PORT, WAIT_TIMEOUT, frontend=True):
            fail("服务未能就绪，请查看上面的启动日志")
            return 1
        url = f"http://{HOST}:{WEB_PORT}"
        print(f"\n就绪  {url}（Ctrl+C 停止）", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        while all(child.poll() is None for child in processes.children):
            time.sleep(0.2)
        fail("本机服务意外退出，请查看启动日志")
        return 1
    except KeyboardInterrupt:
        print("\n正在停止本次启动的服务…", flush=True)
        return 0
    except OSError:
        fail("启动失败，请检查工具安装、目录权限和端口占用情况")
        return 1
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
