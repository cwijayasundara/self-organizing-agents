"""Task ledger: dependency-gated, leased, atomically claimed tasks."""
from __future__ import annotations

import json
import sqlite3
from typing import Callable, Sequence

from agora.ledger.artifacts import artifact_from_row
from agora.ledger.board import Board
from agora.ledger.db import Database
from agora.ledger.types import ClaimRejected, LedgerError, Task, TaskSpec, TaskStatus
from agora.validators import Validator

# A task is blocked while any dependency is not done.
_DEPS_DONE = (
    "NOT EXISTS (SELECT 1 FROM task_deps d JOIN tasks t ON t.id=d.dep_id "
    "WHERE d.task_id=tasks.id AND t.status<>'done')"
)


def _title_key(title: str) -> str:
    return " ".join(title.lower().split())


class TaskLedger:
    def __init__(
        self, db: Database, board: Board, clock: Callable[[], float], lease_s: int,
        validators: Sequence[Validator] = (),
        reviewer_family_must_differ: bool = True,
    ):
        self.validators = tuple(validators)
        self.reviewer_family_must_differ = reviewer_family_must_differ
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
        if self.held_by(agent_id):
            return []
        rows = self.db.read(f"SELECT * FROM tasks WHERE status='open' AND {_DEPS_DONE} ORDER BY rowid")
        return [t for t in self._from_rows(rows) if self._review_claim_rejection(t, agent_id, family) is None]

    # ---- extension point for Task 8 ---------------------------------------
    def _review_claim_rejection(self, task: Task, agent_id: str, family: str) -> str | None:
        """Review-task rules ("own work", "same family as author"); None means allowed.

        Shared by claim() and claimable().
        """
        if task.kind != "review":
            return None
        author = None
        if task.review_of is not None:
            rows = self.db.read("SELECT owner FROM tasks WHERE id=?", (task.review_of,))
            author = rows[0]["owner"] if rows else None
        if author is not None and agent_id == author:
            return "own work"
        if self.reviewer_family_must_differ and family == task.author_family:
            return "same family as author"
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
        try:
            self.board.write_note("ledger", "OBSERVED", f"RELEASED {task_id} by {agent_id}: {reason}"[:100],
                                  task_id=task_id)
        except LedgerError:
            pass  # best-effort: the release is already committed
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
            try:
                self.board.write_note("ledger", "OBSERVED", f"LEASE_EXPIRED {task_id} owner={owner}",
                                      task_id=task_id)
            except LedgerError:
                pass  # best-effort: the expiry is already committed
        return [t for t, _ in expired]

    # ---- review gate -------------------------------------------------------
    def submit_for_review(self, task_id: str, agent_id: str, artifact_id: str) -> Task:
        """Move the work task to in_review and return the newly created review task."""
        work = self._require_owner(task_id, agent_id)
        with self.db.write() as c:
            if not c.execute("SELECT 1 FROM artifacts WHERE id=? AND task_id=?",
                             (artifact_id, task_id)).fetchone():
                raise LedgerError(f"artifact {artifact_id} does not belong to task {task_id}")
            n = c.execute("SELECT COUNT(*)+1 AS n FROM tasks WHERE review_of=?", (task_id,)).fetchone()["n"]
            review_id = f"review:{task_id}:{n}"
            self._insert(c, TaskSpec(
                id=review_id, title=f"Review {task_id}" + (f" (round {n})" if n > 1 else ""),
                objective=f"Review the submitted artifact for work task {task_id} ({work.title}) "
                          "against its acceptance criteria; approve or reject with reasons.",
                output_format="Verdict: approve or reject, with reasons.",
                acceptance=list(work.acceptance), deps=[], required=False, kind="review",
            ))
            c.execute("UPDATE tasks SET review_of=?, author_family=?, artifact_id=? WHERE id=?",
                      (task_id, work.owner_family, artifact_id, review_id))
            c.execute("UPDATE tasks SET status='in_review', artifact_id=?, version=version+1 WHERE id=?",
                      (artifact_id, task_id))
        return self.get(review_id)

    def record_verdict(self, review_task_id: str, reviewer_id: str, approve: bool, reasons: str) -> Task:
        review = self._require_owner(review_task_id, reviewer_id)
        if review.kind != "review" or review.review_of is None:
            raise LedgerError(f"{review_task_id} is not a review task")
        work = self.get(review.review_of)
        rows = self.db.read("SELECT * FROM artifacts WHERE id=?", (review.artifact_id,))
        if not rows:
            raise LedgerError("review task has no artifact")
        artifact = artifact_from_row(rows[0])
        errors = [e for v in self.validators for e in v(work, artifact)]
        passed = approve and not errors
        with self.db.write() as c:
            cur = c.execute(
                "UPDATE tasks SET status='done', version=version+1 "
                "WHERE id=? AND owner=? AND status='claimed'", (review_task_id, reviewer_id))
            if cur.rowcount == 0:
                raise LedgerError("not owner")
            if passed:
                c.execute("UPDATE tasks SET status='done', version=version+1 WHERE id=?", (work.id,))
            else:
                c.execute("UPDATE tasks SET status='claimed', lease_until=?, version=version+1 WHERE id=?",
                          (self.clock() + self.lease_s, work.id))
        detail = reasons if not errors else "; ".join(errors) + ((" | " + reasons) if reasons else "")
        text = f"{'APPROVE' if passed else 'REJECT'} {work.id}: {detail}"[:300]
        self.board.write_note(reviewer_id, "REVIEW", text, task_id=work.id)
        return self.get(work.id)
