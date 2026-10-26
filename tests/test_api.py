import os

import pytest

from agora.api import SwarmOutcome, run_swarm
from agora.config import ConfigError, load_roster
from agora.ledger.types import LedgerError, TaskSpec
from fakes import ScriptedChatModel


def _roster(wall=0.5):
    r = load_roster("roster.example.yaml")
    peers = [p for p in r.peers if p.id in ("P01", "P03")]  # deepseek + haiku: two families
    return r.model_copy(update={
        "peers": peers,
        "budget": r.budget.model_copy(update={"wall_clock_s": wall}),
    })


def _specs():
    return [TaskSpec(
        id="summary", title="Summary", objective="Summarise the brief.",
        output_format="markdown", acceptance=["one", "two", "three"], deps=(), kind="integration",
    )]


def test_run_swarm_offline_uses_injected_models(tmp_path):
    db = str(tmp_path / "r.sqlite")
    models = {"deepseek": ScriptedChatModel(), "haiku": ScriptedChatModel()}
    outcome = run_swarm(_roster(), _specs(), "Brief.", db, models=models,
                        runner_kwargs={"grace_s": 0.1})
    assert isinstance(outcome, SwarmOutcome)
    assert outcome.result.status == "timeout"
    assert outcome.db_path == db and os.path.exists(db)


def test_admission_is_applied(tmp_path):
    def no_facts(author, type, text, detail):
        return ["no facts allowed"] if type == "FACT" else []

    models = {"deepseek": ScriptedChatModel(), "haiku": ScriptedChatModel()}
    outcome = run_swarm(_roster(), _specs(), "Brief.", str(tmp_path / "r.sqlite"), models=models,
                        admission=[no_facts], runner_kwargs={"grace_s": 0.1})
    with pytest.raises(LedgerError, match="admission"):
        outcome.ledger.board.write_note("P01", "FACT", "x")


def test_unused_model_not_built(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    built = []
    import agora.api as api
    monkeypatch.setattr(api, "build_model", lambda spec: built.append(spec.key) or ScriptedChatModel())
    run_swarm(_roster(), _specs(), "Brief.", str(tmp_path / "r.sqlite"),
              runner_kwargs={"grace_s": 0.1})
    assert sorted(built) == ["deepseek", "haiku"]  # minimax, luna, glm are never built


def test_missing_injected_model_raises(tmp_path):
    with pytest.raises(ConfigError):
        run_swarm(_roster(), _specs(), "Brief.", str(tmp_path / "r.sqlite"),
                  models={"deepseek": ScriptedChatModel()})
