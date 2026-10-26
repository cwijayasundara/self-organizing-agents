from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from agora.config import load_roster
from agora.eval.arms.supervisor import SUBAGENT_DEFS, SUPERVISOR_PROMPT, run_supervisor_arm
from agora.eval.config import ArmBudget
from agora.eval.meter import SpendMeter
from agora.ledger.budget import cost_of
from agora.ledger.types import Usage
from tests.fakes import ScriptedChatModel, tool_call

ROSTER = load_roster("roster.example.yaml")
DS = ROSTER.models["deepseek"]
GLM = ROSTER.models["glm"]
BRIEF = "Evaluate Zorblax market entry. Distinctive sentence: the walrus council decides.\nUse {braces} safely."
DOSSIER = "# Dossier\nFindings [a.txt]\nDOSSIER_SUMMARY: ok"


def write(path="/dossier.md", content=DOSSIER):
    return tool_call("write_file", {"file_path": path, "content": content})


def delegate(name="market-analyst"):
    return tool_call("task", {"description": "analyse the market", "subagent_type": name})


def usage(tokens=1000, out=500):
    return {"input_tokens": tokens, "output_tokens": out, "total_tokens": tokens + out}


def ai(text, **kw):
    return AIMessage(text, usage_metadata=usage(**kw))


def delegate_u(name="market-analyst"):
    m = delegate(name)
    m.usage_metadata = usage()
    return m


def models(sup_script, sub_script):
    sup = ScriptedChatModel(script=sup_script)
    sub = ScriptedChatModel(script=sub_script)
    return sup, {"glm": (GLM, sub), "deepseek": (DS, sup)}, sub


async def run(sup, subs, tmp_path, usd=1.0, wall=1000.0, cap=None, meter=None, **kw):
    meter = meter or SpendMeter(cap if cap is not None else usd)
    out = await run_supervisor_arm("c0-sup", DS, sup, subs, BRIEF, str(tmp_path),
                                   ArmBudget(usd, wall, 100), meter, 1, 7, **kw)
    return out, meter


async def test_supervisor_delegates_and_writes_dossier(tmp_path):
    sup, subs, sub = models([delegate(), write(), AIMessage("written"), AIMessage("FINAL")],
                            [AIMessage("market findings [a.txt]")])
    out, _ = await run(sup, subs, tmp_path)
    assert out.status == "finished" and out.final_text == DOSSIER
    assert out.notes["stop"] == "final"
    assert out.notes["model"] == DS.key
    assert out.notes["subagents"] == [d["name"] for d in SUBAGENT_DEFS]
    assert out.notes["subagent_models"]["market-analyst"] == "glm"
    assert any("market findings" in str(m.content) for batch in sup.seen for m in batch)
    assert sub.seen  # the specialist model really ran


async def test_spend_counted_across_supervisor_and_subagent(tmp_path):
    sup, subs, _ = models([delegate_u(), write(), AIMessage("w"), AIMessage("FINAL")],
                          [ai("sub done")])
    out, meter = await run(sup, subs, tmp_path)
    assert {DS.key, GLM.key} <= set(meter.by_model)
    assert meter.by_model[GLM.key] > 0 and meter.by_model[DS.key] > 0
    assert out.spend_usd == pytest.approx(meter.total_usd)


async def test_shared_model_counted_once(tmp_path):
    shared = ScriptedChatModel(script=[delegate_u(), ai("sub done"), write(), ai("w"), ai("FINAL")])
    subs = {"glm": (DS, shared), "deepseek": (DS, shared)}
    out, meter = await run(shared, subs, tmp_path)
    assert out.status == "finished"
    # 5 calls, each charged exactly once (4 carry usage; the write call has none)
    one = cost_of(DS, Usage(1000, 0, 500))
    calls_with_usage = 4
    assert meter.total_usd == pytest.approx(one * calls_with_usage)


async def test_budget_cap_inside_subagent_returns_partial_text(tmp_path):
    cap = cost_of(DS, Usage(1000, 0, 500)) * 1.5  # supervisor call 1 ok; crossed in subagent call
    w = write()
    w.usage_metadata = None
    sup, subs, _ = models([w, delegate_u(), AIMessage("never")], [ai("sub done", tokens=10**6)])
    out, meter = await run(sup, subs, tmp_path, usd=cap)
    assert out.status == "budget"
    assert out.final_text == DOSSIER


async def test_subagent_cannot_write_data_dir(tmp_path):
    (tmp_path / "real.txt").write_text("orig")
    sup, subs, _ = models([delegate(), write(), AIMessage("w"), AIMessage("FINAL")],
                          [tool_call("write_file", {"file_path": "/data/x", "content": "hack"}),
                           tool_call("write_file", {"file_path": "/data/real.txt", "content": "hack"}),
                           AIMessage("tried")])
    out, _ = await run(sup, subs, tmp_path)
    assert out.status == "finished"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["real.txt"]
    assert (tmp_path / "real.txt").read_text() == "orig"


async def test_missing_subagent_model_key_raises(tmp_path):
    sup = ScriptedChatModel(script=[])
    with pytest.raises(ValueError, match="glm"):
        await run(sup, {"deepseek": (DS, sup)}, tmp_path)


async def test_meter_guards(tmp_path):
    sup, subs, _ = models([], [])
    with pytest.raises(ValueError):
        await run(sup, subs, tmp_path, usd=1.0, cap=2.0)
    m = SpendMeter(1.0)
    m.attach(ScriptedChatModel(script=[ai("x")]), DS).invoke("a")
    with pytest.raises(ValueError):
        await run(sup, subs, tmp_path, meter=m)


async def test_models_detached_after_run(tmp_path):
    sup, subs, sub = models([write(), AIMessage("w"), AIMessage("FINAL")], [])
    meter = SpendMeter(1.0)
    await run(sup, subs, tmp_path, meter=meter)
    before = meter.total_usd
    sup.invoke("x")
    sub.invoke("x")
    assert meter.total_usd == before
    from agora.eval.meter import _Handler
    assert not any(isinstance(c, _Handler) for c in (sup.callbacks or []) + (sub.callbacks or []))


def test_prompt_has_brief_and_no_template_text():
    p = SUPERVISOR_PROMPT.replace("{brief}", BRIEF)
    assert "walrus council" in p and "{braces}" in p
    assert "/dossier.md" in p and "DOSSIER_SUMMARY" in p and "`task`" in p
    low = p.lower()
    for bad in ("claim a", "claim task", "reviewer", "review protocol", "board", "12 task", "twelve"):
        assert bad not in low


def test_four_subagents_defined_with_alternating_models():
    assert [d["name"] for d in SUBAGENT_DEFS] == [
        "market-analyst", "financial-modeler", "regulatory-analyst", "customer-researcher"]
    assert [d["model"] for d in SUBAGENT_DEFS] == ["glm", "deepseek", "glm", "deepseek"]
    for d in SUBAGENT_DEFS:
        assert d["description"].count(".") == 1 and "/data/" in d["system_prompt"]
        assert "[" in d["system_prompt"]
