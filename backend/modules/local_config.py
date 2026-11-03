"""Local settings boundary: validated edits and public metadata without credential values."""
from __future__ import annotations

import ipaddress
import math
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import settings as config


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(default_factory=dict)
    clear: list[str] = Field(default_factory=list)


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def local_only(request: Request) -> None:
    """Check the connection, Host and browser Origin; never trust forwarded headers here."""
    peer = request.client.host if request.client else ""
    host = urlsplit(str(request.url)).hostname or ""
    if not _loopback(peer) or not _loopback(host):
        raise HTTPException(403, "设置只能从本机页面访问")
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "不能从其他网站修改本机设置")
    if origin:
        try:
            parsed = urlsplit(origin)
            valid = (parsed.scheme in ("http", "https") and _loopback(parsed.hostname or "")
                     and not parsed.username and not parsed.password
                     and not parsed.query and not parsed.fragment and parsed.path in ("", "/"))
            _ = parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(403, "设置只能从本机页面访问")


def view() -> dict:
    env = config.settings()
    saved = config.read_local()
    out = {}
    for name, field in config.SETTINGS_FIELDS.items():
        selected = name
        if field["type"] == "secret":
            selected = next((key for key in (name, *field.get("aliases", [])) if env.get(key)), name)
        source, overridden = config.source_of(selected)
        item = {"source": source, "overridden_by_env": overridden, "local_configured": bool(saved.get(name))}
        if field["type"] == "secret":
            item["configured"] = config.is_configured(env, field)
        else:
            value = env.get(name, "")
            # Legacy files can contain authenticated URLs even though new edits reject them.
            # Keep that untouched value on the backend, never reflect it in the browser.
            if field["type"] == "url" and value:
                try:
                    parsed = urlsplit(value)
                    hidden = bool(parsed.username or parsed.password or parsed.query or parsed.fragment)
                except ValueError:
                    hidden = True
                if hidden:
                    item.update(redacted=True, configured=True)
                    value = ""
            if name in ("DECISION", "BROWSER") and value:
                value = "off" if value.lower() in ("0", "false", "off", "no") else "on"
            item["value"] = value
        out[name] = item
    return out


BOUNDS = {"OLLAMA_NUM_CTX": (1024, 262144), "LLM_FIRST_TOKEN_TIMEOUT": (1, 900), "LLM_TEMPERATURE": (0, 2)}


def validate(values: dict[str, str], clear: list[str]) -> dict[str, str | None]:
    """An empty secret retains its value; empty optional controls restore inherited defaults."""
    if any(name not in config.SETTINGS_FIELDS for name in (*values, *clear)):
        raise HTTPException(400, "包含不支持的配置项")
    updates: dict[str, str | None] = {name: None for name in clear}
    for name, raw in values.items():
        field = config.SETTINGS_FIELDS[name]
        if len(raw) > (8192 if field["type"] == "secret" else 2048) or any(
            ord(c) < 32 or ord(c) == 127 or c in "\u0085\u2028\u2029" for c in raw
        ):
            raise HTTPException(400, f"{field['label']} 包含不支持的字符或长度过长")
        value = raw.strip()
        if field["type"] == "secret":
            if value:
                updates[name] = value
            continue
        if not value:
            updates[name] = None
            continue
        if field["type"] == "number":
            try:
                number = float(value)
                low, high = BOUNDS[name]
                valid = math.isfinite(number) and low <= number <= high
                if name == "OLLAMA_NUM_CTX":
                    valid = valid and number.is_integer()
                    value = str(int(number)) if valid else value
            except (ValueError, OverflowError):
                valid = False
            if not valid:
                raise HTTPException(400, f"{field['label']} 超出允许范围")
        elif field["type"] == "select":
            if value not in [option["value"] for option in field["options"]]:
                raise HTTPException(400, f"{field['label']} 的选项无效")
        elif field["type"] == "url":
            try:
                parsed = urlsplit(value)
                valid = (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                         and not parsed.username and not parsed.password
                         and not parsed.query and not parsed.fragment and not any(c.isspace() for c in value))
                _ = parsed.port
            except ValueError:
                valid = False
            if not valid:
                raise HTTPException(400, f"{field['label']} 需要有效的 HTTP(S) 地址，不能带账号或查询参数")
            value = value.rstrip("/")
        elif len(value) > 256:
            raise HTTPException(400, f"{field['label']} 过长")
        updates[name] = value
    return updates
