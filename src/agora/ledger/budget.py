"""Token spend accounting with tiered, cache-aware per-model pricing."""
from __future__ import annotations

from typing import Callable

from agora.config import ModelSpec
from agora.ledger.db import Database
from agora.ledger.types import LedgerError, Usage


def cost_of(spec: ModelSpec, usage: Usage) -> float:
    """USD cost of one call. `usage.input_tokens` includes the cached tokens."""
    inp, cached, out = usage.input_tokens, usage.cached_input_tokens, usage.output_tokens
    if inp < 0 or cached < 0 or out < 0:
        raise LedgerError("token counts must not be negative")
    if cached > inp:
        raise LedgerError(f"cached tokens ({cached}) exceed input tokens ({inp})")
    price = spec.price
    best = -1
    for tier in spec.tiers:
        if tier.above_prompt_tokens < inp and tier.above_prompt_tokens > best:
            best, price = tier.above_prompt_tokens, tier.price
    return ((inp - cached) * price.in_per_m + cached * price.cached_per_m + out * price.out_per_m) / 1e6


class BudgetLedger:
    def __init__(self, db: Database, prices: dict[str, ModelSpec], clock: Callable[[], float]):
        self.db = db
        self.prices = prices
        self.clock = clock

    def charge(self, agent_id: str, model_key: str, usage: Usage) -> float:
        spec = self.prices.get(model_key)
        if spec is None:
            raise LedgerError(f"unknown model key: {model_key!r}")
        usd = cost_of(spec, usage)
        with self.db.write() as conn:
            conn.execute(
                "INSERT INTO spend(agent_id, model_key, input_tokens, cached_input_tokens,"
                " output_tokens, usd, created_at) VALUES (?,?,?,?,?,?,?)",
                (agent_id, model_key, usage.input_tokens, usage.cached_input_tokens,
                 usage.output_tokens, usd, self.clock()),
            )
        return usd

    def spent(self, agent_id: str | None = None) -> float:
        if agent_id is None:
            rows = self.db.read("SELECT COALESCE(SUM(usd), 0) AS s FROM spend")
        else:
            rows = self.db.read("SELECT COALESCE(SUM(usd), 0) AS s FROM spend WHERE agent_id=?", (agent_id,))
        return float(rows[0]["s"])

    def peer_exhausted(self, agent_id: str, peer_usd: float) -> bool:
        """True once the agent's spend has reached `peer_usd` (spent >= peer_usd)."""
        return self.spent(agent_id) >= peer_usd
