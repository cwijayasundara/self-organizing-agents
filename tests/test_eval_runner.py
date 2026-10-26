import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agora.config import ModelSpec
from agora.dataroom.generate import generate_dataroom
from agora.eval import arms as arms_mod
from agora.eval.arms.types import ArmOutcome
from agora.eval.config import ArmBudget, load_eval_config
from agora.eval.runner import ResultRow, run_eval
from tests.fakes import ScriptedChatModel

GOOD = json.dumps({"factual_accuracy": 4, "completeness": 4, "citation_quality": 4,
                   "decision_quality": 4, "clarity": 4})


@pytest.fixture
def cfg(tmp_path):
    c = load_eval_config("examples/eu_market_entry/eval.yaml")
    return c.model_copy(update={
        "data_root": str(tmp_path / "data"), "gold_root": str(tmp_path / "gold"),
        "out_dir": str(tmp_path / "out"), "arms": ["c0-deepseek", "c1-10"], "seeds": 1,
        "variants": [0]})


def gold_text(cfg, variant=0):
    g = generate_dataroom(variant, str(Path(cfg.data_root) / f"v{variant}"),
                          str(Path(cfg.gold_root) / f"v{variant}.json"))
    return g, "\n".join(f"{p.description} {' '.join(p.detectors[0])}" for p in g.planted)


def fake_arm(text="", spend=0.5, calls=None, status="done", notes=None):
    async def fn(arm, cfg, models, brief, data_dir, db_path, variant, seed, meter):
        if calls is not None:
            calls.append(dict(arm=arm, models=models, brief=brief, data_dir=data_dir, db_path=db_path,
                              meter=meter, variant=variant, seed=seed))
        return ArmOutcome(arm, variant, seed, status, text, spend, 1.0, notes or {})
    return fn


def judges(*scripts):
    return {"haiku": ScriptedChatModel(script=[AIMessage(s) for s in scripts]),
            "luna": ScriptedChatModel(script=[AIMessage(s) for s in scripts])}


def factory(counter=None):
    def f(cfg):
        if counter is not None:
            counter.append(1)
        return {k: (s, ScriptedChatModel()) for k, s in cfg.team_models.items()}
    return f


def run(cfg, **kw):
    kw.setdefault("max_total_usd", 100.0)
    kw.setdefault("models_factory", factory())
    return asyncio.run(run_eval(cfg, **kw))


def test_run_eval_writes_rows_texts_and_scores(cfg):
    g, text = gold_text(cfg)
    res = run(cfg, run_arm_fn=fake_arm(text), judges_override=judges(GOOD, GOOD, GOOD, GOOD))
    assert len(res.rows) == 2 and not res.stopped_by_cap
    for r in res.rows:
        assert r.recall > 0.5 and r.status == "done"
        assert Path(r.final_text_path).read_text() == text
        assert r.judge_mean == 4.0 and r.judge_id in ("haiku", "luna")
    lines = (Path(cfg.out_dir) / "results.jsonl").read_text().splitlines()
    assert [ResultRow.from_json(l) for l in lines] == res.rows
    assert Path(cfg.out_dir, "texts", "c0-deepseek_v0_s0.md").exists()


def test_resume_skips_existing_rows(cfg):
    _, text = gold_text(cfg)
    first = run(cfg, run_arm_fn=fake_arm(text), judges_override=judges(GOOD, GOOD))
    calls = []
    second = run(cfg, run_arm_fn=fake_arm(text, calls=calls), judges_override=judges())
    assert calls == [] and second.rows == first.rows
    assert second.spent_total_usd == pytest.approx(first.spent_total_usd)


def test_spend_cap_stops_before_unaffordable_run(cfg):
    _, text = gold_text(cfg)
    calls = []
    res = run(cfg, max_total_usd=1.5 * cfg.budget_usd, run_arm_fn=fake_arm(text, spend=2.0, calls=calls),
              judges_override=judges(GOOD, GOOD))
    assert len(calls) == 1 and len(res.rows) == 1 and res.stopped_by_cap


def test_judge_failure_recorded_as_none_not_zero(cfg):
    _, text = gold_text(cfg)
    res = run(cfg, run_arm_fn=fake_arm(text), judges_override=judges("garbage", "garbage"))
    r = res.rows[0]
    assert r.judge_mean is None and "judge" in r.notes


def test_judge_timeout_recorded_as_none(cfg):
    _, text = gold_text(cfg)

    class Hang(ScriptedChatModel):
        async def _agenerate(self, *a, **k):
            await asyncio.sleep(30)

    res = run(cfg, run_arm_fn=fake_arm(text), judges_override={"haiku": Hang(), "luna": Hang()},
              judge_timeout_s=0.05)
    assert all(r.judge_mean is None and "timed out" in r.notes["judge"] for r in res.rows)


def test_empty_dossier_skips_judge(cfg):
    gold_text(cfg)
    j = judges(GOOD)
    res = run(cfg, run_arm_fn=fake_arm(""), judges_override=j)
    r = res.rows[0]
    assert r.judge_mean is None and r.judge_id is None and r.notes["judge"] == "empty dossier"
    assert all(not m.seen for m in j.values())


def test_arm_exception_recorded_as_error_row_and_run_continues(cfg):
    _, text = gold_text(cfg)
    ok = fake_arm(text)

    async def fn(arm, *a):
        if arm == "c0-deepseek":
            raise RuntimeError("boom " * 200)
        return await ok(arm, *a)

    res = run(cfg, run_arm_fn=fn, judges_override=judges(GOOD, GOOD))
    assert [r.status for r in res.rows] == ["error", "done"]
    assert res.rows[0].notes["error"].startswith("RuntimeError: boom")
    assert len(res.rows[0].notes["error"]) <= 320 and res.rows[0].recall == 0.0


def test_gold_never_reaches_arms(cfg):
    g, text = gold_text(cfg)
    calls = []
    run(cfg, run_arm_fn=fake_arm(text, calls=calls), judges_override=judges(GOOD, GOOD))
    c = calls[0]
    assert not Path(cfg.gold_root).resolve().is_relative_to(Path(c["data_dir"]).resolve())
    for answer in (g.undercutting_competitor, g.anomaly_segment, g.misleading_interview):
        assert answer.lower() not in c["brief"].lower()
    assert not any(p.description.lower() in c["brief"].lower() for p in g.planted)
    assert str(Path(cfg.gold_root)) not in c["db_path"] + c["data_dir"]
    assert Path(c["db_path"]).parent.name == "ledgers"


def test_fresh_models_and_meter_per_run(cfg):
    _, text = gold_text(cfg)
    n, calls = [], []
    run(cfg, models_factory=factory(n), run_arm_fn=fake_arm(text, calls=calls),
        judges_override=judges(GOOD, GOOD))
    assert len(n) == 3  # one preflight build + one fresh build per run
    assert calls[0]["meter"] is not calls[1]["meter"]
    assert all(c["meter"].cap_usd == cfg.budget_usd and c["meter"].total_usd == 0 for c in calls)
    assert calls[0]["models"]["glm"][1] is not calls[1]["models"]["glm"][1]


def test_run_arm_dispatch(cfg, monkeypatch):
    seen = []

    async def single(arm, spec, model, brief, data_dir, budget, meter, variant, seed, **k):
        seen.append(("single", arm, spec.key, budget))

    async def sup(arm, spec, model, subs, brief, data_dir, budget, meter, variant, seed, **k):
        seen.append(("sup", arm, spec.key, sorted(subs)))

    async def swarm(arm, n, same, models, brief, template, data_dir, budget, db, variant, seed, **k):
        seen.append(("swarm", arm, n, same, template))

    import agora.eval.arms.single as s1, agora.eval.arms.supervisor as s2, agora.eval.arms.swarm as s3
    monkeypatch.setattr(s1, "run_single_arm", single)
    monkeypatch.setattr(s2, "run_supervisor_arm", sup)
    monkeypatch.setattr(s3, "run_swarm_arm", swarm)
    models = {k: (s.model_copy(update={"key": k}), ScriptedChatModel()) for k, s in cfg.team_models.items()}
    for arm in arms_mod.ARM_IDS:
        asyncio.run(arms_mod.run_arm(arm, cfg, models, "b", "d", "db", 0, 0, None))
    budget = ArmBudget(cfg.budget_usd, float(cfg.wall_clock_s), cfg.episode_recursion_limit)
    assert seen == [
        ("single", "c0-deepseek", "deepseek", budget), ("single", "c0-glm", "glm", budget),
        ("swarm", "c1-10", 10, False, cfg.template_path), ("swarm", "c2-5", 5, False, cfg.template_path),
        ("swarm", "c2-3", 3, False, cfg.template_path),
        ("sup", "c3-supervisor", "deepseek", ["deepseek", "glm"]),
        ("swarm", "a1-same-family", 10, True, cfg.template_path)]
    with pytest.raises(ValueError):
        asyncio.run(arms_mod.run_arm("nope", cfg, models, "b", "d", "db", 0, 0, None))


def _spending_arm(raise_after=True, tokens=1_000_000):
    async def fn(arm, cfg, models, brief, data_dir, db_path, variant, seed, meter):
        spec, model = models["glm"]
        model.script.append(AIMessage("x", usage_metadata={
            "input_tokens": tokens, "output_tokens": tokens, "total_tokens": 2 * tokens}))
        await model.ainvoke("hi")
        if raise_after:
            raise RuntimeError("crash after spend")
        return ArmOutcome(arm, variant, seed, "done", "", 0.0, 1.0, {})
    return fn


def test_unmetered_spend_recorded_on_error_and_success(cfg):
    gold_text(cfg)
    res = run(cfg, run_arm_fn=_spending_arm(), judges_override=judges(GOOD, GOOD))
    assert res.rows[0].status == "error"
    assert res.rows[0].spend_usd == pytest.approx(0.65) and res.rows[0].notes["acct_usd"] == pytest.approx(0.65)
    assert res.spent_total_usd == pytest.approx(1.3)
    ok = run(cfg.model_copy(update={"out_dir": cfg.out_dir + "2"}),
             run_arm_fn=_spending_arm(raise_after=False), judges_override=judges(GOOD, GOOD))
    assert ok.rows[0].status == "done" and ok.rows[0].spend_usd == pytest.approx(0.65)


def test_stale_ledger_quarantined(cfg):
    _, text = gold_text(cfg)
    led = Path(cfg.out_dir) / "ledgers"
    led.mkdir(parents=True)
    (led / "c0-deepseek_v0_s0.sqlite").write_text("stale")
    (led / "c0-deepseek_v0_s0.sqlite-wal").write_text("wal")
    res = run(cfg, run_arm_fn=fake_arm(text), judges_override=judges(GOOD, GOOD))
    assert res.rows[0].status == "done" and res.rows[0].notes["stale_ledger"] == "c0-deepseek_v0_s0.crashed-1.sqlite"
    assert (led / "c0-deepseek_v0_s0.crashed-1.sqlite").read_text() == "stale"
    assert (led / "c0-deepseek_v0_s0.crashed-1.sqlite-wal").exists()


def test_preflight_missing_judge_key_aborts_before_any_arm_call(cfg, monkeypatch):
    from agora.config import ConfigError
    for k in ("FIREWORKS_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    calls = []
    with pytest.raises(ConfigError) as e:
        run(cfg, run_arm_fn=fake_arm("x", calls=calls))
    assert calls == [] and ("ANTHROPIC_API_KEY" in str(e.value) or "OPENAI_API_KEY" in str(e.value))
    assert not Path(cfg.out_dir, "results.jsonl").exists()


def test_error_rows_retried_on_resume_and_spend_counts(cfg):
    _, text = gold_text(cfg)
    res1 = run(cfg, run_arm_fn=_spending_arm(), judges_override=judges(GOOD, GOOD))
    calls = []
    res2 = run(cfg, run_arm_fn=fake_arm(text, spend=0.5, calls=calls), judges_override=judges(GOOD, GOOD, GOOD, GOOD))
    assert len(calls) == 2  # both error rows retried
    assert len(res2.rows) == 4 and [r.status for r in res2.rows] == ["error", "error", "done", "done"]
    assert res2.spent_total_usd == pytest.approx(res1.spent_total_usd + 1.0)
    calls3 = []
    run(cfg, run_arm_fn=fake_arm(text, calls=calls3), judges_override=judges())
    assert calls3 == []


def test_hung_arm_times_out_into_error_row(cfg):
    gold_text(cfg)

    async def hang(*a):
        await asyncio.sleep(30)

    res = run(cfg, run_arm_fn=hang, run_timeout_s=0.05, judges_override=judges())
    assert [r.status for r in res.rows] == ["error", "error"]
    assert "TimeoutError" in res.rows[0].notes["error"]


def test_scoring_error_still_yields_row(cfg, monkeypatch):
    _, text = gold_text(cfg)
    import agora.eval.runner as rn

    def boom(*a):
        raise RuntimeError("score bug")

    monkeypatch.setattr(rn, "score_dossier", boom)
    res = run(cfg, run_arm_fn=fake_arm(text, spend=0.7), judges_override=judges())
    assert res.rows[0].status == "done" and res.rows[0].spend_usd == 0.7
    assert "scoring_error" in res.rows[0].notes and res.rows[0].recall == 0.0


def test_rows_record_budget_in_notes(cfg):
    _, text = gold_text(cfg)
    res = run(cfg, run_arm_fn=fake_arm(text), judges_override=judges(GOOD, GOOD))
    assert res.rows[0].notes["budget_usd"] == cfg.budget_usd and res.rows[0].notes["wall_clock_s"] == 1500
