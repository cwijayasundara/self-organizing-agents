"""Agent-to-agent messages with exactly-once delivery per recipient."""
from __future__ import annotations

from typing import Callable

from agora.ledger.db import Database
from agora.ledger.types import LedgerError, Message

MAX_TEXT = 1000


class Mailbox:
    def __init__(self, db: Database, clock: Callable[[], float]):
        self.db = db
        self.clock = clock
        self._audience: set[str] = set()

    def register(self, agent_ids: list[str]) -> None:
        """Set the broadcast audience (replaces any previous audience)."""
        self._audience = set(agent_ids)

    def send(self, sender: str, recipient: str | None, text: str, urgent: bool) -> Message:
        if not text or not text.strip():
            raise LedgerError("message text must not be empty")
        if len(text) > MAX_TEXT:
            raise LedgerError(f"message text is {len(text)} chars; the limit is {MAX_TEXT}")
        now = self.clock()
        with self.db.write() as conn:
            cur = conn.execute(
                "INSERT INTO messages(sender, recipient, text, urgent, created_at) VALUES (?,?,?,?,?)",
                (sender, recipient, text, int(urgent), now),
            )
            mid = cur.lastrowid
        return Message(mid, sender, recipient, text, urgent, now)

    def take(self, agent_id: str, urgent_only: bool) -> list[Message]:
        """Return and mark delivered this agent's pending messages, oldest first."""
        broadcast_ok = agent_id in self._audience
        sql = (
            "SELECT m.* FROM messages m WHERE NOT EXISTS ("
            " SELECT 1 FROM deliveries d WHERE d.message_id=m.id AND d.recipient=?)"
            " AND (m.recipient=? OR (m.recipient IS NULL AND ? AND m.sender<>?))"
        )
        params: list = [agent_id, agent_id, int(broadcast_ok), agent_id]
        if urgent_only:
            sql += " AND m.urgent=1"
        sql += " ORDER BY m.id"
        with self.db.write() as conn:
            rows = conn.execute(sql, params).fetchall()
            conn.executemany(
                "INSERT INTO deliveries(message_id, recipient) VALUES (?,?)",
                [(r["id"], agent_id) for r in rows],
            )
        return [
            Message(r["id"], r["sender"], r["recipient"], r["text"], bool(r["urgent"]), r["created_at"])
            for r in rows
        ]
