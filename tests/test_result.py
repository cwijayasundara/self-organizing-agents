"""The finished run shows the problem and the final artifact."""
import json

from agora.ledger.types import TaskSpec
from agora.observe import LedgerReader
from agora.result import choose_final_tasks, format_final_output


def _task(tid, kind="work", required=True, title=None):
    return TaskSpec(id=tid, title=title or tid, objective="o", output_format="md",
                    acceptance=["a", "b", "c"], deps=[], required=required, kind=kind)


def test_integration_artifact_wins_over_section_work():
    tasks = [_task("productivity"), _task("synthesis", kind="integration"), _task("review:x", kind="review", required=False)]
    assert [t.id for t in choose_final_tasks(tasks)] == ["synthesis"]


def test_without_integration_every_required_task_is_final():
    tasks = [_task("a"), _task("b", required=False), _task("review:a", kind="review", required=False)]
    assert [t.id for t in choose_final_tasks(tasks)] == ["a"]


def test_format_names_the_problem_and_each_artifact():
    text = format_final_output("Should we?\n\nPick one.", [("synthesis@v2 (Memo)", "Pilot.")])
    assert text.startswith("======== problem ========\nShould we?")
    assert "======== final output: synthesis@v2 (Memo) ========\nPilot.\n" in text


def test_format_says_when_nothing_was_committed():
    text = format_final_output("The question.", [])
    assert "final output: none committed" in text


def test_reader_returns_stored_brief_and_only_the_integration_artifact(ledger):
    ledger.meta.put("brief", "Q?\n" + "x" * 4000)
    ledger.tasks.create_task(_task("section"))
    ledger.tasks.create_task(_task("synthesis", kind="integration", title="Memo"))
    ledger.tasks.claim("section", "P01", "fa")
    ledger.artifacts.commit("section", "P01", "section body")
    ledger.tasks.claim("synthesis", "P02", "fb")
    ledger.artifacts.commit("synthesis", "P02", "the memo")
    state = LedgerReader(ledger.db._conn.execute("PRAGMA database_list").fetchone()["file"]).state()
    assert state["brief"].startswith("Q?") and len(state["brief"]) > 4000
    assert [(a["id"], a["title"], a["content"]) for a in state["final"]] == [("synthesis@v1", "Memo", "the memo")]


def test_reader_survives_a_ledger_with_no_brief_table(ledger):
    import sqlite3
    path = ledger.db._conn.execute("PRAGMA database_list").fetchone()["file"]
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE run_meta")
    conn.commit()
    conn.close()
    state = LedgerReader(path).state()
    assert state["brief"] is None and state["final"] == []
