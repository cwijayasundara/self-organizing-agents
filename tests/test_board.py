import pytest

from agora.ledger.board import Board
from agora.ledger.types import LedgerError


def test_text_caps(ledger):
    ledger.board.write_note("P01", "FACT", "x" * 100)
    with pytest.raises(LedgerError, match="100"):
        ledger.board.write_note("P01", "FACT", "x" * 101)
    ledger.board.write_note("P01", "REVIEW", "x" * 300)
    ledger.board.write_note("P01", "DECISION", "x" * 200)
    with pytest.raises(LedgerError, match="200"):
        ledger.board.write_note("P01", "DECISION", "x" * 201)


def test_patch_summary_requires_real_evidence(ledger):
    with pytest.raises(LedgerError, match="evidence"):
        ledger.board.write_note("P01", "PATCH_SUMMARY", "artifact=a1 | idea=sizing | evidence=TBD", task_id="T1")
    with pytest.raises(LedgerError, match="evidence"):
        ledger.board.write_note("P01", "PATCH_SUMMARY", "artifact=a1 | idea=sizing", task_id="T1")
    with pytest.raises(LedgerError, match="evidence"):
        ledger.board.write_note("P01", "PATCH_SUMMARY", "artifact=a1 | evidence= | idea=x", task_id="T1")
    ledger.board.write_note("P01", "PATCH_SUMMARY", "artifact=a1 | idea=sizing | evidence=crm.csv rows 1-400", task_id="T1")


def test_newer_patch_summary_supersedes_and_fail_invalidates(ledger):
    a = ledger.board.write_note("P01", "PATCH_SUMMARY", "artifact=a1 | idea=v1 | evidence=crm.csv", task_id="T1")
    b = ledger.board.write_note("P01", "PATCH_SUMMARY", "artifact=a2 | idea=v2 | evidence=crm.csv", task_id="T1")
    assert [n.id for n in ledger.board.recent()] == [b.id]
    ledger.board.write_note("P01", "FAIL", "v2 double counts EU revenue", task_id="T1")
    assert b.id not in [n.id for n in ledger.board.recent()]
    assert {a.id, b.id} <= {n.id for n in ledger.board.grep("idea")}


def test_supersede_is_scoped_to_author_and_task(ledger):
    p = lambda who, t: ledger.board.write_note(who, "PATCH_SUMMARY", "artifact=a | evidence=data.csv", task_id=t)
    other_author, other_task = p("P02", "T1"), p("P01", "T2")
    p("P01", "T1")
    ledger.board.write_note("P01", "FAIL", "no task id fail")
    ids = [n.id for n in ledger.board.recent()]
    assert other_author.id in ids and other_task.id in ids


def test_unknown_type_rejected(ledger):
    with pytest.raises(LedgerError):
        ledger.board.write_note("P01", "TODO", "x")


def test_recent_window_and_since(ledger):
    for i in range(5):
        ledger.board.write_note("P01", "FACT", f"f{i}")
    assert [n.text for n in ledger.board.recent(limit=2)] == ["f3", "f4"]
    assert len(ledger.board.recent(since_id=ledger.board.last_note_id("P01") - 1)) == 1


def test_delta_returns_unseen_foreign_notes_once(ledger):
    ledger.board.write_note("P02", "FACT", "f1")
    ledger.board.write_note("P01", "FACT", "mine")
    assert [n.text for n in ledger.board.delta("P01")] == ["f1"]
    assert ledger.board.delta("P01") == []
    ledger.board.write_note("P02", "FAIL", "f2")
    assert [n.text for n in ledger.board.delta("P01")] == ["f2"]
    assert [n.text for n in ledger.board.delta("P03")] == ["f1", "mine", "f2"]


def test_delta_limit_keeps_newest_and_skips_the_rest(ledger):
    for i in range(5):
        ledger.board.write_note("P02", "FACT", f"f{i}")
    assert [n.text for n in ledger.board.delta("P01", limit=2)] == ["f3", "f4"]
    assert ledger.board.delta("P01") == []


def test_delta_excludes_invalidated(ledger):
    ledger.board.write_note("P02", "PATCH_SUMMARY", "artifact=a | evidence=x.csv", task_id="T1")
    ledger.board.write_note("P02", "FAIL", "broken", task_id="T1")
    assert [n.type for n in ledger.board.delta("P01")] == ["FAIL"]


def test_admission_hook_can_reject(ledger):
    no_cite = lambda author, type_, text, detail: ["no citation"] if type_ == "FACT" and not detail else []
    board = Board(ledger.db, ledger.clock, admission=[no_cite])
    with pytest.raises(LedgerError, match="admission: no citation"):
        board.write_note("P01", "FACT", "revenue 10m")
    assert board.recent() == []
    board.write_note("P01", "FACT", "revenue 10m", detail="10-K p4")
    assert board.recent()[-1].text == "revenue 10m"


def test_admission_errors_joined(ledger):
    board = Board(ledger.db, ledger.clock, admission=[lambda *a: ["e1"], lambda *a: ["e2"]])
    with pytest.raises(LedgerError, match="admission: e1; e2"):
        board.write_note("P01", "FACT", "x")


def test_grep_searches_text_and_detail(ledger):
    ledger.board.write_note("P01", "FACT", "alpha", detail="beta gamma")
    ledger.board.write_note("P01", "FACT", "delta")
    assert [n.text for n in ledger.board.grep("beta & gamma")] == ["alpha"]
    assert [n.text for n in ledger.board.grep("alpha | delta")] == ["alpha", "delta"]


def test_unfold_and_last_note_id(ledger):
    n = ledger.board.write_note("P01", "FACT", "x", detail="long detail")
    assert ledger.board.unfold(n.id) == n
    assert ledger.board.unfold(n.id).detail == "long detail"
    with pytest.raises(LedgerError):
        ledger.board.unfold(999)
    assert ledger.board.last_note_id("P01") == n.id
    assert ledger.board.last_note_id("nobody") == 0


def test_on_task_note_called_after_commit_only_with_task_id(ledger):
    seen = []
    def cb(task_id, author):
        seen.append((task_id, author, ledger.board.last_note_id(author)))
    ledger.board.on_task_note = cb
    ledger.board.write_note("P01", "FACT", "no task")
    assert seen == []
    n = ledger.board.write_note("P01", "FACT", "with task", task_id="T1")
    assert seen == [("T1", "P01", n.id)]
    with pytest.raises(LedgerError):
        ledger.board.write_note("P01", "FACT", "x" * 101, task_id="T1")
    assert len(seen) == 1
