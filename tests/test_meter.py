from __future__ import annotations

import threading

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from agora.config import load_roster
from agora.eval.meter import BudgetExceeded, SpendMeter, detach_all
from agora.ledger.budget import cost_of
from agora.ledger.types import Usage
from tests.fakes import ScriptedChatModel

ROSTER = load_roster("roster.example.yaml")
DS = ROSTER.models["deepseek"]


def msg(inp=1000, out=500, cached=None, **extra):
    um = {"input_tokens": inp, "output_tokens": out, "total_tokens": (inp or 0) + (out or 0)}
    if cached is not None:
        um["input_token_details"] = {"cache_read": cached}
    um.update(extra)
    return AIMessage("ok", usage_metadata=um)


def model(*msgs):
    return ScriptedChatModel(script=list(msgs))


def test_totals_match_cost_of():
    m = SpendMeter(100.0)
    llm = m.attach(model(msg(1000, 500), msg(2000, 100)), DS)
    llm.invoke("a")
    llm.invoke("b")
    want = cost_of(DS, Usage(1000, 0, 500)) + cost_of(DS, Usage(2000, 0, 100))
    assert m.total_usd == pytest.approx(want)
    assert m.total_usd > 0


def test_cached_tokens_discounted():
    m = SpendMeter(100.0)
    m.attach(model(msg(10000, 10, cached=8000)), DS).invoke("a")
    assert m.total_usd == pytest.approx(cost_of(DS, Usage(10000, 8000, 10)))
    plain = SpendMeter(100.0)
    plain.attach(model(msg(10000, 10)), DS).invoke("a")
    assert m.total_usd < plain.total_usd


async def test_cap_raises_from_invoke():
    m = SpendMeter(cost_of(DS, Usage(1000, 0, 500)) * 1.5)
    llm = m.attach(model(msg(), msg(), msg(), msg()), DS)
    llm.invoke("a")
    with pytest.raises(BudgetExceeded):
        llm.invoke("b")
    with pytest.raises(BudgetExceeded):
        await llm.ainvoke("c")


def test_two_models_accumulate_separately():
    m = SpendMeter(100.0)
    hk = ROSTER.models["haiku"]
    m.attach(model(msg(1000, 100)), DS).invoke("a")
    m.attach(model(msg(3000, 300)), hk).invoke("a")
    bm = m.by_model
    assert set(bm) == {DS.key, hk.key}
    assert bm[DS.key] == pytest.approx(cost_of(DS, Usage(1000, 0, 100)))
    assert bm[hk.key] == pytest.approx(cost_of(hk, Usage(3000, 0, 300)))
    assert m.total_usd == pytest.approx(sum(bm.values()))
    bm.clear()
    assert len(m.by_model) == 2


def test_missing_usage_ignored():
    m = SpendMeter(0.0000001)
    m.attach(model(AIMessage("no usage")), DS).invoke("a")
    assert m.total_usd == 0.0
    assert m.by_model == {}


def test_malformed_usage_does_not_raise():
    m = SpendMeter(1e9)
    none_msg = AIMessage("ok")
    none_msg.usage_metadata = {"input_tokens": None, "output_tokens": None, "total_tokens": 0}  # type: ignore[typeddict-item]
    llm = m.attach(model(msg(-5, 10), none_msg, msg(100, 10, cached=500), msg(100, -1, cached=-3)), DS)
    for _ in range(4):
        llm.invoke("a")
    assert m.total_usd >= 0.0
    # clamped: cached 500 > input 100 costs as cached == input
    clamped = SpendMeter(1e9)
    clamped.attach(model(msg(100, 10, cached=500)), DS).invoke("a")
    assert clamped.total_usd == pytest.approx(cost_of(DS, Usage(100, 100, 10)))


@pytest.mark.parametrize("um", [
    {"input_tokens": float("inf"), "output_tokens": float("inf")},
    {"input_tokens": float("nan"), "output_tokens": float("nan")},
    {"input_tokens": 10**400, "output_tokens": 10**400},
    {"input_tokens": -1, "output_tokens": -1},
    {"input_tokens": None, "output_tokens": None},
    {"input_tokens": "abc", "output_tokens": "x"},
    {"input_tokens": 10, "output_tokens": 5, "input_token_details": ["cache_read"]},
    "not a dict",
])
def test_unusable_usage_never_raises(um):
    m = SpendMeter(1e9)
    ai = AIMessage("ok")
    ai.usage_metadata = um  # type: ignore[assignment]
    m.attach(model(ai), DS).invoke("a")
    if isinstance(um, dict) and um.get("input_tokens") == 10:
        assert m.total_usd == pytest.approx(cost_of(DS, Usage(10, 0, 5)))
    else:
        assert m.total_usd == 0.0


def test_attach_twice_charges_once():
    m = SpendMeter(100.0)
    llm = model(msg())
    m.attach(llm, DS)
    m.attach(llm, DS)
    llm.invoke("a")
    assert m.total_usd == pytest.approx(cost_of(DS, Usage(1000, 0, 500)))


def test_attach_two_specs_latter_wins():
    m = SpendMeter(100.0)
    hk = ROSTER.models["haiku"]
    llm = model(msg())
    m.attach(llm, DS)
    m.attach(llm, hk)
    llm.invoke("a")
    assert m.by_model == {hk.key: pytest.approx(cost_of(hk, Usage(1000, 0, 500)))}


def test_two_meters_count_independently():
    a, b = SpendMeter(100.0), SpendMeter(100.0)
    llm = model(msg())
    a.attach(llm, DS)
    b.attach(llm, DS)
    llm.invoke("x")
    unit = cost_of(DS, Usage(1000, 0, 500))
    assert a.total_usd == pytest.approx(unit) and b.total_usd == pytest.approx(unit)


def test_detach_only_removes_own_handler():
    class H(BaseCallbackHandler):
        pass

    foreign = H()
    a, b = SpendMeter(100.0), SpendMeter(100.0)
    llm = model(msg())
    llm.callbacks = [foreign]
    a.attach(llm, DS)
    b.attach(llm, DS)
    assert a.detach(llm) is llm
    assert foreign in llm.callbacks and len(llm.callbacks) == 2
    llm.invoke("x")
    assert a.total_usd == 0.0 and b.total_usd > 0
    SpendMeter(1.0).detach(model())  # callbacks None is tolerated


def test_detach_all_stops_old_meter():
    old = SpendMeter(1e-9)
    llm = model(msg(), msg())
    old.attach(llm, DS)
    with pytest.raises(BudgetExceeded):
        llm.invoke("a")
    spent = old.total_usd
    assert detach_all(llm) is llm
    llm.invoke("b")
    assert old.total_usd == spent


async def test_deep_agent_subagent_cap(tmp_path):
    from deepagents import create_deep_agent
    from langgraph.checkpoint.memory import InMemorySaver
    from tests.fakes import call

    m = SpendMeter(cost_of(DS, Usage(1000, 0, 500)) * 1.2)  # crossed only by the subagent's call
    sup = m.attach(model(
        AIMessage("", tool_calls=[call("task", {"description": "go", "subagent_type": "sub"})],
                  usage_metadata={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500}),
        AIMessage("done"),
    ), DS)
    sub = m.attach(model(msg(), AIMessage("sub done")), ROSTER.models["haiku"])
    graph = create_deep_agent(
        model=sup,
        subagents=[{"name": "sub", "description": "d", "system_prompt": "s", "model": sub}],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "t"}, "recursion_limit": 25}
    with pytest.raises(BudgetExceeded):
        await graph.ainvoke({"messages": [("user", "hi")]}, config)
    assert set(m.by_model) == {DS.key, ROSTER.models["haiku"].key}
    assert m.by_model[DS.key] == pytest.approx(cost_of(DS, Usage(1000, 0, 500)))
    assert m.by_model[ROSTER.models["haiku"].key] == pytest.approx(cost_of(ROSTER.models["haiku"], Usage(1000, 0, 500)))
    assert graph.get_state(config).values["messages"]


def test_reset_clears_totals():
    m = SpendMeter(100.0)
    m.attach(model(msg()), DS).invoke("a")
    assert m.total_usd > 0
    m.reset()
    assert m.total_usd == 0.0
    assert m.by_model == {}


def test_exception_not_swallowed_in_graph():
    from langgraph.graph import END, START, MessagesState, StateGraph

    m = SpendMeter(1e-9)
    llm = m.attach(model(msg()), DS)

    chain = RunnableLambda(lambda x: x) | llm | RunnableLambda(lambda x: x)
    with pytest.raises(BudgetExceeded):
        chain.invoke("hi")

    llm2 = m.attach(model(msg()), DS)
    g = StateGraph(MessagesState)
    g.add_node("n", lambda s: {"messages": [llm2.invoke(s["messages"])]})
    g.add_edge(START, "n")
    g.add_edge("n", END)
    with pytest.raises(BudgetExceeded):
        g.compile().invoke({"messages": [("user", "hi")]})


def test_attach_preserves_existing_callbacks():
    seen = []

    class H(BaseCallbackHandler):
        def on_llm_end(self, response, **kw):
            seen.append(1)

    llm = model(msg())
    llm.callbacks = [H()]
    m = SpendMeter(100.0)
    assert m.attach(llm, DS) is llm
    assert len(llm.callbacks) == 2
    llm.invoke("a")
    assert seen == [1]
    assert m.total_usd > 0


def test_concurrent_calls_sum_exactly():
    m = SpendMeter(1e9)
    unit = cost_of(DS, Usage(1000, 0, 500))

    class Fixed(ScriptedChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kw):
            return ChatResult(generations=[ChatGeneration(message=msg())])

    fixed = m.attach(Fixed(), DS)

    def work():
        for _ in range(50):
            fixed.invoke("a")

    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert m.total_usd == pytest.approx(400 * unit, rel=1e-12)
