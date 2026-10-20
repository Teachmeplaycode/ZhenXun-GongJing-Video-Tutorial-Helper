"""One-answer budget and cost metering. Unset limits preserve existing behavior.

Call/external counters reserve before execution (failed attempts count). Initial selected
frames count too; view_frames is clipped and replay/motion require their worst-case quota.
frames_reserved is conservative logical tool quota, not a count of physical retry decodes.
Seconds bound outstanding awaits through cancellation; synchronous/native cleanup still
requires cooperative cancellation. Tokens use reported known lower bounds and output caps:
provider input size/unknown usage cannot be predicted, so this is not a hard total-token cap.
Prices LLM_PRICE_IN_M/LLM_PRICE_OUT_M are CNY per million. No default or currency conversion
is assumed; unknown price or any incomplete call makes cost unavailable. Configure the
actual provider/model price (official source https://api-docs.deepseek.com/quick_start/pricing).
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from dataclasses import dataclass, field
from contextlib import aclosing

from modules.llm import LLMError

EXTERNAL_TOOLS = {"web_search", "fetch_page", "search_papers", "browse"}
FRAME_TOOLS = {"view_frames", "replay", "measure_motion"}

LIMIT_ENV = {"external": "LLM_BUDGET_MAX_EXTERNAL", "tool_calls": "LLM_BUDGET_MAX_TOOL_CALLS",
             "frames": "LLM_BUDGET_MAX_FRAMES", "seconds": "LLM_BUDGET_MAX_SECONDS",
             "tokens": "LLM_BUDGET_MAX_TOKENS"}
DENY_TEXT = {
    "external": "本次回答的外部访问次数已达到上限（{limit} 次：web_search / fetch_page / browse / search_papers）。"
                "这次调用没有执行。请根据已获取的信息回答，并说明哪些内容未能进一步核实。",
    "tool_calls": "本次回答的工具调用次数已达到上限（{limit} 次）。这次调用没有执行。请直接根据已有的画面、转写和工具结果回答。",
    "frames": "本次回答读取的帧数已达到上限（{limit} 帧）。这次调用没有执行。请根据已有画面回答。",
    "seconds": "本次回答的时长已达到上限（{limit} 秒），已停止新的模型和工具调用。已有内容已保留。",
    "tokens": "本次回答已报告的 token 用量已达到上限（{limit}），已停止新的模型和工具调用。已有内容已保留。",
}


def _number(raw: str) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def limits(env: dict | None = None) -> dict[str, float | None]:
    """The configured caps; None = unlimited. `env` defaults to the process environment."""
    source = os.environ if env is None else env
    parsed = {name: _number(source.get(var, "")) for name, var in LIMIT_ENV.items()}
    return {k: (int(v) if v is not None and k != "seconds" else v) for k, v in parsed.items()}


def prices(env: dict | None = None) -> tuple[float | None, float | None]:
    """(¥ per 1M input tokens, ¥ per 1M output tokens); either missing means no cost estimate."""
    source = os.environ if env is None else env
    return _number(source.get("LLM_PRICE_IN_M", "")), _number(source.get("LLM_PRICE_OUT_M", ""))


@dataclass
class AnswerBudget:
    """Counters and call records for one answer (see the module docstring for the口径)."""
    caps: dict[str, float | None] = field(default_factory=limits)
    external_calls: int = 0
    tool_calls: int = 0        # executed calls, failures included; refused calls are not here
    blocked_calls: int = 0
    frames_read: int = 0
    frames_reserved: int = 0
    output_reserved: int = 0
    unreported_token_reserve: int = 0
    calls: list[dict] = field(default_factory=list)
    active: dict = field(default_factory=dict, repr=False)
    prompt_complete: bool = True
    completion_complete: bool = True
    limit_hits: list[str] = field(default_factory=list)  # each cap, in the order first hit
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    tokens_known: bool = True  # every metered call reported its usage
    max_wait_ms: int | None = None
    started: float = field(default_factory=time.perf_counter)
    _call_started: float | None = field(default=None, repr=False)
    _first_word_at: float | None = field(default=None, repr=False)

    # ---- budget gates -----------------------------------------------------------------
    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def _hit(self, cap: str) -> str:
        if cap not in self.limit_hits:
            self.limit_hits.append(cap)
        return cap

    def check_tool(self, name: str) -> str | None:
        """Why this tool call must be refused (a cap name), or None when it may run.

        Time and token caps refuse every tool; the others only the kind they limit.
        Called before the tool runs; `tool_done` after, whatever happened.
        """
        if self.caps["seconds"] is not None and self.elapsed() >= self.caps["seconds"]:
            return self._hit("seconds")
        if (self.caps["tokens"] is not None
                and self.prompt_tokens + self.completion_tokens + self.output_reserved + self.unreported_token_reserve >= self.caps["tokens"]):
            return self._hit("tokens")
        if self.caps["tool_calls"] is not None and self.tool_calls >= self.caps["tool_calls"]:
            return self._hit("tool_calls")
        if name in EXTERNAL_TOOLS and self.caps["external"] is not None \
                and self.external_calls >= self.caps["external"]:
            return self._hit("external")
        if name in FRAME_TOOLS and self.caps["frames"] is not None and self.frames_reserved >= self.caps["frames"]:
            return self._hit("frames")
        return None

    def gate_round(self) -> str | None:
        """Why no further model request may start (time or reported token lower bound)."""
        if self.caps["seconds"] is not None and self.elapsed() >= self.caps["seconds"]:
            return self._hit("seconds")
        if (self.caps["tokens"] is not None
                and self.prompt_tokens + self.completion_tokens + self.output_reserved + self.unreported_token_reserve >= self.caps["tokens"]):
            return self._hit("tokens")
        return None

    def deny_text(self, cap: str) -> str:
        limit = self.caps[cap]
        return DENY_TEXT[cap].format(limit=f"{limit:g}" if limit is not None else "0")

    def tool_done(self, name: str, count: int = 0) -> None:
        """Account one executed tool call (failed ones too: the attempt cost the budget)."""
        self.tool_calls += 1
        if name in EXTERNAL_TOOLS:
            self.external_calls += 1
        if name in FRAME_TOOLS:
            self.frames_read += max(0, count)
            self.frames_reserved += max(0, count)

    def tool_refused(self) -> None:
        self.blocked_calls += 1

    # ---- main-model metering ----------------------------------------------------------
    def llm_started(self) -> None:
        self._call_started, self._first_word_at = time.perf_counter(), None

    def llm_first_word(self) -> None:
        if self._call_started is not None and self._first_word_at is None:
            self._first_word_at = time.perf_counter()
            self._note_wait(int((self._first_word_at - self._call_started) * 1000))

    def llm_finished(self, prompt_tokens, completion_tokens):
        wait = None
        if self._call_started is not None:
            wait = int(((self._first_word_at or time.perf_counter()) - self._call_started) * 1000)
        self.record(prompt_tokens, completion_tokens, wait_ms=wait)
        self._call_started = self._first_word_at = None

    def llm_failed(self):
        wait = None if self._call_started is None else int(((self._first_word_at or time.perf_counter()) - self._call_started) * 1000)
        self.record(None, None, wait_ms=wait, status="error")
        self._call_started = self._first_word_at = None

    def _note_wait(self, ms: int) -> None:
        self.max_wait_ms = ms if self.max_wait_ms is None else max(self.max_wait_ms, ms)

    # ---- the intent fallback (module A) -----------------------------------------------
    def add_side(self, usage, elapsed_ms) -> None:
        """A's metadata is absent for no request, but nullable fields mean a real unknown call."""
        if isinstance(elapsed_ms, (int, float)) and not isinstance(elapsed_ms, bool) and math.isfinite(elapsed_ms) and elapsed_ms >= 0:
            self._note_wait(int(elapsed_ms))
        if usage is None:
            return
        p, c = side_tokens(usage)
        self.record(p, c, wait_ms=None, status="intent")

    def record(self, prompt, completion, *, wait_ms=None, status="done"):
        p, c = token(prompt), token(completion)
        self.llm_calls += 1
        failed = status in {"error", "cancelled"}
        self.llm_failures += int(failed)
        self.prompt_tokens += p or 0
        self.completion_tokens += c or 0
        self.prompt_complete &= p is not None and not failed
        self.completion_complete &= c is not None and not failed
        self.tokens_known = self.prompt_complete and self.completion_complete
        if wait_ms is not None:
            self._note_wait(wait_ms)
        self.calls.append({"prompt": p, "completion": c, "wait_ms": wait_ms, "status": status})

    def finish_call(self, key, status="done"):
        call = self.active.pop(key, None)
        if call is None:
            return
        p, c = side_tokens(call["usage"])
        allowance = call.get("allowance", 0)
        self.output_reserved -= allowance
        if p is None or c is None or status in {"error", "cancelled"}:
            # Unknown/cancelled output may still be charged: do not make its allowance
            # available to another call. Completed known usage reconciles normally.
            self.unreported_token_reserve += max(0, allowance - (c or 0))
        self.record(p, c, wait_ms=int(((call["first"] or time.perf_counter()) - call["began"]) * 1000), status=status)

    def settle_calls(self, keys):
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        for key in list(keys):
            call = self.active.get(key)
            if call is None:
                continue
            task = call.get("task")
            if task is not None and task is not current and not task.done():
                task.cancel()
            self.finish_call(key, "cancelled")

    def cancel_open_calls(self):
        self.settle_calls(list(self.active))

    def usage(self):
        return {"prompt": self.prompt_tokens if self.prompt_complete else None,
                "completion": self.completion_tokens if self.completion_complete else None,
                "known_prompt": self.prompt_tokens, "known_completion": self.completion_tokens,
                "complete": self.tokens_known}

    def remaining_seconds(self):
        cap = self.caps["seconds"]
        return None if cap is None else max(0., cap - self.elapsed())

    async def bounded(self, awaitable):
        """The answer's remaining wall time applies to each outstanding await, not just rounds."""
        remaining = self.remaining_seconds()
        if remaining is None:
            return await awaitable
        if remaining <= 0:
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise BudgetExceeded(self, "seconds")
        try:
            return await asyncio.wait_for(awaitable, remaining)
        except TimeoutError as exc:
            raise BudgetExceeded(self, "seconds") from exc

    async def iterate(self, stream):
        try:
            while True:
                try:
                    item = await self.bounded(anext(stream))
                except StopAsyncIteration:
                    return
                yield item
        finally:
            await stream.aclose()

    def select_frames(self, count):
        cap = self.caps["frames"]
        n = count if cap is None else min(count, max(0, int(cap) - self.frames_reserved))
        if n < count:
            self._hit("frames")
        self.frames_reserved += n
        self.frames_read += n
        return n

    def prepare_tool(self, name, args):
        """Reserve before awaiting: parallel callers cannot each spend the same remaining slot.

        view_frames is clipped. replay/motion reserve their conservative per-call maximum;
        if it will not fit, refuse before decoding. Failed attempts keep their reservation.
        """
        args = dict(args)
        denied = self.check_tool(name)
        reserve = 0
        if not denied and name in FRAME_TOOLS:
            if name == "view_frames":
                try:
                    reserve = max(1, min(6, int(args.get("count", 4))))
                except (ValueError, TypeError, OverflowError):
                    reserve = 4
            else:
                reserve = 16 if name == "replay" else 300
            cap = self.caps["frames"]
            remaining = reserve if cap is None else max(0, int(cap) - self.frames_reserved)
            if name == "view_frames":
                reserve = min(reserve, remaining)
                args["count"] = reserve
            if reserve == 0 or reserve > remaining:
                denied = self._hit("frames")
        if denied:
            self.tool_refused()
            return denied, args
        self.tool_calls += 1
        self.external_calls += int(name in EXTERNAL_TOOLS)
        self.frames_reserved += reserve
        return None, args

    def tool_result(self, name, count):
        if name in FRAME_TOOLS:
            self.frames_read += max(0, count)

    # ---- reports ----------------------------------------------------------------------
    def cost(self) -> dict:
        """{cny: float | None, computable: bool, reason: str | None} — never a made-up ¥0."""
        in_price, out_price = prices()
        if in_price is None or out_price is None:
            return {"cny": None, "computable": False, "reason": "单价未配置（LLM_PRICE_IN_M / LLM_PRICE_OUT_M）"}
        if self.llm_calls == 0:
            return {"cny": None, "computable": False, "reason": "没有模型调用"}
        if not self.tokens_known:
            return {"cny": None, "computable": False, "reason": "有调用的 token 用量未知"}
        try:
            cny = (self.prompt_tokens * in_price + self.completion_tokens * out_price) / 1_000_000
        except OverflowError:
            cny = math.inf
        if not math.isfinite(cny):
            return {"cny": None, "computable": False, "reason": "费用超出可计算数值范围"}
        return {"cny": round(cny, 6), "computable": True, "reason": None}

    def cost_text(self) -> str:
        cost = self.cost()
        if cost["computable"]:
            return f"约￥{cost['cny']:.4f}"
        return f"费用不可计算（{cost['reason']}）"

    def snapshot(self, elapsed_ms: int | None = None) -> dict:
        """Structured fields for run.completed and the answer log line."""
        return {"external_calls": self.external_calls, "tool_calls": self.tool_calls,
                "blocked_calls": self.blocked_calls, "frames_read": self.frames_read, "frames_reserved": self.frames_reserved,
                "output_reserved": self.output_reserved, "unreported_token_reserve": self.unreported_token_reserve,
                "limit_hits": list(self.limit_hits),
                "limits": {k: v for k, v in self.caps.items() if v is not None},
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "tokens_known": self.tokens_known, "token_limit_basis": "reported_lower_bound", "llm_calls": self.llm_calls,
                "llm_failures": self.llm_failures, "max_wait_ms": self.max_wait_ms,
                "elapsed_ms": elapsed_ms if elapsed_ms is not None else int(self.elapsed() * 1000),
                "calls": list(self.calls), "usage": self.usage(), "cost": self.cost()}


def token(value):
    return value if type(value) is int and value >= 0 else None


def side_tokens(usage) -> tuple[int | None, int | None]:
    if usage is None:
        return None, None
    if isinstance(usage, dict):
        def pick(*keys):
            return next((token(usage[k]) for k in keys if k in usage), None)
        return pick("prompt", "prompt_tokens"), pick("completion", "completion_tokens")
    return token(getattr(usage, "prompt_tokens", None)), token(getattr(usage, "completion_tokens", None))


class BudgetExceeded(LLMError):
    def __init__(self, spend, cap):
        spend._hit(cap)
        self.cap = cap
        super().__init__("budget", spend.deny_text(cap), False)


class MeteredClient:
    """Per-answer proxy, including nested/concurrent skills. No mutation of shared clients."""
    def __init__(self, client, spend):
        self.client, self.spend = client, spend

    def __getattr__(self, key):
        return getattr(self.client, key)

    async def stream(self, messages, usage, max_tokens=2048, **kwargs):
        b = self.spend
        over = b.gate_round()
        if over:
            raise BudgetExceeded(b, over)
        cap = b.caps["tokens"]
        allowance = 0
        if cap is not None:
            # Input size is provider-reported only; enforce remaining known lower bound
            # and cap this request's output, without claiming a hard total-token bound.
            remaining = int(cap - b.prompt_tokens - b.completion_tokens - b.output_reserved - b.unreported_token_reserve)
            if remaining <= 0:
                raise BudgetExceeded(b, "tokens")
            max_tokens = min(max_tokens, remaining)
            allowance = max_tokens
            b.output_reserved += allowance
        began, first, status = time.perf_counter(), None, "done"
        key = object()
        b.active[key] = {"usage": usage, "began": began, "first": None,
                         "allowance": allowance, "task": asyncio.current_task()}
        stream = self.client.stream(messages, usage, max_tokens=max_tokens, **kwargs)
        try:
            async with aclosing(b.iterate(stream)) as owned_stream:
                async for delta in owned_stream:
                    if first is None and delta:
                        first = time.perf_counter()
                        if key in b.active:
                            b.active[key]["first"] = first
                    yield delta
        except (asyncio.CancelledError, GeneratorExit):
            status = "cancelled"
            raise
        except BaseException:
            status = "error"
            raise
        finally:
            b.finish_call(key, status)
