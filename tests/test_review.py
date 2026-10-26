import pytest

from agora.ledger import open_ledger
from agora.ledger.types import ClaimRejected, LedgerError
from agora.validators import mentions_acceptance, non_empty
from conftest import claimed_with_artifact, spec


def _submitted(ledger, task="A"):
    art = claimed_with_artifact(ledger, task, "P01", "deepseek")
    return ledger.tasks.submit_for_review(task, "P01", art.id)


def _review_notes(ledger):
    return [n for n in ledger.board.recent() if n.type == "REVIEW"]


def test_same_family_cannot_review(ledger):
    r = _submitted(ledger)
    assert r.id == "review:A:1" and r.kind == "review" and r.required is False
    assert r.review_of == "A" and r.author_family == "deepseek" and r.status == "open"
    assert ledger.tasks.get("A").status == "in_review"
    with pytest.raises(ClaimRejected, match="same family"):
        ledger.tasks.claim(r.id, "P02", "deepseek")
    ledger.tasks.claim(r.id, "P03", "anthropic")


def test_author_cannot_review_own_work(ledger):
    r = _submitted(ledger)
    # author in a different family label still counts as own work
    with pytest.raises(ClaimRejected, match="own work"):
        ledger.tasks.claim(r.id, "P01", "anthropic")


def test_family_rule_can_be_disabled(tmp_path, clock):
    lg = open_ledger(str(tmp_path / "d.sqlite"), clock=clock, reviewer_family_must_differ=False)
    r = _submitted(lg)
    lg.tasks.claim(r.id, "P02", "deepseek")
    lg.db.close()


def test_claimable_excludes_same_family_review(ledger):
    r = _submitted(ledger)
    assert r.id not in [t.id for t in ledger.tasks.claimable("P02", "deepseek")]
    assert r.id not in [t.id for t in ledger.tasks.claimable("P01", "anthropic")]
    assert r.id in [t.id for t in ledger.tasks.claimable("P03", "anthropic")]


def test_approve_marks_done(ledger):
    r = _submitted(ledger)
    ledger.tasks.claim(r.id, "P03", "anthropic")
    work = ledger.tasks.record_verdict(r.id, "P03", True, "solid")
    assert work.id == "A" and work.status == "done"
    assert ledger.tasks.get(r.id).status == "done"
    notes = _review_notes(ledger)
    assert len(notes) == 1 and notes[0].text.startswith("APPROVE A")


def test_reject_returns_to_author(ledger, clock):
    r = _submitted(ledger)
    ledger.tasks.claim(r.id, "P03", "anthropic")
    clock.advance(500)
    work = ledger.tasks.record_verdict(r.id, "P03", False, "needs more detail")
    assert work.status == "claimed" and work.owner == "P01"
    assert work.lease_until == clock() + ledger.tasks.lease_s
    assert ledger.tasks.get(r.id).status == "done"
    assert _review_notes(ledger)[0].text.startswith("REJECT A")


def test_resubmission_after_rejection_creates_second_review(ledger):
    r = _submitted(ledger)
    ledger.tasks.claim(r.id, "P03", "anthropic")
    ledger.tasks.record_verdict(r.id, "P03", False, "no")
    art = ledger.artifacts.commit("A", "P01", "z" * 300)
    r2 = ledger.tasks.submit_for_review("A", "P01", art.id)
    assert r2.id == "review:A:2"


def test_validator_failure_overrides_approval(tmp_path, clock):
    lg = open_ledger(str(tmp_path / "v.sqlite"), clock=clock, validators=[non_empty(min_chars=500)])
    lg.tasks.create_task(spec("A"))
    lg.tasks.claim("A", "P01", "deepseek")
    art = lg.artifacts.commit("A", "P01", "x" * 50)
    r = lg.tasks.submit_for_review("A", "P01", art.id)
    lg.tasks.claim(r.id, "P03", "anthropic")
    work = lg.tasks.record_verdict(r.id, "P03", True, "fine")
    assert work.status == "claimed" and work.owner == "P01"
    notes = [n for n in lg.board.recent() if n.type == "REVIEW"]
    assert "non_empty" in notes[0].text and notes[0].text.startswith("REJECT A")
    lg.db.close()


def test_note_truncated_to_300(ledger):
    r = _submitted(ledger)
    ledger.tasks.claim(r.id, "P03", "anthropic")
    ledger.tasks.record_verdict(r.id, "P03", True, "r" * 1000)
    assert len(_review_notes(ledger)[0].text) == 300


def test_only_review_claimer_records_verdict(ledger):
    r = _submitted(ledger)
    with pytest.raises(LedgerError, match="not owner"):
        ledger.tasks.record_verdict(r.id, "P03", True, "unclaimed")
    ledger.tasks.claim(r.id, "P03", "anthropic")
    with pytest.raises(LedgerError, match="not owner"):
        ledger.tasks.record_verdict(r.id, "P04", True, "imposter")


def test_non_owner_cannot_commit(ledger):
    claimed_with_artifact(ledger, "A", "P01", "deepseek")
    with pytest.raises(LedgerError, match="not owner"):
        ledger.artifacts.commit("A", "P02", "content")


def test_empty_artifact_rejected(ledger):
    ledger.tasks.create_task(spec("A"))
    ledger.tasks.claim("A", "P01", "deepseek")
    with pytest.raises(LedgerError):
        ledger.artifacts.commit("A", "P01", "   ")


def test_versions_increment_and_latest(ledger):
    ledger.tasks.create_task(spec("A"))
    assert ledger.artifacts.latest("A") is None
    ledger.tasks.claim("A", "P01", "deepseek")
    a1 = ledger.artifacts.commit("A", "P01", "one")
    a2 = ledger.artifacts.commit("A", "P01", "two")
    assert (a1.id, a2.id) == ("A@v1", "A@v2")
    assert ledger.artifacts.latest("A").id == "A@v2"
    assert ledger.artifacts.get("A@v1").content == "one"
    with pytest.raises(LedgerError):
        ledger.artifacts.get("A@v9")


def test_submit_requires_owner_and_own_artifact(ledger):
    art = claimed_with_artifact(ledger, "A", "P01", "deepseek")
    with pytest.raises(LedgerError, match="not owner"):
        ledger.tasks.submit_for_review("A", "P02", art.id)
    with pytest.raises(LedgerError):
        ledger.tasks.submit_for_review("A", "P01", "B@v1")


def test_builtin_validators():
    from agora.ledger.types import Artifact
    t = spec("A")
    task = type("T", (), {})()
    task.acceptance = ["Pricing model covered", "Lists risks"]
    art = Artifact("A@v1", "A", "P01", 1, "The PRICING model covered here", 0.0)
    assert mentions_acceptance()(task, art) == [
        "mentions_acceptance: missing acceptance criterion 'Lists risks'"
    ]
    assert non_empty(10)(task, art) == []
    assert non_empty(100)(task, art)[0].startswith("non_empty:")
    assert t.id == "A"
