from __future__ import annotations

from dataclasses import dataclass


STATUSES = ("finished", "done", "budget", "timeout", "stalled")


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

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid status {self.status!r}; expected one of {STATUSES}")
