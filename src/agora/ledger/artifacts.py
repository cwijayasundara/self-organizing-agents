"""Versioned work products attached to tasks."""
from __future__ import annotations

import sqlite3
from typing import Callable

from agora.ledger.db import Database
from agora.ledger.types import Artifact, LedgerError


def artifact_from_row(r: sqlite3.Row) -> Artifact:
    return Artifact(id=r["id"], task_id=r["task_id"], author=r["author"], version=r["version"],
                    content=r["content"], created_at=r["created_at"])


class ArtifactStore:
    def __init__(self, db: Database, tasks, clock: Callable[[], float]):
        self.db = db
        self.tasks = tasks
        self.clock = clock

    def commit(self, task_id: str, agent_id: str, content: str) -> Artifact:
        if not content.strip():
            raise LedgerError("empty artifact")
        self.tasks._require_owner(task_id, agent_id)
        with self.db.write() as c:
            # Re-check inside the transaction: a release/reclaim may have landed since the check above.
            row = c.execute("SELECT owner, status, kind FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise LedgerError(f"unknown task {task_id}")
            if row["kind"] == "review":
                raise LedgerError("review tasks take a verdict, not an artifact; use review_verdict")
            if row["owner"] != agent_id or row["status"] != "claimed":
                raise LedgerError("not owner")
            n = c.execute("SELECT COALESCE(MAX(version),0)+1 AS n FROM artifacts WHERE task_id=?",
                          (task_id,)).fetchone()["n"]
            art_id = f"{task_id}@v{n}"
            c.execute("INSERT INTO artifacts (id, task_id, author, version, content, created_at) "
                      "VALUES (?,?,?,?,?,?)", (art_id, task_id, agent_id, n, content, self.clock()))
        return self.get(art_id)

    def latest(self, task_id: str, author: str | None = None) -> Artifact | None:
        if author is None:
            rows = self.db.read("SELECT * FROM artifacts WHERE task_id=? ORDER BY version DESC LIMIT 1",
                                (task_id,))
        else:
            rows = self.db.read(
                "SELECT * FROM artifacts WHERE task_id=? AND author=? ORDER BY version DESC LIMIT 1",
                (task_id, author))
        return artifact_from_row(rows[0]) if rows else None

    def get(self, artifact_id: str) -> Artifact:
        rows = self.db.read("SELECT * FROM artifacts WHERE id=?", (artifact_id,))
        if not rows:
            raise LedgerError(f"unknown artifact {artifact_id}")
        return artifact_from_row(rows[0])
