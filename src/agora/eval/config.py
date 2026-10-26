"""Evaluation configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agora.config import ConfigError, ModelSpec


@dataclass(frozen=True)
class ArmBudget:
    usd: float
    wall_clock_s: float
    episode_recursion_limit: int = 100  # same per-episode step limit as the swarm (BudgetSpec)


TEAM_KEYS = {"deepseek", "glm"}


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_root: str
    gold_root: str
    out_dir: str
    brief_path: str
    template_path: str
    budget_usd: float = Field(gt=0)
    wall_clock_s: int = Field(gt=0)
    episode_recursion_limit: int = 100
    team_models: dict[str, ModelSpec]
    judges: dict[str, ModelSpec]
    arms: list[str]
    variants: list[int]
    seeds: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def _fill_keys(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for field in ("team_models", "judges"):
                if isinstance(data.get(field), dict):
                    data[field] = {k: ({**v, "key": k} if isinstance(v, dict) else v)
                                   for k, v in data[field].items()}
        return data

    @model_validator(mode="after")
    def _check(self) -> "EvalConfig":
        from agora.eval.arms import ARM_IDS
        if set(self.team_models) != TEAM_KEYS:
            raise ValueError(f"team_models keys must be exactly {sorted(TEAM_KEYS)}, got {sorted(self.team_models)}")
        if not self.judges:
            raise ValueError("judges must not be empty")
        team_ids = {s.id for s in self.team_models.values()}
        for k, s in self.judges.items():
            if k in self.team_models:
                raise ValueError(f"judge key {k!r} must not equal a team model key")
            if s.id in team_ids:
                raise ValueError(f"judge {k!r} uses a team model id {s.id!r}")
        if not self.arms:
            raise ValueError("arms must not be empty")
        for a in self.arms:
            if a not in ARM_IDS:
                raise ValueError(f"unknown arm {a!r}; expected one of {list(ARM_IDS)}")
        if len(set(self.arms)) != len(self.arms):
            raise ValueError("duplicate arms")
        if not self.variants:
            raise ValueError("variants must not be empty")
        return self


def load_eval_config(path: str | Path) -> EvalConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text())
        return EvalConfig.model_validate(raw)
    except (ValidationError, yaml.YAMLError, OSError) as e:
        raise ConfigError(" ".join(str(e).split())) from e
