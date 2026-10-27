"""Append-only activity log (episodes, tool calls, runner actions) for logs and the live view.

Peers never read it and the runner's progress fingerprint ignores it, so it cannot change behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agora.ledger.db import Database

MAX_DETAIL = 2000


@dataclass(frozen=True)
class Event:
    id: int
    actor: str
    kind: str
    task_id: str | None
    detail: str | None
    created_at: float


class EventLog:
    def __init__(self, db: Database, clock: Callable[[], float]):
        self.db = db
        self.clock = clock

    def emit(self, actor: str, kind: str, detail: str | None = None, task_id: str | None = None) -> None:
        if detail is not None and len(detail) > MAX_DETAIL:
            detail = detail[: MAX_DETAIL - 1] + "…"
        with self.db.write() as c:
            c.execute(
                "INSERT INTO events (actor, kind, task_id, detail, created_at) VALUES (?,?,?,?,?)",
                (actor, kind, task_id, detail, self.clock()),
            )

    def since(self, event_id: int = 0, limit: int = 1000) -> list[Event]:
        rows = self.db.read("SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?", (event_id, limit))
        return [Event(r["id"], r["actor"], r["kind"], r["task_id"], r["detail"], r["created_at"]) for r in rows]
