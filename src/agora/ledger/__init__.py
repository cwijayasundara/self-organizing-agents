"""Shared ledger: the single source of truth every agent coordinates through."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from agora.config import ModelSpec  # typing only
from agora.ledger.db import Database


@dataclass
class Ledger:
    db: Database
    clock: Callable[[], float]
    board: Any = None
    tasks: Any = None
    artifacts: Any = None
    mail: Any = None
    budget: Any = None


def open_ledger(
    path: str,
    clock: Callable[[], float] = time.time,
    lease_s: int = 1200,
    validators=(),
    prices: dict[str, ModelSpec] | None = None,
    reviewer_family_must_differ: bool = True,
) -> Ledger:
    # Tasks 6-9 wire in board/tasks/artifacts/mail/budget and use the extra parameters.
    return Ledger(db=Database(path), clock=clock)
