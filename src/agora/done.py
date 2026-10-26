"""Definition of done, computed from the ledger."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DoneStatus:
    done: bool
    missing: list[str]


def evaluate_done(ledger) -> DoneStatus:
    """Done when every required work/integration task is done.

    An empty ledger (nothing required) is never done.
    """
    required = [t for t in ledger.tasks.list() if t.required and t.kind in ("work", "integration")]
    missing = sorted(t.id for t in required if t.status != "done")
    return DoneStatus(done=bool(required) and not missing, missing=missing)
