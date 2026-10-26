import pytest

from agora.ledger.db import Database

INSERT = "INSERT INTO messages(sender,recipient,text,urgent,created_at) VALUES('a',NULL,'t',0,0)"


def test_write_rolls_back_on_error(tmp_path):
    db = Database(str(tmp_path / "x.sqlite"))
    with pytest.raises(RuntimeError):
        with db.write() as c:
            c.execute(INSERT)
            raise RuntimeError
    assert db.read("SELECT COUNT(*) n FROM messages")[0]["n"] == 0


def test_write_commits(tmp_path):
    db = Database(str(tmp_path / "x.sqlite"))
    with db.write() as c:
        c.execute(INSERT)
    assert db.read("SELECT COUNT(*) n FROM messages")[0]["n"] == 1
    db.close()


def test_pragmas_and_tables(tmp_path):
    db = Database(str(tmp_path / "x.sqlite"))
    assert db.read("PRAGMA journal_mode")[0][0] == "wal"
    assert db.read("PRAGMA foreign_keys")[0][0] == 1
    names = {r["name"] for r in db.read("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"notes", "tasks", "task_deps", "artifacts", "messages",
            "deliveries", "cursors", "spend"} <= names
    cols = {r["name"] for r in db.read("PRAGMA table_info(tasks)")}
    assert "title_key" in cols
    assert "invalidated" in {r["name"] for r in db.read("PRAGMA table_info(notes)")}
    db.close()


def test_reopen_is_idempotent(tmp_path):
    p = str(tmp_path / "x.sqlite")
    Database(p).close()
    Database(p).close()


def test_ledger_fixture(ledger, clock):
    assert ledger.db is not None
    clock.advance(5)
    assert ledger.clock() == 1005.0
