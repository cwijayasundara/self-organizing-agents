from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from agora.config import load_roster
from agora.eval.arms.single import CONTINUATION, FIRST_MESSAGE, SINGLE_PROMPT, run_single_arm
from agora.eval.config import ArmBudget
from agora.eval.meter import SpendMeter
from tests.fakes import ScriptedChatModel, tool_call

SPEC = load_roster("roster.example.yaml").models["deepseek"]
BRIEF = "Evaluate Zorblax market entry. Distinctive sentence: the walrus council decides.\nUse {braces} safely."
DOSSIER = "# Dossier\nFindings [a.txt]\nDOSSIER_SUMMARY: ok"


def write(path="/dossier.md", content=DOSSIER):
    return tool_call("write_file", {"file_path": path, "content": content})


def heavy(tokens):  # AI message whose usage costs tokens/1M * $0.30
    return AIMessage("big", usage_metadata={"input_tokens": tokens, "output_tokens": 0, "total_tokens": tokens})


async def arm(model, tmp_path, usd=1.0, wall=1000.0, clock=None, cap=None):
    meter = SpendMeter(cap if cap is not None else usd)
    kw = {"clock": clock} if clock else {}
    out = await run_single_arm("c0-deepseek", SPEC, model, BRIEF, str(tmp_path), ArmBudget(usd, wall),
                               meter, 1, 7, **kw)
    return out, meter


async def test_finished_when_final_reply_and_file_written(tmp_path):
    model = ScriptedChatModel(script=[write(), AIMessage("written"), AIMessage("FINAL")])
    out, _ = await arm(model, tmp_path)
    assert out.status == "finished" and out.final_text == DOSSIER
    assert out.arm == "c0-deepseek" and out.variant == 1 and out.seed == 7


async def test_continuation_sent_until_final(tmp_path):
    model = ScriptedChatModel(script=[write(), AIMessage("draft"), AIMessage("FINAL")])
    out, _ = await arm(model, tmp_path)
    assert out.status == "finished" and out.notes["episodes"] == 2
    assert FIRST_MESSAGE in str(model.seen[0][-1].content)
    assert CONTINUATION in str(model.seen[2][-1].content)


async def test_final_without_file_keeps_going(tmp_path):
    model = ScriptedChatModel(script=[AIMessage("FINAL"), write(), AIMessage("FINAL")])
    out, _ = await arm(model, tmp_path)
    assert out.status == "finished" and out.notes["episodes"] == 2 and out.final_text == DOSSIER


async def test_budget_exceeded_returns_partial_text(tmp_path):
    model = ScriptedChatModel(script=[write(), heavy(4_000_000)])
    out, meter = await arm(model, tmp_path, usd=1.0)
    assert out.status == "budget" and out.final_text == DOSSIER
    assert out.spend_usd == meter.total_usd >= 1.0


async def test_spend_stop_fraction(tmp_path):
    model = ScriptedChatModel(script=[write(), heavy(3_200_000), AIMessage("more")])  # $0.96 of $1
    out, meter = await arm(model, tmp_path, usd=1.0)
    assert out.status == "budget" and out.final_text == DOSSIER
    assert 0.9 <= meter.total_usd < 1.0 and out.notes["episodes"] == 1


async def test_wall_clock_timeout(tmp_path):
    ticks = {"n": 0}

    def clock():  # the first reads are at t=0; later reads are past the wall clock
        ticks["n"] += 1
        return 0.0 if ticks["n"] <= 3 else 500.0

    model = ScriptedChatModel(script=[write(), AIMessage("draft")])
    out, _ = await arm(model, tmp_path, wall=100.0, clock=clock)
    assert out.status == "timeout" and out.final_text == DOSSIER
    assert out.elapsed_s >= 100.0


async def test_data_dir_is_read_only(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("orig")
    model = ScriptedChatModel(script=[write("/data/x", "boom"), write("/data/a.txt", "boom"), write(),
                                      AIMessage("FINAL")])
    out, _ = await arm(model, data)
    assert sorted(p.name for p in data.iterdir()) == ["a.txt"]
    assert (data / "a.txt").read_text() == "orig"
    assert out.final_text == DOSSIER


async def test_episode_cap(tmp_path):
    model = ScriptedChatModel(script=[])
    out, _ = await arm(model, tmp_path)
    assert out.status == "finished" and out.notes["episodes"] == 8
    assert len(model.seen) == 8


async def test_model_detached_after_run(tmp_path):
    model = ScriptedChatModel(script=[write(), AIMessage("FINAL")])
    out, meter = await arm(model, tmp_path)
    before = meter.total_usd
    model.script = [heavy(1_000_000)]
    await model.ainvoke("hi")
    assert meter.total_usd == before


async def test_prompt_has_brief_and_no_template_text(tmp_path):
    model = ScriptedChatModel(script=[write(), AIMessage("FINAL")])
    await arm(model, tmp_path)
    system = str(model.seen[0][0].content)
    assert "the walrus council decides" in system and "{braces}" in system
    assert "claim_task" not in system and "board" not in system.lower()
    assert "claim_task" not in SINGLE_PROMPT and "board" not in SINGLE_PROMPT.lower()
