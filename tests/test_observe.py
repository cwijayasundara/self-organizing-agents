import json
import logging
import sqlite3
import urllib.error
import urllib.request

import pytest
from langchain_core.messages import AIMessage

from agora import cli
from agora.api import run_swarm
from agora.config import load_roster
from agora.ledger import open_ledger
from agora.ledger.types import TaskSpec
from agora.observe import ConsoleTail, LedgerReader, LiveServer, setup_logging
from fakes import ScriptedChatModel, cfg, peer_for, tool_call


def _spec(tid="T1", deps=()):
    return TaskSpec(id=tid, title=f"Task {tid}", objective="do it", output_format="md",
                    acceptance=["a", "b", "c"], deps=list(deps))


@pytest.fixture
def ledger(tmp_path):
    lg = open_ledger(str(tmp_path / "l.sqlite"))
    lg.mail.register(["P01", "P02"])
    lg.tasks.create_task(_spec())
    return lg


def _db(ledger):
    return ledger.db._conn.execute("PRAGMA database_list").fetchone()["file"]


def test_reader_waits_for_missing_ledger(tmp_path):
    assert LedgerReader(str(tmp_path / "nope.sqlite")).state() == {"waiting": True}


def test_reader_is_incremental(ledger):
    ledger.events.emit("runner", "run_start", json.dumps({"run_name": "r", "peers": [], "swarm_usd": 1,
                                                          "wall_clock_s": 9}))
    ledger.board.write_note("P01", "FACT", "first")
    ledger.mail.send("P01", "P02", "hello", urgent=False)
    r = LedgerReader(_db(ledger))
    s = r.state()
    assert s["roster"]["run_name"] == "r" and s["ended"] is None
    assert [t["id"] for t in s["tasks"]] == ["T1"] and s["tasks"][0]["deps"] == []
    assert [n["text"] for n in s["notes"]] == ["first"]
    assert [m["text"] for m in s["messages"]] == ["hello"]
    ledger.board.write_note("P02", "FACT", "second")
    s2 = r.state(notes=s["notes"][-1]["id"], messages=s["messages"][-1]["id"], events=s["events"][-1]["id"])
    assert [n["text"] for n in s2["notes"]] == ["second"] and s2["messages"] == [] and s2["events"] == []


def test_reader_handles_ledger_without_events_table(ledger):
    path = _db(ledger)
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE events")
    conn.commit()
    conn.close()
    s = LedgerReader(path).state()
    assert s["events"] == [] and s["roster"] is None and [t["id"] for t in s["tasks"]] == ["T1"]


def test_console_tail_logs_coordination(ledger, caplog):
    setup_logging(0)
    logging.getLogger("agora").addHandler(caplog.handler)
    try:
        tail = ConsoleTail(_db(ledger))
        tail.poll()  # baseline: the seeded task
        ledger.events.emit("P01", "episode_start", "Begin.")
        ledger.events.emit("P01", "tool", "list_tasks()")  # DEBUG: hidden at verbosity 0
        ledger.tasks.claim("T1", "P01", "fa")
        ledger.board.write_note("P01", "CLAIM", "taking T1", task_id="T1")
        ledger.mail.send("P01", None, "anyone has prices?", urgent=True)
        ledger.events.emit("P02", "tool_error", "board_write(type=FACT, text=" + "x" * 400
                           + ") -> ERROR: FACT text is 536 chars; the cap is 100")
        tail.poll()
    finally:
        logging.getLogger("agora").removeHandler(caplog.handler)
    text = caplog.text
    assert "P01" in text and "episode 1 starts" in text
    assert "CLAIM T1: taking T1" in text
    assert "→ all (urgent): anyone has prices?" in text
    assert "T1 (Task T1) claimed by P01" in text
    assert "list_tasks" not in text
    assert "-> ERROR: FACT text is 536 chars; the cap is 100" in text  # long args never hide the reason


def test_live_server_endpoints(ledger):
    ledger.tasks.claim("T1", "P01", "fa")
    ledger.artifacts.commit("T1", "P01", "# result")
    server = LiveServer(_db(ledger), port=0).start(open_browser=False)
    try:
        page = urllib.request.urlopen(server.url).read().decode()
        assert "agora live view" in page
        state = json.loads(urllib.request.urlopen(server.url + "api/state?notes=0").read())
        assert state["tasks"][0]["owner"] == "P01"
        art = json.loads(urllib.request.urlopen(server.url + "api/artifact?task=T1").read())
        assert art["content"] == "# result" and art["id"] == "T1@v1"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(server.url + "api/artifact?task=missing")
    finally:
        server.stop()


def test_runner_emits_episode_and_run_events(tmp_path):
    r = load_roster("roster.example.yaml")
    roster = r.model_copy(update={
        "peers": [p for p in r.peers if p.id in ("P01", "P03")],
        "budget": r.budget.model_copy(update={"wall_clock_s": 0.5}),
    })
    models = {"deepseek": ScriptedChatModel(), "haiku": ScriptedChatModel()}
    out = run_swarm(roster, [_spec()], "Brief.", str(tmp_path / "r.sqlite"), models=models,
                    runner_kwargs={"grace_s": 0.1})
    events = out.ledger.events.since()
    kinds = [e.kind for e in events]
    assert kinds[0] == "run_start" and kinds[-1] == "run_end"
    assert json.loads(events[0].detail)["peers"][0] == {
        "id": "P01", "model": "deepseek", "family": "deepseek", "lens": roster.peers[0].lens}
    assert events[-1].detail == out.result.status
    assert "P01" in {e.actor for e in events if e.kind == "episode_start"}  # P03 is still staggered
    assert "episode_end" in kinds


async def test_tool_calls_are_recorded(ledger):
    model = ScriptedChatModel(script=[tool_call("claim_task", {"task_id": "T1"}),
                                      tool_call("claim_task", {"task_id": "nope"}), AIMessage("done")])
    await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, cfg("P01"))
    tools = [e for e in ledger.events.since() if e.kind in ("tool", "tool_error")]
    assert [(e.actor, e.kind, e.task_id) for e in tools] == [
        ("P01", "tool", "T1"), ("P01", "tool_error", "nope")]
    assert tools[0].detail == "claim_task(task_id=T1)"
    assert tools[1].detail.startswith("claim_task(task_id=nope) -> ERROR")


def test_cli_watch_missing_ledger(tmp_path, capsys):
    assert cli.main(["watch", str(tmp_path / "nope.sqlite"), "--no-browser"]) == 1
    assert "does not exist" in capsys.readouterr().err
