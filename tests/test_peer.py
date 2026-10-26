import re

from langchain_core.messages import AIMessage

from agora import peer as peer_mod
from agora.protocol import render_protocol
from fakes import ScriptedChatModel, call, cfg, peer_for, tool_call


async def test_task_tool_hidden_and_peer_tools_visible(ledger):
    model = ScriptedChatModel(script=[])
    await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    names = set(model.bound_tools[-1])
    assert "task" not in names and {"claim_task", "board_write"} <= names
    assert all("task" not in tools for tools in model.bound_tools)


async def test_task_tool_cannot_be_called(ledger):
    model = ScriptedChatModel(script=[
        tool_call("task", {"description": "x", "subagent_type": "general-purpose"}), AIMessage("ok")])
    out = await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    tool_msg = [m for m in out["messages"] if m.type == "tool"][0]
    assert "not available" in tool_msg.content
    assert len(model.seen) == 2  # no sub-agent model call


async def test_turn_start_delta_message(ledger):
    ledger.board.write_note("P02", "FACT", "germany blocked by licence")
    model = ScriptedChatModel(script=[])
    peer = peer_for(model, ledger)
    await peer.ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    first = "\n".join(str(m.content) for m in model.seen[-1])
    assert "CLAIMABLE NOW" in first and "germany blocked by licence" in first
    await peer.ainvoke({"messages": [("user", "again")]}, config=cfg("P01"))
    second_new = [m for m in model.seen[-1] if "NEW SINCE YOUR LAST TURN" in str(m.content)][-1]
    assert "germany blocked by licence" not in str(second_new.content)  # delta shows each note once


async def test_system_message_stable_across_calls(ledger):
    model = ScriptedChatModel(script=[tool_call("list_tasks", {}), tool_call("list_tasks", {}), AIMessage("ok")])
    peer = peer_for(model, ledger)
    await peer.ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    ledger.board.write_note("P02", "FACT", "new fact between episodes")
    await peer.ainvoke({"messages": [("user", "again")]}, config=cfg("P01"))
    systems = {str(call_[0].content) for call_ in model.seen}
    assert len(systems) == 1 and "CLAIMABLE NOW" not in next(iter(systems))
    prior = model.seen[-2]
    latest = model.seen[-1]  # earlier messages are a prefix of later ones
    assert [m.content for m in latest[:len(prior)]] == [m.content for m in prior]


async def test_data_dir_is_read_only(ledger, tmp_path):
    (tmp_path / "facts.txt").write_text("original")
    model = ScriptedChatModel(script=[
        tool_call("read_file", {"file_path": "/data/facts.txt"}),
        tool_call("write_file", {"file_path": "/data/facts.txt", "content": "boom"}),
        AIMessage("ok"),
    ])
    out = await peer_for(model, ledger, data_dir=str(tmp_path)).ainvoke(
        {"messages": [("user", "go")]}, config=cfg("P01"))
    tool_texts = [str(m.content) for m in out["messages"] if m.type == "tool"]
    assert "original" in tool_texts[0] and (tmp_path / "facts.txt").read_text() == "original"
    assert "boom" not in (tmp_path / "facts.txt").read_text()


async def test_peer_notice_appended_to_tool_result(ledger):
    ledger.mail.register(["P01", "P02"])
    ledger.mail.send("P02", "P01", "I am doing Germany", urgent=True)
    model = ScriptedChatModel(script=[tool_call("list_tasks", {}), AIMessage("ok")])
    out = await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    tool_msg = [m for m in out["messages"] if m.type == "tool"][0]
    assert "PEER NOTICES:" in tool_msg.content and "I am doing Germany" in tool_msg.content


async def test_peer_notice_shows_each_fail_once_and_skips_own_notes(ledger):
    model = ScriptedChatModel(script=[tool_call("list_tasks", {}), tool_call("list_tasks", {}), AIMessage("ok")])
    orig = model._generate

    def gen(messages, *a, **k):
        if not model.seen:  # notes arrive during the episode
            ledger.board.write_note("P02", "FAIL", "scraper approach does not work")
            ledger.board.write_note("P01", "FAIL", "my own failure")
            ledger.board.write_note("P02", "FACT", "plain fact")
        return orig(messages, *a, **k)

    object.__setattr__(model, "_generate", gen)
    out = await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    first, second = [m for m in out["messages"] if m.type == "tool"][:2]
    assert "scraper approach does not work" in first.content
    assert "my own failure" not in first.content and "plain fact" not in first.content
    assert "PEER NOTICES:" not in second.content


async def test_budget_middleware_ends_episode(ledger):
    big = AIMessage("", tool_calls=[call("list_tasks")],
                    usage_metadata={"input_tokens": 5_000_000, "output_tokens": 0, "total_tokens": 5_000_000})
    model = ScriptedChatModel(script=[big, tool_call("list_tasks", {}), AIMessage("never")])
    await peer_for(model, ledger, peer_usd=0.5).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    assert len(model.seen) == 1 and ledger.budget.spent("P01") > 0.5


async def test_budget_middleware_tolerates_missing_usage(ledger):
    model = ScriptedChatModel(script=[tool_call("list_tasks", {}), AIMessage("ok")])
    await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    assert len(model.seen) == 2 and ledger.budget.spent("P01") == 0


def test_protocol_differs_only_in_fields():
    a = render_protocol("P01", 10, "lens-a", "BRIEF")
    b = render_protocol("P02", 10, "lens-b", "BRIEF")
    assert a.replace("P01", "P02").replace("lens-a", "lens-b") == b
    assert not re.search(r"\d{4}-\d{2}-\d{2}", a)


def test_summarization_trigger_follows_max_prompt_tokens(ledger, monkeypatch):
    captured = {}
    real = peer_mod.create_deep_agent

    def spy(**kw):
        captured.update(kw)
        return real(**kw)

    monkeypatch.setattr(peer_mod, "create_deep_agent", spy)
    peer_for(ScriptedChatModel(script=[]), ledger, max_prompt_tokens=90000)
    summ = [m for m in captured["middleware"] if m.name == "SummarizationMiddleware"]
    assert len(summ) == 1 and summ[0]._lc_helper.trigger == ("tokens", 90000)


async def test_urgent_dm_survives_command_result_and_is_delivered_once(ledger):
    ledger.mail.register(["P01", "P02"])
    ledger.mail.send("P02", "P01", "switch to Spain", urgent=True)
    todos = [{"content": "a", "status": "pending"}]
    model = ScriptedChatModel(script=[tool_call("write_todos", {"todos": todos}),
                                      tool_call("list_tasks", {}), AIMessage("ok")])
    out = await peer_for(model, ledger).ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    texts = [str(m.content) for m in out["messages"] if m.type == "tool"]
    assert sum("switch to Spain" in t for t in texts) == 1
    assert ledger.mail.take("P01", urgent_only=True) == []


async def test_preexisting_notes_not_replayed_in_tool_results(ledger):
    for i in range(300):
        ledger.board.write_note("P02", "CLAIM", f"angle {i}")
    model = ScriptedChatModel(script=[tool_call("list_tasks", {}), tool_call("list_tasks", {}), AIMessage("ok")])
    peer = peer_for(model, ledger)
    # a note written during the episode (from a tool call) must still show up
    orig = model._generate

    def gen(messages, *a, **k):
        if len(model.seen) == 1:
            ledger.board.write_note("P02", "FAIL", "mid-episode failure")
        return orig(messages, *a, **k)

    object.__setattr__(model, "_generate", gen)
    out = await peer.ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    first, second = [m for m in out["messages"] if m.type == "tool"][:2]
    assert "PEER NOTICES:" not in first.content
    assert "mid-episode failure" in second.content and "angle 1" not in second.content


async def test_between_episode_notes_in_snapshot_not_in_notices(ledger):
    model = ScriptedChatModel(script=[AIMessage("ok"), tool_call("list_tasks", {}), AIMessage("ok")])
    peer = peer_for(model, ledger)
    await peer.ainvoke({"messages": [("user", "go")]}, config=cfg("P01"))
    ledger.board.write_note("P02", "FAIL", "between episodes failure")
    out = await peer.ainvoke({"messages": [("user", "again")]}, config=cfg("P01"))
    assert "between episodes failure" in "\n".join(str(m.content) for m in model.seen[-2])
    tool_msg = [m for m in out["messages"] if m.type == "tool"][0]
    assert "between episodes failure" not in tool_msg.content
