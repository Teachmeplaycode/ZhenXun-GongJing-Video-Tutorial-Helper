"""Settings from the environment, falling back to `backend/.env` (real environment variables win)."""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
# Logins saved from the UI (modules/accounts). A separate file, because dev.sh restarts the backend
# whenever .env changes, which would cut off answers in progress.
ACCOUNTS_FILE = ENV_FILE.with_name(".env.accounts")
# User settings written from the Settings panel (model/API/runtime). gitignored (matched by .env.*),
# read on every request so a saved change applies to the next call without restarting the backend.
# Real environment variables still win, so a server operator can lock a value with an env var.
LOCAL_FILE = ENV_FILE.with_name(".env.local")


def parse_assignment(line: str) -> tuple[str, str]:
    """`[export ]NAME=value` with optional quotes → (NAME, value); a bare value gives ("", value)."""
    name, sep, value = line.removeprefix("export ").partition("=")
    if not sep:
        name, value = "", name
    return name.strip(), value.strip().strip("'\"")


def read_env_file(path: Path) -> dict[str, str]:
    """Minimal .env reader: NAME=value lines, `#` comments; no variable expansion."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return {}
    pairs = (parse_assignment(line.strip()) for line in lines if "=" in line and not line.strip().startswith("#"))
    return {name: value for name, value in pairs if name}


# The web demo sets these per request (app.py): `overlay` holds the signed-in person's own platform
# logins and blanks out everyone else's; `vault` is where a new login of theirs is saved instead of
# .env.accounts (modules/members.py). Unset locally.
overlay: ContextVar[dict | None] = ContextVar("settings_overlay", default=None)
vault: ContextVar[object | None] = ContextVar("settings_vault", default=None)


def cn_proxy() -> str | None:
    """CN_PROXY: an HTTP proxy in mainland China for the platforms that turn away overseas servers
    (小红书, 元宝 / 视频号 …); None when unset, e.g. on a machine that is in mainland China already."""
    return settings().get("CN_PROXY", "").strip() or None


def settings() -> dict[str, str]:
    """Read on every call so an edited .env applies to the next request.

    Precedence: .env < .env.accounts (logins from the UI) < .env.local (Settings panel) < real
    environment variables < the request's overlay (the web demo: this person's own logins).
    """
    return {**read_env_file(ENV_FILE), **read_env_file(ACCOUNTS_FILE), **read_env_file(LOCAL_FILE),
            **os.environ, **(overlay.get() or {})}


def read_local() -> dict[str, str]:
    """Just the Settings-panel file, for the API to report what it holds."""
    return read_env_file(LOCAL_FILE)


def write_local(updates: dict[str, str | None]) -> dict[str, str]:
    """Set (or with None, remove) keys in .env.local, keeping the other lines.

    Atomic (temp file + os.replace), UTF-8, mode 0600. Returns the resulting file contents as a dict.
    Never called in the public demo: app.py guards the route, and the web demo stores per-person
    settings through settings.vault instead.
    """
    lines = LOCAL_FILE.read_text(encoding="utf-8").splitlines() if LOCAL_FILE.exists() else []
    out: list[str] = []
    done: set[str] = set()
    for line in lines:
        name = parse_assignment(line.strip())[0] if "=" in line and not line.strip().startswith("#") else ""
        if name in updates:
            done.add(name)
            if updates[name] is not None:
                out.append(f'{name}={updates[name]}')
            continue
        out.append(line)
    out += [f'{k}={v}' for k, v in updates.items() if k not in done and v is not None]
    if not any(not l.startswith("#") for l in out):
        out.insert(0, "# Written by the Settings panel; real environment variables still win. Do not commit.")
    tmp = LOCAL_FILE.with_name(LOCAL_FILE.name + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.replace(tmp, LOCAL_FILE)  # atomic on the same filesystem
    try:
        os.chmod(LOCAL_FILE, 0o600)
    except OSError:
        pass
    return read_local()


def source_of(key: str) -> tuple[str | None, bool]:
    """Where `key`'s effective value comes from, and whether an environment variable overrides the file.

    Source is one of: "overlay" (per-request), "environment", "local" (.env.local), "accounts"
    (.env.accounts), "env" (.env), or None. `overridden_by_env` is True when a real environment
    variable is set (it wins over every file), so a file edit would not take effect.
    """
    if (overlay.get() or {}).get(key):
        return "overlay", bool(os.environ.get(key))
    if os.environ.get(key):
        return "environment", True
    if read_env_file(LOCAL_FILE).get(key):
        return "local", False
    if read_env_file(ACCOUNTS_FILE).get(key):
        return "accounts", False
    if read_env_file(ENV_FILE).get(key):
        return "env", False
    return None, False


# What the Settings panel shows. `secret` fields are never echoed back: the API reports only whether
# one is set. `aliases` let a secret be considered configured when any of them has a value.
SETTINGS_GROUPS: list[dict] = [
    {"id": "model", "label": "模型与 API", "fields": [
        {"name": "LLM_PROVIDER", "label": "模型服务", "type": "select",
         "options": [{"value": "deepseek", "label": "DeepSeek / OpenAI 兼容"}, {"value": "ollama", "label": "本地 Ollama"}],
         "default": "deepseek", "hint": "OpenAI 兼容的云端服务，或本机的 Ollama。"},
        {"name": "LLM_BASE_URL", "label": "服务地址", "type": "url",
         "hint": "DeepSeek 默认 https://api.deepseek.com；Ollama 默认 http://localhost:11434。"},
        {"name": "LLM_MODEL", "label": "模型名", "type": "text",
         "hint": "DeepSeek 用 deepseek-flash；Ollama 用 qwen3.5:9b（需支持图片）。"},
        {"name": "LLM_API_KEY", "label": "API Key", "type": "secret", "aliases": ["DEEPSEEK_API_KEY"],
         "hint": "Ollama 不需要。留空保留原值，点「清除」删除。"},
        {"name": "TAVILY_API_KEY", "label": "Tavily Key", "type": "secret",
         "hint": "联网搜索备用（tavily.com）。"},
        {"name": "OPENALEX_API_KEY", "label": "OpenAlex Key", "type": "secret",
         "hint": "论文检索，带 key 约 1000 次/天（openalex.org 免费注册）。"},
        {"name": "CN_PROXY", "label": "国内代理", "type": "url",
         "hint": "小红书、视频号等需要国内 IP 的平台走这个代理；在国内可留空。"},
    ]},
    {"id": "runtime", "label": "本地运行", "fields": [
        {"name": "OLLAMA_NUM_CTX", "label": "Ollama 上下文长度", "type": "number", "default": "65536",
         "hint": "Ollama 的上下文窗口。"},
        {"name": "LLM_FIRST_TOKEN_TIMEOUT", "label": "首字超时（秒）", "type": "number",
         "hint": "等第一个字的最长时间；Ollama 默认 300，云端默认 90。"},
        {"name": "LLM_TEMPERATURE", "label": "采样温度", "type": "number",
         "hint": "默认 0.3；基准测试用 0 让两次结果更接近。"},
        {"name": "DECISION", "label": "决策模块", "type": "select",
         "options": [{"value": "", "label": "开启"}, {"value": "off", "label": "关闭"}],
         "hint": "过滤搜索结果、拦截注入、判断是否查资料；关闭后退回简单规则。"},
        {"name": "DECISION_MODEL", "label": "决策模型", "type": "text",
         "hint": "Ollama 里的决策模型，默认 qwen3.5:9b。"},
        {"name": "KEEP_UPLOADS", "label": "保留上传原文件", "type": "select",
         "options": [{"value": "on", "label": "保留"}, {"value": "off", "label": "处理后删除"}],
         "default": "on", "hint": "保留后可回放原视频；公开服务器可设为删除。"},
        {"name": "BROWSER", "label": "浏览器操作", "type": "select",
         "options": [{"value": "", "label": "需要时启动"}, {"value": "off", "label": "关闭"}],
         "hint": "扫码登录和部分平台解析要用无头浏览器；关闭后只能用 Cookie。"},
    ]},
]

SETTINGS_FIELDS: dict[str, dict] = {f["name"]: f for g in SETTINGS_GROUPS for f in g["fields"]}
SECRET_FIELDS: set[str] = {f["name"] for f in SETTINGS_FIELDS.values() if f.get("type") == "secret"}


def is_configured(env: dict[str, str], field: dict) -> bool:
    """Whether a field has any value, checking aliases for secrets."""
    if env.get(field["name"]):
        return True
    return any(env.get(a) for a in field.get("aliases", []))
