"""Evaluation configuration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArmBudget:
    usd: float
    wall_clock_s: float
    episode_recursion_limit: int = 100  # same per-episode step limit as the swarm (BudgetSpec)
