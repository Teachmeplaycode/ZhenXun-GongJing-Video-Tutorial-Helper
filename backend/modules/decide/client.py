"""Typed decisions with probabilities, in the style of TypeSafe's Jev ("System One"): a choice among
named options, or a yes/no probability (noul). Nothing is generated: the model reads a question whose
options are lettered A, B, C… and the answer is the probability it puts on each letter as the next
token, so the output can only ever be one of the options.

Runs on the local Ollama (Jev itself is hosted-only). A 36-case comparison on 2026-10-15 put
qwen3.5:9b this way level with Kev-4B (92 %, Brier 0.16) and ahead of decider-4b and Kev-0.8B;
see backend/README.md.

  DECISION          on (default) / off
  DECISION_MODEL    default qwen3.5:9b
  DECISION_URL      default http://localhost:11434
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

import httpx

from ..settings import settings

LETTERS = "ABCDEFGHIJKLMNOP"
TOP_LOGPROBS = 20


@dataclass
class Decision:
    probabilities: dict[str, float]
    model: str
    latency_ms: float
    extra: dict = field(default_factory=dict)

    @property
    def choice(self) -> str:
        return max(self.probabilities, key=self.probabilities.get)

    @property
    def confidence(self) -> float:
        """Jev's definition: 0 when the probabilities are uniform, 1 when one option has them all."""
        n = len(self.probabilities)
        return (n * max(self.probabilities.values()) - 1) / (n - 1) if n > 1 else 1.0


def enabled() -> bool:
    return settings().get("DECISION", "on").lower() not in ("off", "0", "false")


class Decider:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, log=None):
        config = settings()
        self.model = config.get("DECISION_MODEL", "qwen3.5:9b")
        self.http = httpx.AsyncClient(base_url=config.get("DECISION_URL", "http://localhost:11434").rstrip("/"),
                                      transport=transport, trust_env=False, timeout=httpx.Timeout(120, connect=3))
        self.log = log  # optional callable(task, state, question, decision): keeps data for calibration/training

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _letters(self, prompt: str, n: int) -> dict[str, float]:
        response = await self.http.post("/api/chat", json={
            "model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False,
            "keep_alive": "30m", "logprobs": True, "top_logprobs": TOP_LOGPROBS,
            "options": {"num_predict": 1, "temperature": 0}})
        response.raise_for_status()
        steps = response.json().get("logprobs") or []
        if not steps:
            raise ValueError("model returned no logprobs (needs Ollama ≥ 0.12 and a model that supports them)")
        mass: dict[str, float] = defaultdict(float)
        for alt in steps[0].get("top_logprobs") or []:
            letter = alt["token"].strip()
            if letter in LETTERS[:n]:
                mass[letter] += math.exp(alt["logprob"])  # "A" and " A" are the same answer
        total = sum(mass.values())
        if total <= 0:
            raise ValueError("none of the option letters were among the likely next tokens")
        return {letter: mass.get(letter, 0.0) / total for letter in LETTERS[:n]}

    async def choice(self, state: str, instructions: str, criteria: dict[str, str], *, task: str = "") -> Decision:
        """Pick one of `criteria` (name → description). Raises on any failure; callers fall back."""
        names = list(criteria)
        body = "\n".join(f"{LETTERS[i]}. {criteria[name]}" for i, name in enumerate(names))
        prompt = f"State:\n{state}\n\nQuestion: {instructions}\n{body}\nAnswer with a single letter."
        started = time.perf_counter()
        letters = await self._letters(prompt, len(names))
        decision = Decision({name: letters[LETTERS[i]] for i, name in enumerate(names)}, self.model,
                            round((time.perf_counter() - started) * 1000, 1))
        if self.log:
            self.log(task or "choice", state, {"instructions": instructions, "criteria": criteria}, decision)
        return decision

    async def warm(self) -> None:
        """Load the model ahead of the first real decision (loading takes ~5 s; a decision ~0.2 s)."""
        try:
            await self.http.post("/api/chat", json={"model": self.model, "messages": [], "keep_alive": "30m"})
        except httpx.HTTPError:
            pass  # Ollama not running: the first decision will fail and callers fall back

    async def noul(self, state: str, instructions: str, *, task: str = "") -> float:
        """Probability that the answer to a yes/no question is yes."""
        d = await self.choice(state, instructions, {"yes": "是", "no": "否"}, task=task or "noul")
        return d.probabilities["yes"]
