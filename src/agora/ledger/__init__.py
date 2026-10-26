"""Shared ledger: the single source of truth every agent coordinates through."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from agora.config import ModelSpec  # typing only
from agora.ledger.artifacts import ArtifactStore
from agora.ledger.board import Admission, Board
from agora.ledger.budget import BudgetLedger
from agora.ledger.db import Database
from agora.ledger.mailbox import Mailbox
from agora.ledger.tasks import TaskLedger


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
    admission: Sequence[Admission] = (),
) -> Ledger:
    db = Database(path)
    board = Board(db, clock, on_task_note=None, admission=admission)
    tasks = TaskLedger(db, board, clock, lease_s, validators, reviewer_family_must_differ)
    board.on_task_note = tasks.renew_if_owner
    artifacts = ArtifactStore(db, tasks, clock)
    return Ledger(
        db=db, clock=clock, board=board, tasks=tasks, artifacts=artifacts,
        mail=Mailbox(db, clock), budget=BudgetLedger(db, prices or {}, clock),
    )
