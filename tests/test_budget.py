import pytest

from agora.config import load_roster
from agora.ledger.budget import cost_of
from agora.ledger.types import LedgerError, Usage


def test_haiku_long_prompt_tier():
    haiku = load_roster("roster.example.yaml").models["haiku"]
    assert cost_of(haiku, Usage(50_000, 0, 1_000)) == pytest.approx(0.0055)
    assert cost_of(haiku, Usage(150_000, 0, 1_000)) == pytest.approx(0.0775)


def test_cached_tokens_discounted():
    ds = load_roster("roster.example.yaml").models["deepseek"]
    assert cost_of(ds, Usage(1_000_000, 900_000, 0)) == pytest.approx(0.0354)


def test_invalid_usage_rejected():
    ds = load_roster("roster.example.yaml").models["deepseek"]
    with pytest.raises(LedgerError):
        cost_of(ds, Usage(100, 200, 0))
    with pytest.raises(LedgerError):
        cost_of(ds, Usage(-1, 0, 0))
    with pytest.raises(LedgerError):
        cost_of(ds, Usage(100, 0, -5))


def test_charge_and_spent_totals(ledger):
    a = ledger.budget.charge("P01", "haiku", Usage(50_000, 0, 1_000))
    b = ledger.budget.charge("P02", "deepseek", Usage(1_000_000, 900_000, 0))
    assert a == pytest.approx(0.0055)
    assert ledger.budget.spent("P01") == pytest.approx(a)
    assert ledger.budget.spent("P02") == pytest.approx(b)
    assert ledger.budget.spent() == pytest.approx(a + b)
    assert ledger.budget.spent("nobody") == 0.0


def test_peer_exhausted(ledger):
    assert not ledger.budget.peer_exhausted("P01", 0.01)
    ledger.budget.charge("P01", "haiku", Usage(50_000, 0, 1_000))  # 0.0055
    assert not ledger.budget.peer_exhausted("P01", 0.01)
    ledger.budget.charge("P01", "haiku", Usage(50_000, 0, 1_000))  # 0.011
    assert ledger.budget.peer_exhausted("P01", 0.01)
    assert not ledger.budget.peer_exhausted("P02", 0.01)


def test_unknown_model_key(ledger):
    with pytest.raises(LedgerError, match="nope"):
        ledger.budget.charge("P01", "nope", Usage(1, 0, 1))
