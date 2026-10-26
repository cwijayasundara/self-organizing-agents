"""Task ledger: dependency-gated, leased, atomically claimed tasks."""
from __future__ import annotations

import json
import sqlite3
from typing import Callable

from agora.ledger.board import Board
from agora.ledger.db import Database
from agora.ledger.types import ClaimRejected, LedgerError, Task, TaskSpec, TaskStatus

# A task is blocked while any dependency is not done.
_DEPS_DONE = (
    "NOT EXISTS (SELECT 1 FROM task_deps d JOIN tasks t ON t.id=d.dep_id "
    "WHERE d.task_id=tasks.id AND t.status<>'done')"
)


def _title_key(title: str) -> str:
    return " ".join(title.lower().split())


class TaskLedger:
    def __init__(self, db: Database, board: Board, clock: Callable[[], float], lease_s: int):
        self.db = db
        self.board = board
        self.clock = clock
        self.lease_s = lease_s

    # ---- reads -------------------------------------------------------------
    def _task(self, r: sqlite3.Row, deps: list[str]) -> Task:
        return Task(
            id=r["id"], title=r["title"], objective=r["objective"], output_format=r["output_format"],
            acceptance=json.loads(r["acceptance"]), deps=deps, required=bool(r["required"]),
            kind=r["kind"], status=r["status"], owner=r["owner"], owner_family=r["owner_family"],
            lease_until=r["lease_until"], review_of=r["review_of"], author_family=r["author_family"],
            artifact_id=r["artifact_id"], version=r["version"],
        )

    def _from_rows(self, rows: list[sqlite3.Row]) -> list[Task]:
        deps: dict[str, list[str]] = {}
        for d in self.db.read("SELECT task_id, dep_id FROM task_deps ORDER BY rowid"):
            deps.setdefault(d["task_id"], []).append(d["dep_id"])
        return [self._task(r, deps.get(r["id"], [])) for r in rows]

    def get(self, task_id: str) -> Task:
        rows = self.db.read("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not rows:
            raise LedgerError(f"unknown task {task_id}")
        return self._from_rows(rows)[0]

    def list(self, status: TaskStatus | None = None) -> list[Task]:
        if status is None:
            rows = self.db.read("SELECT * FROM tasks ORDER BY rowid")
        else:
            rows = self.db.read("SELECT * FROM tasks WHERE status=? ORDER BY rowid", (status,))
        return self._from_rows(rows)

    def held_by(self, agent_id: str) -> list[Task]:
        rows = self.db.read(
            "SELECT * FROM tasks WHERE owner=? AND status='claimed' ORDER BY rowid", (agent_id,)
        )
        return self._from_rows(rows)

    def claimable(self, agent_id: str, family: str) -> list[Task]:
        rows = self.db.read(f"SELECT * FROM tasks WHERE status='open' AND {_DEPS_DONE} ORDER BY rowid")
        return [t for t in self._from_rows(rows) if self._review_claim_rejection(t, agent_id, family) is None]

    # ---- extension point for Task 8 ---------------------------------------
    def _review_claim_rejection(self, task: Task, agent_id: str, family: str) -> str | None:
        """Review-task rules ("same family as author", "own work"); None means allowed.

        Task 8 implements this; it is shared by claim() and claimable().
        """
        return None

    # ---- writes ------------------------------------------------------------
    def create_task(self, spec: TaskSpec) -> Task:
        with self.db.write() as c:
            self._insert(c, spec)
        return self.get(spec.id)

    def _insert(self, c: sqlite3.Connection, spec: TaskSpec) -> None:
        if c.execute("SELECT 1 FROM tasks WHERE id=?", (spec.id,)).fetchone():
            raise LedgerError(f"duplicate task id {spec.id}")
        for dep in spec.deps:
            if not c.execute("SELECT 1 FROM tasks WHERE id=?", (dep,)).fetchone():
                raise LedgerError(f"unknown dep {dep} for task {spec.id}")
        c.execute(
            "INSERT INTO tasks (id, title, title_key, objective, output_format, acceptance, required, kind) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (spec.id, spec.title, _title_key(spec.title), spec.objective, spec.output_format,
             json.dumps(spec.acceptance), int(spec.required), spec.kind),
        )
        for dep in spec.deps:
            c.execute("INSERT OR IGNORE INTO task_deps (task_id, dep_id) VALUES (?,?)", (spec.id, dep))

    def reserve(self, spec: TaskSpec) -> tuple[Task, bool]:
        with self.db.write() as c:
            row = c.execute(
                "SELECT id FROM tasks WHERE title_key=? AND status<>'done' ORDER BY rowid LIMIT 1",
                (_title_key(spec.title),),
            ).fetchone()
            if row is None:
                self._insert(c, spec)
        if row is not None:
            return self.get(row["id"]), False
        return self.get(spec.id), True

    def claim(self, task_id: str, agent_id: str, family: str) -> Task:
        existing = self.db.read("SELECT id FROM tasks WHERE id=?", (task_id,))
        if existing:
            # Task 8 hook: review-task family / own-work rules, checked before the claim.
            reason = self._review_claim_rejection(self.get(task_id), agent_id, family)
            if reason is not None:
                raise ClaimRejected(reason)
        with self.db.write() as c:
            row = c.execute(
                "UPDATE tasks SET status='claimed', owner=?, owner_family=?, lease_until=?, version=version+1 "
                f"WHERE id=? AND status='open' AND {_DEPS_DONE} "
                "AND NOT EXISTS (SELECT 1 FROM tasks WHERE owner=? AND status='claimed') RETURNING id",
                (agent_id, family, self.clock() + self.lease_s, task_id, agent_id),
            ).fetchone()
        if row is not None:
            return self.get(task_id)
        raise ClaimRejected(self._rejection_reason(task_id, agent_id))

    def _rejection_reason(self, task_id: str, agent_id: str) -> str:
        rows = self.db.read("SELECT status FROM tasks WHERE id=?", (task_id,))
        if not rows:
            return "unknown task"
        if rows[0]["status"] != "open":
            return "not open"
        if self.db.read(f"SELECT 1 FROM tasks WHERE id=? AND NOT {_DEPS_DONE}", (task_id,)):
            return "deps not done"
        return "already holding a task"

    def _require_owner(self, task_id: str, agent_id: str) -> Task:
        task = self.get(task_id)
        if task.owner != agent_id or task.status != "claimed":
            raise LedgerError("not owner")
        return task

    def renew(self, task_id: str, agent_id: str) -> Task:
        self._require_owner(task_id, agent_id)
        with self.db.write() as c:
            cur = c.execute(
                "UPDATE tasks SET lease_until=? WHERE id=? AND owner=? AND status='claimed'",
                (self.clock() + self.lease_s, task_id, agent_id),
            )
        if cur.rowcount == 0:
            raise LedgerError("not owner")
        return self.get(task_id)

    def renew_if_owner(self, task_id: str, author: str) -> None:
        """Board hook: a note by the owner renews the lease. Never raises LedgerError."""
        try:
            self.renew(task_id, author)
        except LedgerError:
            pass

    def release(self, task_id: str, agent_id: str, reason: str) -> Task:
        self._require_owner(task_id, agent_id)
        with self.db.write() as c:
            cur = c.execute(
                "UPDATE tasks SET status='open', owner=NULL, owner_family=NULL, lease_until=NULL, "
                "version=version+1 WHERE id=? AND owner=? AND status='claimed'",
                (task_id, agent_id),
            )
        if cur.rowcount == 0:
            raise LedgerError("not owner")
        self.board.write_note("ledger", "OBSERVED", f"RELEASED {task_id} by {agent_id}: {reason}"[:100],
                              task_id=task_id)
        return self.get(task_id)

    def sweep_expired(self) -> list[str]:
        expired: list[tuple[str, str]] = []
        with self.db.write() as c:
            for r in c.execute(
                "SELECT id, owner FROM tasks WHERE status='claimed' AND lease_until<? ORDER BY rowid",
                (self.clock(),),
            ).fetchall():
                c.execute(
                    "UPDATE tasks SET status='open', owner=NULL, owner_family=NULL, lease_until=NULL, "
                    "version=version+1 WHERE id=?",
                    (r["id"],),
                )
                expired.append((r["id"], r["owner"]))
        # Notes are written after the transaction: write() is not re-entrant.
        for task_id, owner in expired:
            self.board.write_note("ledger", "OBSERVED", f"LEASE_EXPIRED {task_id} owner={owner}", task_id=task_id)
        return [t for t, _ in expired]
