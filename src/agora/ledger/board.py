"""Typed append-only note board with evidence filtering and superseding."""
from __future__ import annotations

import sqlite3
from typing import Callable, Sequence

from agora.ledger.db import Database
from agora.ledger.grep_query import QueryError, compile_query
from agora.ledger.types import LedgerError, Note, NoteType

Admission = Callable[[str, str, str, "str | None"], list[str]]

PLACEHOLDER_EVIDENCE = frozenset(
    {"tbd", "todo", "pending", "should work", "n/a", "na", "later", "unknown", "wip", "none"}
)

_DEFAULT_CAP = 100
_CAPS = {
    "FACT": 100, "OBSERVED": 100, "FAIL": 100, "CLAIM": 100,
    "DECISION": 200,
    "PATCH_SUMMARY": 300, "REVIEW": 300, "DISSENT": 300,
}


def _row(r: sqlite3.Row) -> Note:
    return Note(
        id=r["id"], author=r["author"], type=r["type"], text=r["text"], task_id=r["task_id"],
        detail=r["detail"], created_at=r["created_at"], invalidated=bool(r["invalidated"]),
    )


def _check_evidence(text: str) -> None:
    _, sep, rest = text.partition("evidence=")
    evidence = rest.split("|", 1)[0].strip().lower() if sep else ""
    if not evidence or evidence in PLACEHOLDER_EVIDENCE:
        raise LedgerError("PATCH_SUMMARY needs real evidence: 'evidence=<source>' is missing or a placeholder")


class Board:
    def __init__(
        self,
        db: Database,
        clock: Callable[[], float],
        on_task_note: Callable[[str, str], None] | None = None,
        admission: Sequence[Admission] = (),
    ):
        self.db = db
        self.clock = clock
        self.on_task_note = on_task_note
        self.admission = tuple(admission)

    def write_note(
        self, author: str, type: NoteType, text: str, task_id: str | None = None, detail: str | None = None
    ) -> Note:
        if type not in _CAPS:
            raise LedgerError(f"unknown note type {type!r}")
        cap = _CAPS[type]
        if len(text) > cap:
            raise LedgerError(f"{type} text is {len(text)} chars; the cap is {cap}")
        if type == "PATCH_SUMMARY":
            _check_evidence(text)
        errors = [e for check in self.admission for e in check(author, type, text, detail)]
        if errors:
            raise LedgerError("admission: " + "; ".join(errors))
        with self.db.write() as c:
            if task_id is not None and type in ("PATCH_SUMMARY", "FAIL"):
                c.execute(
                    "UPDATE notes SET invalidated=1 WHERE author=? AND task_id=? "
                    "AND type='PATCH_SUMMARY' AND invalidated=0",
                    (author, task_id),
                )
            cur = c.execute(
                "INSERT INTO notes (author, type, text, task_id, detail, created_at) VALUES (?,?,?,?,?,?)",
                (author, type, text, task_id, detail, self.clock()),
            )
            row = c.execute("SELECT * FROM notes WHERE id=?", (cur.lastrowid,)).fetchone()
        note = _row(row)
        if task_id is not None and self.on_task_note is not None:
            self.on_task_note(task_id, author)
        return note

    def recent(self, limit: int = 2000, since_id: int = 0) -> list[Note]:
        rows = self.db.read(
            "SELECT * FROM notes WHERE id>? AND invalidated=0 ORDER BY id DESC LIMIT ?", (since_id, limit)
        )
        return [_row(r) for r in reversed(rows)]

    def delta(self, agent_id: str, limit: int = 60) -> list[Note]:
        with self.db.write() as c:
            cur = c.execute("SELECT last_note_id FROM cursors WHERE agent_id=?", (agent_id,)).fetchone()
            cursor = cur["last_note_id"] if cur else 0
            rows = c.execute(
                "SELECT * FROM notes WHERE id>? AND author!=? AND invalidated=0 ORDER BY id DESC LIMIT ?",
                (cursor, agent_id, limit),
            ).fetchall()
            top = c.execute("SELECT COALESCE(MAX(id), 0) AS m FROM notes").fetchone()["m"]
            c.execute(
                "INSERT INTO cursors (agent_id, last_note_id) VALUES (?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET last_note_id=excluded.last_note_id",
                (agent_id, top),
            )
        return [_row(r) for r in reversed(rows)]

    def grep(self, query: str) -> list[Note]:
        try:
            match = compile_query(query)
        except QueryError as e:
            raise LedgerError(f"bad grep query: {e}") from e
        rows = self.db.read("SELECT * FROM notes ORDER BY id")
        return [_row(r) for r in rows if match(r["text"]) or (r["detail"] is not None and match(r["detail"]))]

    def unfold(self, note_id: int) -> Note:
        rows = self.db.read("SELECT * FROM notes WHERE id=?", (note_id,))
        if not rows:
            raise LedgerError(f"note {note_id} not found")
        return _row(rows[0])

    def last_note_id(self, author: str) -> int:
        return self.db.read("SELECT COALESCE(MAX(id), 0) AS m FROM notes WHERE author=?", (author,))[0]["m"]
