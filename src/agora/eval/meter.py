"""Hard-capped USD spend meter, attached to chat models via LangChain callbacks."""
from __future__ import annotations

import threading
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult

from agora.config import ModelSpec
from agora.ledger.budget import cost_of
from agora.ledger.types import Usage


class BudgetExceeded(Exception):
    """Raised from an LLM call once cumulative spend reaches the cap."""


def _count(v: Any) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0


class _Handler(BaseCallbackHandler):
    raise_error = True  # let BudgetExceeded propagate instead of being logged away
    run_inline = True

    def __init__(self, meter: SpendMeter, spec: ModelSpec):
        self.meter, self.spec = meter, spec

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for gens in response.generations:
            for gen in gens:
                message = getattr(gen, "message", None)
                usage = getattr(message, "usage_metadata", None) if isinstance(message, AIMessage) else None
                if usage:
                    self.meter._record(self.spec, usage)
        self.meter.check()


class SpendMeter:
    def __init__(self, cap_usd: float):
        self.cap_usd = cap_usd
        self._lock = threading.Lock()
        self._by_model: dict[str, float] = {}

    def attach(self, model: BaseChatModel, spec: ModelSpec) -> BaseChatModel:
        existing = model.callbacks
        if existing is None:
            handlers: list = []
        elif isinstance(existing, list):
            handlers = list(existing)
        else:  # a BaseCallbackManager
            handlers = list(existing.handlers)
        handlers.append(_Handler(self, spec))
        model.callbacks = handlers
        return model

    def _record(self, spec: ModelSpec, usage: Any) -> None:
        inp = _count(usage.get("input_tokens"))
        cached = min(_count((usage.get("input_token_details") or {}).get("cache_read")), inp)
        out = _count(usage.get("output_tokens"))
        usd = cost_of(spec, Usage(input_tokens=inp, cached_input_tokens=cached, output_tokens=out))
        with self._lock:
            self._by_model[spec.key] = self._by_model.get(spec.key, 0.0) + usd

    def check(self) -> None:
        """Raise BudgetExceeded if the cap has been reached (callers may also poll this)."""
        total = self.total_usd
        if total >= self.cap_usd:
            raise BudgetExceeded(f"spend ${total:.4f} reached cap ${self.cap_usd:.4f}")

    @property
    def total_usd(self) -> float:
        with self._lock:
            return sum(self._by_model.values())

    @property
    def by_model(self) -> dict[str, float]:
        with self._lock:
            return dict(self._by_model)

    def reset(self) -> None:
        with self._lock:
            self._by_model.clear()
