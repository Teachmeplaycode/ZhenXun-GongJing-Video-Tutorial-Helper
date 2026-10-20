"""One answer's unified budget, call cost and wait record (task B, issue #30).

Three jobs, all configurable through environment variables (unset / unparsable = no limit;
the defaults keep today's normal Q&A untouched):

  1. Budget gates — refuse further work when an answer has used too much, while the model can
     still answer from what it already has (the refusal goes back as a tool result, not an error):

       LLM_BUDGET_MAX_EXTERNAL     web_search / fetch_page / browse / search_papers calls combined
       LLM_BUDGET_MAX_TOOL_CALLS   tool calls actually executed (failed ones included)
       LLM_BUDGET_MAX_FRAMES       frames read from the video (view_frames / replay images,
                                   measure_motion's decoded frames too: they are read, just not sent)
       LLM_BUDGET_MAX_SECONDS      wall-clock time of the whole answer; once over, further model
                                   rounds get no tools so the model has to wrap up
       LLM_BUDGET_MAX_TOKENS       prompt + completion tokens combined, same wrap-up behaviour

     Frame / external / call limits are soft: a call that starts under the limit may push the
     count past it; the next one is refused. tool_calls in run.completed keeps its old meaning
     (calls the model asked for, refused ones included); budget.tool_calls counts executions.

  2. Metering — every main-model call's input/output tokens and first-word wait, the whole
     answer's totals, longest wait, plus the intent fallback's usage/elapsed_ms metadata when
     module A provides it (read with getattr: absent metadata is simply not counted, and
     modules/agent/intent.py itself is never touched).

  3. Cost — estimated in CNY from per-million-token prices:

       LLM_PRICE_IN_M   ¥ per 1M input tokens
       LLM_PRICE_OUT_M  ¥ per 1M output tokens

     Both must be set and every call's usage known for a cost to exist; otherwise the cost is
     None ("不可计算") and is never reported as ¥0. Reference prices (checked 2026-10-20,
     https://api-docs.deepseek.com/quick_start/pricing, deepseek-flash, per 1M tokens, USD):
     input cache-miss $0.15 off-peak / $0.30 peak, input cache-hit $0.003–0.006, output
     $0.60 off-peak / $1.20 peak. The stream's usage does not split cache hits, so configuring
     the cache-miss price is the conservative choice.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

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
    "seconds": "本次回答的时长已达到上限（{limit} 秒）。请立即根据已有信息收尾作答，不要再调用工具。",
    "tokens": "本次回答的 token 用量已达到上限（{limit}）。请立即根据已有信息收尾作答，不要再调用工具。",
}


def _number(raw: str) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def limits(env: dict | None = None) -> dict[str, float | None]:
    """The configured caps; None = unlimited. `env` defaults to the process environment."""
    source = os.environ if env is None else env
    return {name: _number(source.get(var, "")) for name, var in LIMIT_ENV.items()}


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
        if (self.tokens_known and self.caps["tokens"] is not None
                and self.prompt_tokens + self.completion_tokens >= self.caps["tokens"]):
            return self._hit("tokens")
        if self.caps["tool_calls"] is not None and self.tool_calls >= self.caps["tool_calls"]:
            return self._hit("tool_calls")
        if name in EXTERNAL_TOOLS and self.caps["external"] is not None \
                and self.external_calls >= self.caps["external"]:
            return self._hit("external")
        if name in FRAME_TOOLS and self.caps["frames"] is not None and self.frames_read >= self.caps["frames"]:
            return self._hit("frames")
        return None

    def gate_round(self) -> str | None:
        """Whether the next model round must be the last (no tools) because time/tokens ran out."""
        if self.caps["seconds"] is not None and self.elapsed() >= self.caps["seconds"]:
            return self._hit("seconds")
        if (self.tokens_known and self.caps["tokens"] is not None
                and self.prompt_tokens + self.completion_tokens >= self.caps["tokens"]):
            return self._hit("tokens")
        return None

    def deny_text(self, cap: str) -> str:
        limit = self.caps[cap]
        return DENY_TEXT[cap].format(limit=int(limit) if limit is not None else 0)

    def tool_done(self, name: str, count: int = 0) -> None:
        """Account one executed tool call (failed ones too: the attempt cost the budget)."""
        self.tool_calls += 1
        if name in EXTERNAL_TOOLS:
            self.external_calls += 1
        if name in FRAME_TOOLS:
            self.frames_read += max(0, count)

    def tool_refused(self) -> None:
        self.blocked_calls += 1

    # ---- main-model metering ----------------------------------------------------------
    def llm_started(self) -> None:
        self._call_started, self._first_word_at = time.perf_counter(), None

    def llm_first_word(self) -> None:
        if self._call_started is not None and self._first_word_at is None:
            self._first_word_at = time.perf_counter()
            self._note_wait(int((self._first_word_at - self._call_started) * 1000))

    def llm_finished(self, prompt_tokens: int | None, completion_tokens: int | None) -> None:
        """A stream that ended (however it ended): tokens and, with no word at all, the full wait."""
        self.llm_calls += 1
        if prompt_tokens is None or completion_tokens is None:
            self.tokens_known = False
        else:
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
        if self._first_word_at is None and self._call_started is not None:
            self._note_wait(int((time.perf_counter() - self._call_started) * 1000))
        self._call_started = self._first_word_at = None

    def llm_failed(self) -> None:
        """A stream that broke: its usage cannot be known, so no cost estimate is possible."""
        self.llm_calls += 1
        self.llm_failures += 1
        self.tokens_known = False
        if self._call_started is not None and self._first_word_at is None:
            self._note_wait(int((time.perf_counter() - self._call_started) * 1000))
        self._call_started = self._first_word_at = None

    def _note_wait(self, ms: int) -> None:
        self.max_wait_ms = ms if self.max_wait_ms is None else max(self.max_wait_ms, ms)

    # ---- the intent fallback (module A) -----------------------------------------------
    def add_side(self, usage, elapsed_ms) -> None:
        """Count the intent fallback's usage/elapsed_ms when module A provides them on Intent.

        `usage` may be a Usage-like object (prompt_tokens / completion_tokens) or a dict
        (either key spelling); anything else — including the attrs being absent, which is
        today's intent.py — is simply not counted. A broken usage marks the cost unknowable
        rather than guessing zero.
        """
        if isinstance(elapsed_ms, (int, float)) and elapsed_ms >= 0:
            self._note_wait(int(elapsed_ms))
        prompt, completion = side_tokens(usage)
        if prompt is None and completion is None:
            return
        if prompt is None or completion is None:
            self.tokens_known = False
            return
        self.prompt_tokens += prompt
        self.completion_tokens += completion

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
        cny = (self.prompt_tokens * in_price + self.completion_tokens * out_price) / 1_000_000
        return {"cny": round(cny, 6), "computable": True, "reason": None}

    def cost_text(self) -> str:
        cost = self.cost()
        if cost["computable"]:
            return f"约￥{cost['cny']:.4f}"
        return f"费用不可计算（{cost['reason']}）"

    def snapshot(self, elapsed_ms: int | None = None) -> dict:
        """Structured fields for run.completed and the answer log line."""
        return {"external_calls": self.external_calls, "tool_calls": self.tool_calls,
                "blocked_calls": self.blocked_calls, "frames_read": self.frames_read,
                "limit_hits": list(self.limit_hits),
                "limits": {k: v for k, v in self.caps.items() if v is not None},
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "tokens_known": self.tokens_known, "llm_calls": self.llm_calls,
                "llm_failures": self.llm_failures, "max_wait_ms": self.max_wait_ms,
                "elapsed_ms": elapsed_ms if elapsed_ms is not None else int(self.elapsed() * 1000),
                "cost": self.cost()}


def side_tokens(usage) -> tuple[int | None, int | None]:
    """(prompt, completion) tokens out of an intent fallback's usage metadata, or (None, None)."""
    if usage is None:
        return None, None
    if isinstance(usage, dict):
        pick = lambda *keys: next((usage[k] for k in keys if isinstance(usage.get(k), int)), None)  # noqa: E731
        return pick("prompt", "prompt_tokens"), pick("completion", "completion_tokens")
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    return (prompt if isinstance(prompt, int) else None,
            completion if isinstance(completion, int) else None)
