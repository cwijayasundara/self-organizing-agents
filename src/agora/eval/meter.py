"""Hard-capped USD spend meter, attached to chat models via LangChain callbacks."""
from __future__ import annotations

import logging
import threading
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult

from agora.config import ModelSpec
from agora.ledger.budget import cost_of
from agora.ledger.types import Usage


log = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """Raised from an LLM call once cumulative spend reaches the cap."""


def _count(v: Any) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError, OverflowError):
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
                if isinstance(usage, dict) and usage:
                    try:
                        self.meter._record(self.spec, usage)
                    except Exception:  # unusable usage is treated as absent
                        log.debug("ignoring unusable usage_metadata: %r", usage, exc_info=True)
        self.meter.check()


class SpendMeter:
    def __init__(self, cap_usd: float):
        self._cap_usd = cap_usd
        self._lock = threading.Lock()
        self._by_model: dict[str, float] = {}

    @property
    def cap_usd(self) -> float:
        return self._cap_usd

    @staticmethod
    def _handlers(model: BaseChatModel) -> list:
        existing = model.callbacks
        if existing is None:
            return []
        if isinstance(existing, list):
            return list(existing)
        return list(existing.handlers)  # a BaseCallbackManager

    def attach(self, model: BaseChatModel, spec: ModelSpec) -> BaseChatModel:
        """Idempotent per meter: re-attaching replaces this meter's spec. Several meters may
        be attached to one model; each counts independently."""
        handlers = self._handlers(model)
        mine = [h for h in handlers if isinstance(h, _Handler) and h.meter is self]
        if mine:
            mine[0].spec = spec
            handlers = [h for h in handlers if h not in mine[1:]]
        else:
            handlers.append(_Handler(self, spec))
        model.callbacks = handlers
        return model

    def detach(self, model: BaseChatModel) -> BaseChatModel:
        """Remove this meter's handler(s); other callbacks are preserved."""
        model.callbacks = [h for h in self._handlers(model) if not (isinstance(h, _Handler) and h.meter is self)]
        return model

    def _record(self, spec: ModelSpec, usage: Any) -> None:
        inp = _count(usage.get("input_tokens"))
        details = usage.get("input_token_details")
        cached = min(_count(details.get("cache_read")) if isinstance(details, dict) else 0, inp)
        out = _count(usage.get("output_tokens"))
        usd = cost_of(spec, Usage(input_tokens=inp, cached_input_tokens=cached, output_tokens=out))
        with self._lock:
            self._by_model[spec.key] = self._by_model.get(spec.key, 0.0) + usd

    def check(self) -> None:
        """Raise BudgetExceeded if the cap has been reached (callers may also poll this)."""
        total = self.total_usd
        if total >= self.cap_usd:
            raise BudgetExceeded(f"spend ${total:.6f} reached cap ${self.cap_usd:.6f}")

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


def detach_all(model: BaseChatModel) -> BaseChatModel:
    """Remove every meter handler (of any meter) from a reused model."""
    model.callbacks = [h for h in SpendMeter._handlers(model) if not isinstance(h, _Handler)]
    return model
