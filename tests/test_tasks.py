from concurrent.futures import ThreadPoolExecutor

import pytest

from agora.ledger.types import ClaimRejected, LedgerError
from conftest import spec


def test_claim_respects_deps(ledger):
    ledger.tasks.create_task(spec("A")); ledger.tasks.create_task(spec("B", deps=["A"]))
    with pytest.raises(ClaimRejected, match=r"deps not done: A \[open\]"):
        ledger.tasks.claim("B", "P01", "deepseek")
    assert [t.id for t in ledger.tasks.claimable("P01", "deepseek")] == ["A"]


def test_concurrent_claims_single_winner(ledger):
    ledger.tasks.create_task(spec("A"))

    def attempt(i):
        try:
            ledger.tasks.claim("A", f"P{i:02}", f"fam{i}")
            return True
        except ClaimRejected:
            return False

    with ThreadPoolExecutor(20) as ex:
        results = list(ex.map(attempt, range(20)))
    assert results.count(True) == 1


def test_lease_expiry_reopens_and_notes(ledger, clock):
    ledger.tasks.create_task(spec("A")); ledger.tasks.claim("A", "P01", "deepseek")
    clock.advance(1201)
    assert ledger.tasks.sweep_expired() == ["A"]
    t = ledger.tasks.get("A")
    assert (t.status, t.owner, t.lease_until) == ("open", None, None)
    note = ledger.board.grep("LEASE_EXPIRED")[0]
    assert (note.task_id, note.author, note.type, note.text) == ("A", "ledger", "OBSERVED", "LEASE_EXPIRED A owner=P01")


def test_board_note_renews_lease(ledger, clock):
    ledger.tasks.create_task(spec("A")); ledger.tasks.claim("A", "P01", "deepseek")
    clock.advance(1000); ledger.board.write_note("P01", "CLAIM", "testing Germany-first", task_id="A")
    clock.advance(1000)
    assert ledger.tasks.sweep_expired() == []


def test_notes_by_others_or_ledger_do_not_renew(ledger, clock):
    ledger.tasks.create_task(spec("A")); ledger.tasks.claim("A", "P01", "deepseek")
    clock.advance(1000)
    ledger.board.write_note("P02", "FACT", "x", task_id="A")
    ledger.board.write_note("ledger", "OBSERVED", "y", task_id="A")
    clock.advance(201)
    assert ledger.tasks.sweep_expired() == ["A"]


def test_note_on_unclaimed_task_is_silent(ledger):
    ledger.tasks.create_task(spec("A"))
    ledger.board.write_note("P01", "FACT", "x", task_id="A")
    ledger.board.write_note("P01", "FACT", "x", task_id="nope")
    assert ledger.tasks.get("A").lease_until is None


def test_non_owner_cannot_release(ledger):
    ledger.tasks.create_task(spec("A")); ledger.tasks.claim("A", "P01", "deepseek")
    with pytest.raises(LedgerError, match="not owner"):
        ledger.tasks.release("A", "P02", "SYSTEM: release")
    assert ledger.tasks.get("A").owner == "P01"


def test_one_claim_per_agent(ledger):
    ledger.tasks.create_task(spec("A")); ledger.tasks.create_task(spec("B"))
    ledger.tasks.claim("A", "P01", "deepseek")
    with pytest.raises(ClaimRejected, match="already holding"):
        ledger.tasks.claim("B", "P01", "deepseek")
    ledger.tasks.release("A", "P01", "done with it")
    ledger.tasks.claim("B", "P01", "deepseek")


def test_reserve_dedupes_normalized_title(ledger):
    t1, created1 = ledger.tasks.reserve(spec("sub:P01:1", title="Covenant  headroom"))
    t2, created2 = ledger.tasks.reserve(spec("sub:P02:1", title="covenant headroom"))
    assert (created1, created2, t2.id) == (True, False, "sub:P01:1")


def test_reserve_creates_again_when_existing_is_done(ledger):
    t1, _ = ledger.tasks.reserve(spec("a", title="Same"))
    with ledger.db.write() as c:
        c.execute("UPDATE tasks SET status='done' WHERE id='a'")
    t2, created = ledger.tasks.reserve(spec("b", title="same"))
    assert (created, t2.id) == (True, "b")


def test_claim_rejection_reasons(ledger):
    with pytest.raises(ClaimRejected, match="^unknown task$"):
        ledger.tasks.claim("nope", "P01", "f")
    ledger.tasks.create_task(spec("A"))
    ledger.tasks.claim("A", "P01", "f")
    with pytest.raises(ClaimRejected, match="^not open: claimed by P01$"):
        ledger.tasks.claim("A", "P02", "g")


def test_claim_sets_fields_and_lease(ledger, clock):
    ledger.tasks.create_task(spec("A"))
    t = ledger.tasks.claim("A", "P01", "deepseek")
    assert (t.status, t.owner, t.owner_family, t.lease_until, t.version) == (
        "claimed", "P01", "deepseek", clock() + 1200, 1)
    assert [x.id for x in ledger.tasks.held_by("P01")] == ["A"]
    assert ledger.tasks.held_by("P02") == []
    assert ledger.tasks.claimable("P02", "g") == []


def test_claim_succeeds_once_deps_done(ledger):
    ledger.tasks.create_task(spec("A")); ledger.tasks.create_task(spec("B", deps=["A"]))
    with ledger.db.write() as c:
        c.execute("UPDATE tasks SET status='done' WHERE id='A'")
    assert ledger.tasks.claim("B", "P01", "f").status == "claimed"


def test_release_reopens_and_notes_reason(ledger):
    ledger.tasks.create_task(spec("A")); ledger.tasks.claim("A", "P01", "f")
    t = ledger.tasks.release("A", "P01", "blocked-on-data")
    assert (t.status, t.owner, t.owner_family, t.lease_until) == ("open", None, None, None)
    assert ledger.board.grep("blocked-on-data")[0].task_id == "A"


def test_renew_extends_lease_and_requires_owner(ledger, clock):
    ledger.tasks.create_task(spec("A")); ledger.tasks.claim("A", "P01", "f")
    clock.advance(500)
    assert ledger.tasks.renew("A", "P01").lease_until == clock() + 1200
    with pytest.raises(LedgerError, match="not owner"):
        ledger.tasks.renew("A", "P02")


def test_get_and_list(ledger):
    ledger.tasks.create_task(spec("A", deps=[])); ledger.tasks.create_task(spec("B", deps=["A"]))
    ledger.tasks.claim("A", "P01", "f")
    assert ledger.tasks.get("B").deps == ["A"]
    assert ledger.tasks.get("A").acceptance == ["criterion one", "criterion two", "criterion three"]
    assert [t.id for t in ledger.tasks.list()] == ["A", "B"]
    assert [t.id for t in ledger.tasks.list("open")] == ["B"]
    with pytest.raises(LedgerError, match="unknown task"):
        ledger.tasks.get("zzz")


def test_create_task_errors(ledger):
    ledger.tasks.create_task(spec("A"))
    with pytest.raises(LedgerError, match="duplicate"):
        ledger.tasks.create_task(spec("A"))
    with pytest.raises(LedgerError, match="unknown dep"):
        ledger.tasks.create_task(spec("B", deps=["missing"]))
    assert [t.id for t in ledger.tasks.list()] == ["A"]


def test_claimable_empty_when_agent_holds_task(ledger):
    ledger.tasks.create_task(spec("A")); ledger.tasks.create_task(spec("B"))
    ledger.tasks.claim("A", "P01", "deepseek")
    assert ledger.tasks.claimable("P01", "deepseek") == []
    assert [t.id for t in ledger.tasks.claimable("P02", "deepseek")] == ["B"]


def test_same_agent_concurrent_claims_single_winner(ledger):
    for i in range(10):
        ledger.tasks.create_task(spec(f"T{i}"))

    def attempt(i):
        try:
            ledger.tasks.claim(f"T{i % 10}", "P01", "deepseek")
            return True
        except ClaimRejected:
            return False

    with ThreadPoolExecutor(20) as ex:
        results = list(ex.map(attempt, range(20)))
    assert results.count(True) == 1
    assert len(ledger.tasks.held_by("P01")) == 1
