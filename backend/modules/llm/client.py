"""Streaming chat clients: OpenAI-compatible (DeepSeek by default) or a local Ollama.

Configuration comes from the environment, falling back to `backend/.env` (real environment variables win):
  LLM_PROVIDER   deepseek (default; any OpenAI-compatible service) or ollama
  LLM_BASE_URL   default https://api.deepseek.com, or http://localhost:11434 for ollama
  LLM_MODEL      default deepseek-flash, or qwen3.5:9b for ollama (must accept images)
  LLM_API_KEY    or DEEPSEEK_API_KEY; not needed for ollama
  LLM_KEY_FILE   path to a file holding the key, either bare or as one `NAME=value` line
  OLLAMA_NUM_CTX context window for ollama, default 65536 (its OpenAI endpoint can't set this,
                 so the native /api/chat is used)
  LLM_FIRST_TOKEN_TIMEOUT  seconds to wait for the first word; default 90, or 300 for ollama
                           (a local model also has to load and read every image first)
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..settings import parse_assignment, read_env_file, settings  # noqa: F401 (re-exported for tests)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
# A busy DeepSeek keeps the request open with keep-alive lines for up to 10 minutes instead of
# failing, so socket timeouts never fire. These deadlines bound the wait ourselves.
FIRST_TOKEN_TIMEOUT = 90   # seconds until the first content
ANSWER_TIMEOUT = 300       # seconds for the whole answer once it has started
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_FIRST_TOKEN_TIMEOUT = 300


class LLMError(Exception):
    """A model call failed; `message` is user-facing Chinese."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    provider: str = "deepseek"
    num_ctx: int = 65536
    first_token_timeout: float = FIRST_TOKEN_TIMEOUT

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> LLMConfig:
        env = settings() if env is None else env
        if env.get("LLM_PROVIDER", "deepseek").lower() == "ollama":
            return cls(env.get("LLM_BASE_URL", OLLAMA_BASE_URL).rstrip("/"), env.get("LLM_MODEL", OLLAMA_MODEL), "",
                       provider="ollama", num_ctx=int(env.get("OLLAMA_NUM_CTX", "65536")),
                       first_token_timeout=float(env.get("LLM_FIRST_TOKEN_TIMEOUT", OLLAMA_FIRST_TOKEN_TIMEOUT)))
        key = env.get("LLM_API_KEY") or env.get("DEEPSEEK_API_KEY") or ""
        if not key and env.get("LLM_KEY_FILE"):
            key = read_key_file(Path(env["LLM_KEY_FILE"]).expanduser())
        if not key:
            raise LLMError("no_api_key", "未配置模型密钥：请在 backend/.env 中设置 DEEPSEEK_API_KEY（或 LLM_API_KEY）后重启后端")
        return cls(env.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"), env.get("LLM_MODEL", DEFAULT_MODEL), key,
                   first_token_timeout=float(env.get("LLM_FIRST_TOKEN_TIMEOUT", FIRST_TOKEN_TIMEOUT)))


def read_key_file(path: Path) -> str:
    try:
        lines = [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]
    except OSError:
        raise LLMError("no_api_key", f"无法读取密钥文件 {path}")
    if len(lines) != 1:
        raise LLMError("no_api_key", "密钥文件应只有一行")
    return parse_assignment(lines[0])[1]


@dataclass
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


HTTP_ERRORS = {
    400: ("bad_request", "模型拒绝了请求（参数或图片格式不被支持）", False),
    401: ("unauthorized", "模型密钥无效或已过期", False),
    402: ("insufficient_balance", "模型账户余额不足", False),
    422: ("bad_request", "模型拒绝了请求参数", False),
    429: ("rate_limited", "模型请求过于频繁，请稍后再试", True),
}


class Deadline:
    """Bounds each read by the time left: `first` seconds until content starts, then `rest`.

    Applied per await (never held across a generator's `yield`).
    """

    def __init__(self, first: float, rest: float):
        self.loop = asyncio.get_running_loop()
        self.first, self.rest = first, rest
        self.at = self.loop.time() + first
        self.started = False

    def start(self) -> None:
        if not self.started:
            self.started = True
            self.at = self.loop.time() + self.rest

    async def wait(self, awaitable):
        try:
            return await asyncio.wait_for(awaitable, max(0.0, self.at - self.loop.time()))
        except TimeoutError:
            if self.started:
                raise LLMError("timeout", "模型回答时间过长，已中断", True) from None
            raise LLMError("busy", f"模型服务繁忙，{self.first:.0f} 秒内没有响应，请稍后重试", True) from None


class ChatClient:
    """OpenAI-compatible /chat/completions (DeepSeek and the like)."""

    def __init__(self, config: LLMConfig, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 120,
                 first_token_timeout: float | None = None, answer_timeout: float = ANSWER_TIMEOUT):
        self.config = config
        self.first_token_timeout = first_token_timeout or config.first_token_timeout
        self.answer_timeout = answer_timeout
        self.http = httpx.AsyncClient(
            base_url=config.base_url, transport=transport, trust_env=False,
            timeout=httpx.Timeout(timeout, connect=10),
            headers={"Authorization": f"Bearer {config.api_key}"},
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    def body(self, messages: list[dict], max_tokens: int) -> dict:
        body = {
            "model": self.config.model, "messages": messages, "stream": True,
            "stream_options": {"include_usage": True}, "max_tokens": max_tokens, "temperature": 0.3,
        }
        if "deepseek" in self.config.base_url:
            body["thinking"] = {"type": "disabled"}  # keep reasoning text out of the answer stream
        return body

    async def stream(self, messages: list[dict], usage: Usage, max_tokens: int = 2048) -> AsyncIterator[str]:
        """Yield content deltas; fills `usage` as the stream reports it.

        Each read is bounded by the time left before the deadline (never held across a `yield`):
        `first_token_timeout` until content starts, then `answer_timeout` for the rest.
        """
        deadline = Deadline(self.first_token_timeout, self.answer_timeout)
        before_deadline = deadline.wait
        response = None
        try:
            request = self.http.build_request("POST", "/chat/completions", json=self.body(messages, max_tokens))
            response = await before_deadline(self.http.send(request, stream=True))
            if response.status_code >= 400:
                code, message, retryable = HTTP_ERRORS.get(
                    response.status_code, ("upstream", f"模型服务暂时不可用（HTTP {response.status_code}）", True))
                raise LLMError(code, message, retryable)
            lines = response.aiter_lines()
            while True:
                try:
                    line = await before_deadline(anext(lines))
                except StopAsyncIteration:
                    break
                if not line.startswith("data:"):
                    continue  # includes the ": keep-alive" lines a busy server sends
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    usage.prompt_tokens = chunk["usage"].get("prompt_tokens")
                    usage.completion_tokens = chunk["usage"].get("completion_tokens")
                for choice in chunk.get("choices") or []:
                    if choice.get("finish_reason"):
                        usage.finish_reason = choice["finish_reason"]
                    delta = (choice.get("delta") or {}).get("content")
                    if delta:
                        deadline.start()
                        yield delta
        except httpx.TimeoutException:
            raise LLMError("timeout", "模型响应超时，请重试", True)
        except httpx.TransportError:
            raise LLMError("network", "无法连接模型服务，请检查网络", True)
        except json.JSONDecodeError:
            raise LLMError("upstream", "模型返回了无法解析的数据", True)
        finally:
            if response is not None:
                await response.aclose()


class OllamaClient:
    """Local Ollama through its native /api/chat, which (unlike its OpenAI endpoint) takes num_ctx.

    Accepts the same OpenAI-style messages as ChatClient. Native messages carry images separately
    from the text, so each text part opens a new message and the images after it join that message:
    a frame's "帧 F001 · 00:05" label travels with its picture.
    """

    def __init__(self, config: LLMConfig, *, transport: httpx.AsyncBaseTransport | None = None,
                 first_token_timeout: float | None = None, answer_timeout: float = ANSWER_TIMEOUT):
        self.config = config
        self.first_token_timeout = first_token_timeout or config.first_token_timeout
        self.answer_timeout = answer_timeout
        self.http = httpx.AsyncClient(base_url=config.base_url, transport=transport, trust_env=False,
                                      timeout=httpx.Timeout(None, connect=5))

    async def aclose(self) -> None:
        await self.http.aclose()

    @staticmethod
    def native_messages(messages: list[dict]) -> list[dict]:
        out = []
        for m in messages:
            if isinstance(m["content"], str):
                out.append({"role": m["role"], "content": m["content"]})
                continue
            current = None
            for part in m["content"]:
                if part["type"] == "text":
                    current = {"role": m["role"], "content": part["text"], "images": []}
                    out.append(current)
                elif part["type"] == "image_url":
                    if current is None:
                        current = {"role": m["role"], "content": "", "images": []}
                        out.append(current)
                    current["images"].append(part["image_url"]["url"].split(",", 1)[-1])
        return out

    def body(self, messages: list[dict], max_tokens: int) -> dict:
        return {
            "model": self.config.model, "messages": self.native_messages(messages), "stream": True,
            "think": False,  # thinking would delay the first word by minutes on a local model
            "keep_alive": "30m",
            "options": {"num_ctx": self.config.num_ctx, "num_predict": max_tokens, "temperature": 0.3},
        }

    async def stream(self, messages: list[dict], usage: Usage, max_tokens: int = 2048) -> AsyncIterator[str]:
        deadline = Deadline(self.first_token_timeout, self.answer_timeout)
        response = None
        try:
            request = self.http.build_request("POST", "/api/chat", json=self.body(messages, max_tokens))
            response = await deadline.wait(self.http.send(request, stream=True))
            if response.status_code == 404:
                raise LLMError("model_not_found", f"Ollama 里没有模型 {self.config.model}，请先 ollama pull {self.config.model}")
            if response.status_code >= 400:
                detail = (await response.aread()).decode(errors="replace")[:200]
                raise LLMError("upstream", f"Ollama 返回错误（HTTP {response.status_code}）：{detail}", True)
            lines = response.aiter_lines()
            while True:
                try:
                    line = await deadline.wait(anext(lines))
                except StopAsyncIteration:
                    break
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise LLMError("upstream", f"Ollama 出错：{chunk['error'][:200]}", True)
                delta = (chunk.get("message") or {}).get("content")
                if delta:
                    deadline.start()
                    yield delta
                if chunk.get("done"):
                    usage.prompt_tokens = chunk.get("prompt_eval_count")
                    usage.completion_tokens = chunk.get("eval_count")
                    usage.finish_reason = chunk.get("done_reason")
                    break
        except httpx.ConnectError:
            raise LLMError("network", "无法连接本地 Ollama，请确认它已启动（ollama serve）", True)
        except httpx.TransportError:
            raise LLMError("network", "与本地 Ollama 的连接中断", True)
        except json.JSONDecodeError:
            raise LLMError("upstream", "Ollama 返回了无法解析的数据", True)
        finally:
            if response is not None:
                await response.aclose()


def create_client(config: LLMConfig) -> ChatClient | OllamaClient:
    return OllamaClient(config) if config.provider == "ollama" else ChatClient(config)
