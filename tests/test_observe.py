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


async def test_agent_profile_records_configuration_and_effective_model_request(ledger, tmp_path):
    model = ScriptedChatModel()
    peer = peer_for(model, ledger, data_dir=str(tmp_path))
    reader = LedgerReader(_db(ledger))
    profile = reader.agent("P01")
    assert profile["id"] == "P01" and profile["model"] == "deepseek"
    assert "Test brief" in profile["system_prompt"]
    assert profile["skills"] == []
    assert profile["memory"]["private_state_recorded"] is False
    assert profile["data_access"] == {"path": "/data/", "mode": "read-only"}
    assert profile["effective_system_prompt"] is None
    await peer.ainvoke({"messages": [("user", "go")]}, cfg("P01"))
    profile = reader.agent("P01")
    assert profile["effective_system_prompt"] == model.seen[0][0].content
    tools = {t["name"]: t for t in profile["tools"]}
    assert set(tools) == set(model.bound_tools[-1])
    assert "task" not in tools and "read_file" in tools
    assert tools["claim_task"]["description"]
    assert tools["claim_task"]["parameters"]["properties"]["task_id"]["type"] == "string"
    first_prompt = profile["effective_system_prompt"]
    await peer.ainvoke({"messages": [("user", "next episode")]}, cfg("P01"))
    # Independent read-only connections can replay this after the peer is gone.
    replay = LedgerReader(_db(ledger)).agent("P01")
    assert replay["effective_system_prompt"] == first_prompt
    assert "next episode" not in json.dumps(replay)


def test_agent_profile_legacy_and_missing(ledger):
    ledger.events.emit("runner", "run_start", json.dumps({"peers": [
        {"id": "P01", "model": "old-model", "family": "old-family", "lens": "research"}]}))
    # A watch process must also work with databases created before profile recording.
    with ledger.db.write() as conn:
        conn.execute("DROP TABLE IF EXISTS agent_profiles")
    reader = LedgerReader(_db(ledger))
    assert reader.agent("P01") == {
        "id": "P01", "model": "old-model", "family": "old-family", "lens": "research",
        "recorded": False,
    }
    assert reader.agent("missing") is None
    assert reader.agent("P01' OR 1=1 --") is None


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
        ledger.events.emit("P02", "claim_refused",
                           "claim_task(task_id=T1) -> ERROR: not open: claimed by P01")
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
    assert "⚠  claim_task" not in text  # a lost claim is not a progress-log warning


def test_live_server_endpoints(ledger):
    peer_for(ScriptedChatModel(), ledger)
    ledger.tasks.claim("T1", "P01", "fa")
    ledger.artifacts.commit("T1", "P01", "# result")
    server = LiveServer(_db(ledger), port=0).start(open_browser=False)
    try:
        page = urllib.request.urlopen(server.url).read().decode()
        assert "agora live view" in page and 'id="result"' in page
        state = json.loads(urllib.request.urlopen(server.url + "api/state?notes=0").read())
        assert state["tasks"][0]["owner"] == "P01"
        assert state["brief"] is None
        assert state["final"] == [{"task_id": "T1", "title": "Task T1", "id": "T1@v1",
                                   "author": "P01", "content": "# result"}]
        profile = json.loads(urllib.request.urlopen(server.url + "api/agent?id=P01").read())
        assert profile["recorded"] is True and "Test brief" in profile["system_prompt"]
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(server.url + "api/agent?id=missing")
        assert missing.value.code == 404
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


async def test_lost_claim_is_recorded_as_a_refusal(ledger):
    ledger.tasks.claim("T1", "P02", "fb")
    model = ScriptedChatModel(script=[tool_call("claim_task", {"task_id": "T1"}), AIMessage("done")])
    await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, cfg("P01"))
    kinds = [e.kind for e in ledger.events.since() if e.actor == "P01" and e.kind in
             ("tool", "tool_error", "claim_refused")]
    assert kinds == ["claim_refused"]
    detail = next(e.detail for e in ledger.events.since() if e.kind == "claim_refused")
    assert "not open: claimed by P02" in detail and "Claimable now: (none)" in detail


def test_cli_watch_missing_ledger(tmp_path, capsys):
    assert cli.main(["watch", str(tmp_path / "nope.sqlite"), "--no-browser"]) == 1
    assert "does not exist" in capsys.readouterr().err
