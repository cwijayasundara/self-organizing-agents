import asyncio

from langgraph.errors import GraphRecursionError

from agora.config import PeerSpec, load_roster
from agora.ledger.types import Usage
from agora.runner import NUDGE, START, WARN_1, WARN_2, RunResult, SwarmRunner
from conftest import spec

BIG = 10**9


class RunClock:
    """Runner clock: separate from the ledger clock so leases never expire by accident."""

    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.t

    async def sleep(self, s):
        self.sleeps.append(s)
        self.t += s
        await asyncio.sleep(0)  # cooperative yield only; no real waiting


class FakePeer:
    """Async object with ainvoke(input, config) running fn(peer, text, n) against the ledger."""

    def __init__(self, pid, fn=None):
        self.pid, self.fn, self.inputs, self.calls, self.configs, self.first_at = pid, fn, [], 0, [], None
        self.clock = None

    async def ainvoke(self, inp, config):
        text = inp["messages"][0][1]
        if self.first_at is None and self.clock is not None:
            self.first_at = self.clock()
        self.inputs.append(text)
        self.configs.append(config)
        self.calls += 1
        if self.fn is not None:
            res = self.fn(self, text, self.calls)
            if asyncio.iscoroutine(res):
                await res
        return {}


def make_roster(peers, **budget):
    base = load_roster("roster.example.yaml")
    b = base.budget.model_copy(update={
        "stagger_s": 0.01, "peer_usd": 1000, "idle_poll_s": 1, "stuck_turn_s": 1000, "stall_after_s": 300,
        "wall_clock_s": BIG, "swarm_usd": 1000, **budget,
    })
    return base.model_copy(update={
        "peers": [PeerSpec(id=pid, model=model) for pid, model in peers], "budget": b,
    })


def build(ledger, roster, fns, **kw):
    rc = RunClock()
    fakes = {pid: FakePeer(pid, fns.get(pid)) for p in roster.peers for pid in [p.id]}
    for f in fakes.values():
        f.clock = rc
    runner = SwarmRunner(roster, ledger, fakes, clock=rc, sleep=rc.sleep, **kw)
    return runner, fakes, rc


def worker(ledger, family, task_id):
    """Fake work episode: claim task, commit, submit for review, with a board note."""
    def fn(peer, text, n):
        t = ledger.tasks.get(task_id)
        if t.status == "open":
            ledger.tasks.claim(task_id, peer.pid, family)
            art = ledger.artifacts.commit(task_id, peer.pid, "x" * 300)
            ledger.tasks.submit_for_review(task_id, peer.pid, art.id)
            ledger.board.write_note(peer.pid, "FACT", "did the work")
    return fn


def reviewer(ledger, family):
    def fn(peer, text, n):
        for t in ledger.tasks.claimable(peer.pid, family):
            ledger.tasks.claim(t.id, peer.pid, family)
            ledger.tasks.record_verdict(t.id, peer.pid, True, "ok")
            ledger.board.write_note(peer.pid, "FACT", "reviewed")
    return fn


def charge(ledger, pid, usd_millions):
    """Charge deepseek tokens: $0.30 per million input tokens."""
    ledger.budget.charge(pid, "deepseek", Usage(int(usd_millions * 1_000_000 / 0.30), 0, 0))


async def test_run_ends_when_done(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")])
    runner, fakes, _ = build(ledger, roster,
                             {"P01": worker(ledger, "deepseek", "A"), "P02": reviewer(ledger, "anthropic")})
    res = await runner.run()
    assert isinstance(res, RunResult)
    assert res.status == "done" and res.done.done
    assert ledger.tasks.get("A").status == "done"
    assert fakes["P01"].inputs[0].startswith(START)
    assert fakes["P01"].configs[0] == {
        "configurable": {"thread_id": "example:P01"},
        "recursion_limit": roster.budget.episode_recursion_limit,
    }
    assert res.episodes["P01"] >= 1 and res.episodes["P02"] >= 1 and res.retired == []


async def test_run_stops_on_budget(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], swarm_usd=5)

    def spendy(peer, text, n):
        charge(ledger, peer.pid, 3)
        ledger.board.write_note(peer.pid, "FACT", f"spent {n}")

    runner, _, _ = build(ledger, roster, {"P01": spendy})
    res = await runner.run()
    assert res.status == "budget" and res.spent_usd >= 5
    assert not res.done.done


async def test_timeout(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], wall_clock_s=5)

    def busy(peer, text, n):
        ledger.board.write_note(peer.pid, "FACT", f"busy {n}")

    runner, _, _ = build(ledger, roster, {"P01": busy, "P02": busy})
    res = await runner.run()
    assert res.status == "timeout" and res.elapsed_s >= 5


async def test_silent_peer_gets_nudge(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20)
    runner, fakes, _ = build(ledger, roster, {})
    res = await runner.run()
    assert res.status == "stalled"
    p = fakes["P01"].inputs
    assert START in p[0] and NUDGE not in p[0]
    assert NUDGE in p[1]


async def test_warnings_broadcast_once(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], swarm_usd=100)

    def spendy(peer, text, n):
        charge(ledger, peer.pid, {1: 90, 2: 8}.get(n, 5))
        ledger.board.write_note(peer.pid, "FACT", f"spent {n}")

    runner, fakes, _ = build(ledger, roster, {"P01": spendy})
    res = await runner.run()
    assert res.status == "budget"
    w1, w2 = WARN_1.format(pct=85), WARN_2.format(pct=97)
    assert "85%" in w1 and "97%" in w2
    for pid in ("P01", "P02"):
        texts = [m.text for m in ledger.mail.take(pid, urgent_only=True)]
        assert texts.count(w1) == 1 and texts.count(w2) == 1 and len(texts) == 2
    # P02 was idle (reviews nothing) but is woken once per warning, which arrives in its episode input
    joined = "\n".join(fakes["P02"].inputs)
    assert joined.count(w1) == 1 and joined.count(w2) == 1


async def test_failing_peer_is_retired_and_claims_released(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=30)

    def boom(peer, text, n):
        if n == 1:
            ledger.tasks.claim("A", "P01", "deepseek")
        raise RuntimeError("model exploded")

    runner, fakes, rc = build(ledger, roster, {"P01": boom})
    res = await runner.run()
    assert res.retired == ["P01"] and fakes["P01"].calls == 3 and res.episodes["P01"] == 3
    assert ledger.tasks.get("A").owner != "P01"
    assert ledger.tasks.get("A").status in ("open", "claimed")
    notes = [n.text for n in ledger.board.recent() if n.author == "runner"]
    assert "PEER_RETIRED P01" in notes
    assert 5 in rc.sleeps and 10 in rc.sleeps  # back-off min(5n, 60) after failures 1 and 2


async def test_retired_peer_tasks_returned_to_open(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=30)

    def boom(peer, text, n):
        if n == 1:
            ledger.tasks.claim("A", "P01", "deepseek")
        raise RuntimeError("x")

    runner, _, _ = build(ledger, roster, {"P01": boom})
    await runner.run()
    # P02 (no-op fake) never claims, so A must be back to open
    assert ledger.tasks.get("A").status == "open"


async def test_idle_peer_not_invoked(ledger):
    ledger.tasks.create_task(spec("A"))
    # P01 and P02 share a family so P02 can never review P01's work; P03 reviews.
    roster = make_roster([("P01", "deepseek"), ("P02", "deepseek"), ("P03", "haiku")])

    def only_p01_takes_it(peer, text, n):
        worker(ledger, "deepseek", "A")(peer, text, n)

    # P02 must stay idle: make A unavailable to it by letting P01 claim first (P01 starts first).
    runner, fakes, _ = build(ledger, roster, {
        "P01": only_p01_takes_it, "P03": reviewer(ledger, "anthropic")})
    res = await runner.run()
    assert res.status == "done"
    assert res.episodes["P01"] >= 1
    assert res.episodes["P02"] == 0 and fakes["P02"].calls == 0


async def test_stuck_episode_times_out(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stuck_turn_s=0.02, stall_after_s=30)

    async def hang(peer, text, n):
        await asyncio.Event().wait()

    runner, fakes, rc = build(ledger, roster, {"P01": hang})
    res = await runner.run()
    assert fakes["P01"].calls == 3 and res.retired == ["P01"] and res.episodes["P01"] == 3
    assert 5 in rc.sleeps and 10 in rc.sleeps


async def test_stall_detected(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "deepseek")], stall_after_s=20)
    runner, _, _ = build(ledger, roster, {"P01": worker(ledger, "deepseek", "A")})
    res = await runner.run()
    assert ledger.tasks.get("A").status == "in_review"
    assert res.status == "stalled" and not res.done.done


async def test_stagger_order_respected(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku"), ("P03", "minimax")],
                         stagger_s=3, stall_after_s=30)
    runner, fakes, _ = build(ledger, roster, {})
    await runner.run()
    # the only requirement on the fake clock is that peer i starts no earlier than i * stagger
    assert fakes["P01"].first_at >= 0 and fakes["P02"].first_at >= 3 and fakes["P03"].first_at >= 6


async def test_recursion_error_is_not_a_failure(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=30)

    def recurse(peer, text, n):
        raise GraphRecursionError("limit")

    runner, fakes, rc = build(ledger, roster, {"P01": recurse})
    res = await runner.run()
    assert res.retired == [] and fakes["P01"].calls > 3
    assert 5 not in rc.sleeps


async def test_runner_does_not_consume_urgent_mail(ledger):
    ledger.tasks.create_task(spec("A"))
    ledger.mail.send("P02", "P01", "URGENT-SECRET", urgent=True)
    ledger.mail.send("P02", "P01", "ordinary hello", urgent=False)
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20)
    runner, fakes, _ = build(ledger, roster, {})
    await runner.run()
    first = fakes["P01"].inputs[0]
    assert "ordinary hello" in first and "PEER DATA" in first and "URGENT-SECRET" not in "".join(fakes["P01"].inputs)
    assert [m.text for m in ledger.mail.take("P01", urgent_only=True)] == ["URGENT-SECRET"]


async def test_idle_peer_with_only_urgent_mail_stays_idle(ledger):
    ledger.mail.send("P01", "P02", "urgent ping", urgent=True)
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20)
    runner, fakes, _ = build(ledger, roster, {})
    await runner.run()
    assert fakes["P02"].calls == 0


async def test_noop_peers_stall_instead_of_spinning(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20, wall_clock_s=10000)
    holder = {}

    async def lazy(peer, text, n):
        await holder["rc"].sleep(3)  # LLM latency, does nothing

    runner, fakes, rc = build(ledger, roster, {"P01": lazy, "P02": lazy})
    holder["rc"] = rc
    res = await runner.run()
    assert res.status == "stalled" and res.elapsed_s < 10000
    for pid in ("P01", "P02"):
        assert res.episodes[pid] < 10
        assert sum(NUDGE in t for t in fakes[pid].inputs) <= 1


async def test_long_working_episode_is_not_a_stall(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20, wall_clock_s=10000)
    holder = {}

    async def slow_worker(peer, text, n):
        await holder["rc"].sleep(60)
        worker(ledger, "deepseek", "A")(peer, text, n)

    runner, _, rc = build(ledger, roster, {"P01": slow_worker, "P02": reviewer(ledger, "anthropic")})
    holder["rc"] = rc
    res = await runner.run()
    assert res.status == "done"


async def test_done_during_grace_wins_over_timeout(ledger):
    ledger.tasks.create_task(spec("A"))
    ledger.tasks.claim("A", "P01", "deepseek")
    art = ledger.artifacts.commit("A", "P01", "x" * 300)
    review = ledger.tasks.submit_for_review("A", "P01", art.id)
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], wall_clock_s=5)
    holder = {}

    async def slow_review(peer, text, n):
        ledger.tasks.claim(review.id, "P02", "anthropic")
        await holder["rc"].sleep(8)  # outlives the timeout; completes inside the grace period
        ledger.tasks.record_verdict(review.id, "P02", True, "ok")

    runner, _, rc = build(ledger, roster, {"P02": slow_review})
    holder["rc"] = rc
    res = await runner.run()
    assert res.done.done and res.status == "done"


async def test_failed_then_idle_peer_does_not_block_stall(ledger):
    ledger.tasks.create_task(spec("A"))
    ledger.tasks.claim("A", "P01", "deepseek")
    ledger.mail.send("P01", "P02", "one dm", urgent=False)
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=20, wall_clock_s=5000)

    def boom(peer, text, n):
        raise RuntimeError("x")

    runner, fakes, _ = build(ledger, roster, {"P02": boom})
    res = await runner.run()
    assert res.status == "stalled" and res.elapsed_s < 1000
    assert res.episodes["P01"] < 20 and res.episodes["P02"] == 1


async def test_exhausted_peer_is_stopped_and_task_released(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], peer_usd=1, stall_after_s=30)

    def hog(peer, text, n):
        if n == 1:
            ledger.tasks.claim("A", "P01", "deepseek")
        charge(ledger, peer.pid, 5)
        ledger.board.write_note(peer.pid, "FACT", f"spent {n}")

    runner, fakes, _ = build(ledger, roster,
                             {"P01": hog, "P02": lambda p, t, n: (worker(ledger, "anthropic", "A")(p, t, n),
                                                                   reviewer(ledger, "anthropic")(p, t, n))})
    res = await runner.run()
    assert res.exhausted == ["P01"] and res.retired == []
    assert fakes["P01"].calls == 1  # never invoked again after exhaustion
    assert ledger.tasks.get("A").owner != "P01"
    texts = [n.text for n in ledger.board.recent() if n.author == "runner"]
    assert "PEER_BUDGET_EXHAUSTED P01" in texts
    assert fakes["P02"].calls >= 1


async def test_zero_peer_usd_is_honored(ledger):
    ledger.tasks.create_task(spec("A"))
    roster = make_roster([("P01", "deepseek"), ("P02", "haiku")], stall_after_s=30)
    roster.peers[0] = roster.peers[0].model_copy(update={"peer_usd": 0.0})
    runner, fakes, _ = build(ledger, roster, {})
    res = await runner.run()
    assert res.exhausted == ["P01"] and fakes["P01"].calls == 0
