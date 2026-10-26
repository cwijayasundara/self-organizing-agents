"""Roster configuration: models, peers, budget and validation."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

MAX_PEERS = 10


class ConfigError(ValueError):
    """Raised for any roster validation failure."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriceSpec(_Strict):
    in_per_m: float
    cached_per_m: float
    out_per_m: float


class PriceTier(_Strict):
    above_prompt_tokens: int
    price: PriceSpec


class ModelSpec(_Strict):
    key: str = ""
    provider: Literal["fireworks", "anthropic", "openai"]
    id: str
    family: str
    price: PriceSpec
    tiers: list[PriceTier] = Field(default_factory=list)
    reasoning_effort: str | None = None
    effort: str | None = None
    temperature: float | None = None
    api: Literal["chat", "responses"] = "chat"
    max_prompt_tokens: int | None = None
    experiment: bool = False

    @model_validator(mode="after")
    def _check(self) -> ModelSpec:
        if self.id == "auto" and not self.experiment:
            raise ValueError(f"model {self.key!r}: id 'auto' requires experiment: true")
        if self.provider == "anthropic" and self.temperature is not None:
            raise ValueError(f"model {self.key!r}: anthropic models must not set temperature")
        if self.provider == "openai" and self.api == "chat" and self.reasoning_effort != "none":
            raise ValueError(
                f"model {self.key!r}: openai chat api needs reasoning_effort 'none'; "
                "use api: responses for reasoning"
            )
        return self


class PeerSpec(_Strict):
    id: str
    model: str
    lens: str = ""
    peer_usd: float | None = None


class BudgetSpec(_Strict):
    swarm_usd: float
    peer_usd: float
    wall_clock_s: int
    episode_recursion_limit: int = 100
    lease_s: int = 1200
    stagger_s: float = 12
    idle_poll_s: float = 15
    stuck_turn_s: float = 900
    stall_after_s: float = 300
    warn_fractions: tuple[float, float] = (0.85, 0.97)


class ReviewPolicy(_Strict):
    reviewer_family_must_differ: bool = True


class RosterConfig(_Strict):
    run_name: str
    models: dict[str, ModelSpec]
    peers: list[PeerSpec]
    budget: BudgetSpec
    review_policy: ReviewPolicy = Field(default_factory=ReviewPolicy)
    judge: ModelSpec | None = None
    data_dir: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_keys(cls, data):
        if isinstance(data, dict) and isinstance(data.get("models"), dict):
            data = dict(data)
            data["models"] = {
                k: ({**v, "key": k} if isinstance(v, dict) else v)
                for k, v in data["models"].items()
            }
        return data

    @model_validator(mode="after")
    def _check(self) -> RosterConfig:
        if len(self.peers) > MAX_PEERS:
            raise ValueError(f"roster allows at most {MAX_PEERS} peers, got {len(self.peers)}")
        seen: set[str] = set()
        for p in self.peers:
            if p.id in seen:
                raise ValueError(f"duplicate peer id {p.id!r}")
            seen.add(p.id)
            if p.model not in self.models:
                raise ValueError(f"peer {p.id!r} references unknown model {p.model!r}")
        if self.review_policy.reviewer_family_must_differ:
            families = {self.models[p.model].family for p in self.peers}
            if len(families) < 2:
                raise ValueError(
                    "review policy needs a reviewer from a different family: "
                    "peers must use at least 2 distinct model families"
                )
        return self

    def model_for(self, peer_id: str) -> ModelSpec:
        for p in self.peers:
            if p.id == peer_id:
                return self.models[p.model]
        raise KeyError(peer_id)


def load_roster(path: str | Path) -> RosterConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text())
        return RosterConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(str(e)) from e
