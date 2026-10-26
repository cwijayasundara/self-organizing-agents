from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArmOutcome:
    arm: str
    variant: int
    seed: int
    status: str  # "finished" | "done" | "budget" | "timeout" | "stalled"
    final_text: str
    spend_usd: float
    elapsed_s: float
    notes: dict
