import asyncio

import pytest

from agora.ledger.types import LedgerError
from agora.protocol import PROTOCOL
from conftest import approve_through_review, claimed_with_artifact, make_tools_by_name, spec, task_args
from test_runner import build, make_roster


def test_closed_ledger_refuses_reserve_and_submit(ledger):
    art = claimed_with_artifact(ledger, "A", "P01", "deepseek")
    ledger.tasks.close()
    with pytest.raises(LedgerError, match="closing"):
        ledger.tasks.reserve(spec("x"))
    with pytest.raises(LedgerError, match="closing"):
        ledger.tasks.submit_for_review("A", "P01", art.id)
    ledger.tasks.create_task(spec("seed"))  # template seeding keeps working


def test_closed_ledger_still_allows_verdict_and_commit(ledger):
    art = claimed_with_artifact(ledger, "A", "P01", "deepseek")
    review = ledger.tasks.submit_for_review("A", "P01", art.id)
    ledger.tasks.create_task(spec("B"))
    ledger.tasks.claim("B", "P02", "haiku")
    ledger.tasks.claim(review.id, "P03", "anthropic")
    ledger.tasks.close()
    assert ledger.tasks.record_verdict(review.id, "P03", True, "ok").status == "done"
    assert ledger.artifacts.commit("B", "P02", "z" * 300)


def test_tool_errors_when_closed(ledger):
    claimed_with_artifact(ledger, "A", "P01", "deepseek")
    tools = make_tools_by_name("P01", ledger)
    ledger.tasks.close()
    out = tools["create_task"].invoke(task_args())
    assert out.startswith("ERROR:") and "closing" in out
    out = tools["submit_for_review"].invoke({"task_id": "A"})
    assert out.startswith("ERROR:") and "closing" in out


async def test_runner_closes_ledger_on_stop(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20, wall_clock_s=5000)
    runner, _, _ = build(ledger, roster, {})
    assert ledger.tasks.closed is False
    await runner.run()
    assert ledger.tasks.closed is True


async def test_unreviewed_lists_optional_tasks(ledger):
    ledger.tasks.create_task(spec("A"))
    approve_through_review(ledger, "A")
    ledger.tasks.create_task(spec("sub:P01:1", required=False))
    ledger.tasks.claim("sub:P01:1", "P01", "deepseek")
    art = ledger.artifacts.commit("sub:P01:1", "P01", "x" * 300)
    ledger.tasks.submit_for_review("sub:P01:1", "P01", art.id)
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20, wall_clock_s=5000)
    runner, _, _ = build(ledger, roster, {})
    res = await runner.run()
    assert res.unreviewed == ["sub:P01:1"]


async def test_errors_record_last_failure(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=30)

    def boom(peer, text, n):
        raise RuntimeError("boom")

    runner, _, _ = build(ledger, roster, {"P01": boom})
    res = await runner.run()
    assert res.errors["P01"].startswith("RuntimeError: boom")
    assert "P02" not in res.errors


async def test_timeout_error_recorded(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stuck_turn_s=0.02, stall_after_s=30)

    async def hang(peer, text, n):
        await asyncio.Event().wait()

    runner, _, _ = build(ledger, roster, {"P01": hang})
    res = await runner.run()
    assert res.errors["P01"] == "TimeoutError: episode exceeded stuck_turn_s"


def test_protocol_forbids_duplicate_tasks():
    assert "never create a task that duplicates" in PROTOCOL
