"""Run-level text the peers never read, such as the brief they were given."""
from __future__ import annotations

from agora.ledger.db import Database


class MetaStore:
    def __init__(self, db: Database):
        self.db = db

    def put(self, key: str, value: str) -> None:
        with self.db.write() as c:
            c.execute(
                "INSERT INTO run_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get(self, key: str) -> str | None:
        rows = self.db.read("SELECT value FROM run_meta WHERE key=?", (key,))
        return rows[0]["value"] if rows else None
