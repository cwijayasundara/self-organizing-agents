import os

import pytest
import yaml

import agora.eval.arms.swarm as swarm_mod
from agora.api import SwarmOutcome
from agora.config import BudgetSpec, RosterConfig, load_roster
from agora.eval.arms.swarm import LENSES, build_swarm_roster, run_swarm_arm
from agora.eval.config import ArmBudget
from agora.ledger import open_ledger
from agora.ledger.types import TaskSpec
from agora.runner import RunResult
from fakes import ScriptedChatModel

EXAMPLE = "examples/eu_market_entry/roster.yaml"
TEMPLATE = "examples/eu_market_entry/template.yaml"


def _specs():
    return load_roster(EXAMPLE).models


def _bs(**kw):
    base = dict(swarm_usd=3, peer_usd=0.75, wall_clock_s=1500)
    base.update(kw)
    return BudgetSpec(**base)


def _models_pairs():
    return {k: (spec, ScriptedChatModel()) for k, spec in _specs().items()}


def test_roster_sizes_and_families(tmp_path):
    for n in (3, 5, 10):
        r = build_swarm_roster(n, _specs(), _bs(), str(tmp_path))
        assert isinstance(r, RosterConfig)
        assert len(r.peers) == n
        assert {p.model for p in r.peers} == {"deepseek", "glm"}
        assert {r.models[p.model].family for p in r.peers} == {"deepseek", "zhipu"}
        assert r.data_dir == str(tmp_path)
        assert [p.id for p in r.peers] == [f"P{i:02d}" for i in range(1, n + 1)]
    assert len(LENSES) == 12


def test_ten_peer_roster_matches_example_yaml():
    ex = load_roster(EXAMPLE)
    r = build_swarm_roster(10, ex.models, ex.budget, ex.data_dir)
    assert sorted((p.model, p.lens) for p in r.peers) == sorted((p.model, p.lens) for p in ex.peers)


def test_roster_alternates_families_starting_with_deepseek(tmp_path):
    r = build_swarm_roster(7, _specs(), _bs(), str(tmp_path))
    assert [p.model for p in r.peers] == ["deepseek", "glm"] * 3 + ["deepseek"]


def test_same_family_flag_sets_policy(tmp_path):
    a = build_swarm_roster(4, _specs(), _bs(), str(tmp_path))
    b = build_swarm_roster(4, _specs(), _bs(), str(tmp_path), reviewer_family_must_differ=False)
    assert a.review_policy.reviewer_family_must_differ is True
    assert b.review_policy.reviewer_family_must_differ is False


def test_peer_budget_is_quarter_of_swarm(tmp_path, monkeypatch):
    seen = {}

    async def fake(roster, specs, brief, db_path, **kw):
        seen["roster"] = roster
        raise RuntimeError("stop")

    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)
    import asyncio
    with pytest.raises(RuntimeError):
        asyncio.run(run_swarm_arm("s", 5, False, _models_pairs(), "b", TEMPLATE, str(tmp_path),
                                  ArmBudget(usd=3.0, wall_clock_s=60), str(tmp_path / "x.sqlite"), 0, 0))
    b = seen["roster"].budget
    assert b.swarm_usd == 3.0 and b.peer_usd == 0.75 and b.wall_clock_s == 60


def test_budget_step_limit_flows_to_roster(tmp_path, monkeypatch):
    seen = {}

    async def fake(roster, specs, brief, db_path, **kw):
        seen["roster"] = roster
        raise RuntimeError("stop")

    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)
    import asyncio
    with pytest.raises(RuntimeError):
        asyncio.run(run_swarm_arm("s", 5, True, _models_pairs(), "b", TEMPLATE, str(tmp_path),
                                  ArmBudget(usd=1.0, wall_clock_s=60, episode_recursion_limit=37),
                                  str(tmp_path / "x.sqlite"), 0, 0))
    assert seen["roster"].budget.episode_recursion_limit == 37
    assert seen["roster"].review_policy.reviewer_family_must_differ is False
    # the very ModelSpec objects are in the roster
    pairs = _models_pairs()
    assert all(seen["roster"].models[k].id == pairs[k][0].id for k in pairs)


def test_rejects_bad_model_keys_and_peer_counts(tmp_path):
    for n in (2, 11, 0):
        with pytest.raises(ValueError):
            build_swarm_roster(n, _specs(), _bs(), str(tmp_path))
    s = _specs()
    with pytest.raises(ValueError):
        build_swarm_roster(5, {"deepseek": s["deepseek"]}, _bs(), str(tmp_path))
    with pytest.raises(ValueError):
        build_swarm_roster(5, {**s, "extra": s["glm"]}, _bs(), str(tmp_path))
    with pytest.raises(ValueError):
        build_swarm_roster(5, {"deepseek": s["deepseek"], "other": s["glm"]}, _bs(), str(tmp_path))


async def test_swarm_arm_offline_times_out_with_empty_text(tmp_path):
    db = str(tmp_path / "r.sqlite")
    out = await run_swarm_arm("swarm", 3, False, _models_pairs(), "Brief.", TEMPLATE, str(tmp_path),
                              ArmBudget(usd=1.0, wall_clock_s=1), db, 0, 1,
                              runner_kwargs={"grace_s": 0.1})
    assert out.status == "timeout"
    assert out.final_text == ""
    assert out.spend_usd == 0.0
    assert os.path.exists(out.notes["db_path"])


def _fake_outcome(tmp_path, done: dict[str, str], other=()):
    db = str(tmp_path / "seed.sqlite")
    led = open_ledger(db)
    for tid in list(done) + list(other):
        led.tasks.create_task(TaskSpec(id=tid, title=tid, objective="o", output_format="f",
                                       acceptance=[], deps=[]))
    with led.db.write() as c:
        for tid, text in done.items():
            c.execute("UPDATE tasks SET status='done' WHERE id=?", (tid,))
            c.execute("INSERT INTO artifacts (id, task_id, author, version, content, created_at) "
                      "VALUES (?,?,?,?,?,?)", (f"{tid}@v1", tid, "P01", 1, "old " + text, 1.0))
            c.execute("INSERT INTO artifacts (id, task_id, author, version, content, created_at) "
                      "VALUES (?,?,?,?,?,?)", (f"{tid}@v2", tid, "P01", 2, text, 2.0))
    result = RunResult(status="done", spent_usd=0.0, elapsed_s=1.5, done=True, episodes=3,
                       retired=["P02"], exhausted=[], unreviewed=["x"], errors=[])
    return SwarmOutcome(result=result, ledger=led, db_path=db)


def _patch(monkeypatch, outcome):
    async def fake(*a, **kw):
        return outcome
    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)


async def _run(tmp_path, name="o.sqlite"):
    return await run_swarm_arm("swarm", 5, False, _models_pairs(), "Brief.", TEMPLATE, str(tmp_path),
                               ArmBudget(usd=1.0, wall_clock_s=10), str(tmp_path / name), 2, 3)


async def test_final_text_prefers_dossier_artifact(tmp_path, monkeypatch):
    _patch(monkeypatch, _fake_outcome(tmp_path, {"dossier": "FINAL", "a": "A text"}))
    out = await _run(tmp_path)
    assert out.final_text == "FINAL"
    assert out.notes["final_source"] == "dossier"


async def test_final_source_variants(tmp_path, monkeypatch):
    o = _fake_outcome(tmp_path, {"a": "A"}, other=["dossier"])
    with o.ledger.db.write() as c:
        c.execute("INSERT INTO artifacts (id, task_id, author, version, content, created_at) "
                  "VALUES ('dossier@v1','dossier','P01',1,'DRAFT',1.0)")
    _patch(monkeypatch, o)
    out = await _run(tmp_path)
    assert out.final_text == "DRAFT" and out.notes["final_source"] == "dossier_unaccepted"
    o2 = _fake_outcome(tmp_path / "s", {"a": "A"}) if (tmp_path / "s").mkdir() is None else None
    _patch(monkeypatch, o2)
    assert (await _run(tmp_path, "o2.sqlite")).notes["final_source"] == "sections"
    (tmp_path / "e").mkdir()
    _patch(monkeypatch, _fake_outcome(tmp_path / "e", {}, other=["c"]))
    out = await _run(tmp_path, "o3.sqlite")
    assert out.final_text == "" and out.notes["final_source"] == "empty"


async def test_final_text_joins_done_tasks_without_dossier(tmp_path, monkeypatch):
    _patch(monkeypatch, _fake_outcome(tmp_path, {"b": "B text", "a": "A text"}, other=["c"]))
    out = await _run(tmp_path)
    assert out.final_text == "A text\n\n---\n\nB text"


async def test_notes_keys_and_task_statuses(tmp_path, monkeypatch):
    _patch(monkeypatch, _fake_outcome(tmp_path, {"a": "A"}, other=["c"]))
    out = await _run(tmp_path)
    n = out.notes
    assert n["tasks"] == {"a": "done", "c": "open"}
    assert n["unreviewed"] == ["x"] and n["retired"] == ["P02"] and n["episodes"] == 3
    assert n["n_peers"] == 5 and n["same_family_review"] is False
    assert n["episode_recursion_limit"] == 100
    assert {"exhausted", "errors", "db_path"} <= set(n)
    assert out.elapsed_s == 1.5 and out.spend_usd == 0.0


async def test_existing_db_path_rejected_before_any_model_call(tmp_path, monkeypatch):
    called = []

    async def fake(*a, **kw):
        called.append(1)

    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)
    db = tmp_path / "exists.sqlite"
    db.write_text("")
    with pytest.raises(ValueError):
        await _run(tmp_path, "exists.sqlite")
    assert called == []


async def test_gold_never_passed(tmp_path, monkeypatch):
    seen = {}
    real = _fake_outcome(tmp_path, {"a": "A"})

    async def fake(roster, specs, brief, db_path, **kw):
        seen.update(roster=roster, brief=brief, db_path=db_path, kw=kw)
        return real

    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)
    await _run(tmp_path)
    assert seen["brief"] == "Brief."
    assert seen["roster"].data_dir == str(tmp_path)
    assert seen["db_path"] == str(tmp_path / "o.sqlite")
    assert set(seen["kw"]) == {"models", "validators", "admission", "runner_kwargs"}


async def test_grace_defaults_to_zero_and_override_passes(tmp_path, monkeypatch):
    seen = []
    real = _fake_outcome(tmp_path, {"a": "A"})

    async def fake(roster, specs, brief, db_path, **kw):
        seen.append(kw["runner_kwargs"])
        return real if len(seen) == 1 else _fake_outcome(tmp_path / "second", {"a": "A"})

    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)
    (tmp_path / "second").mkdir()
    out = await _run(tmp_path)
    assert seen[0] == {"grace_s": 0.0} and out.notes["grace_s"] == 0.0
    await run_swarm_arm("swarm", 5, False, _models_pairs(), "Brief.", TEMPLATE, str(tmp_path),
                        ArmBudget(usd=1.0, wall_clock_s=10), str(tmp_path / "p.sqlite"), 0, 0,
                        runner_kwargs={"grace_s": 0.1})
    assert seen[1] == {"grace_s": 0.1}


async def test_fractional_wall_clock_rejected(tmp_path):
    with pytest.raises(ValueError, match="whole number"):
        await run_swarm_arm("swarm", 5, False, _models_pairs(), "b", TEMPLATE, str(tmp_path),
                            ArmBudget(usd=1.0, wall_clock_s=0.5), str(tmp_path / "f.sqlite"), 0, 0)


async def test_spend_is_metered_and_models_detached(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage
    pairs = _models_pairs()
    real = _fake_outcome(tmp_path, {"a": "A"})

    async def fake(roster, specs, brief, db_path, *, models, **kw):
        m = models["deepseek"]
        m.script.append(AIMessage("x", usage_metadata={"input_tokens": 1000, "output_tokens": 500,
                                                       "total_tokens": 1500}))
        await m.ainvoke("hi")
        return real

    monkeypatch.setattr(swarm_mod, "arun_swarm", fake)
    out = await run_swarm_arm("swarm", 5, False, pairs, "b", TEMPLATE, str(tmp_path),
                              ArmBudget(usd=1.0, wall_clock_s=10), str(tmp_path / "m.sqlite"), 0, 0)
    assert out.spend_usd == out.notes["metered_usd"] > 0
    assert out.notes["metered_usd"] >= out.notes["ledger_usd"] - 1e-9
    assert not pairs["deepseek"][1].callbacks
