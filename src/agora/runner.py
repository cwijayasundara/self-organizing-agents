"""Supervisor-free swarm runner: starts peers staggered, re-invokes them for bounded episodes,
nudges silent peers, broadcasts deadline warnings, retires failing peers and decides when to stop.

The runner never claims, assigns or reorders tasks; it only reads ledger state and writes mail and notes.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from langgraph.errors import GraphRecursionError

from agora.config import RosterConfig
from agora.done import DoneStatus, evaluate_done
from agora.ledger import Ledger
from agora.ledger.types import LedgerError
from agora.render import wrap_lines

NUDGE = "ANYTHING TO PUBLISH? Your last episode wrote no board note. Post a PATCH_SUMMARY, FACT, FAIL or CLAIM, or release your task."
WARN_1 = "NOTICE: {pct}% of the run budget is used. Do not claim new work tasks. Finish, commit and submit what you hold; prefer reviews."
WARN_2 = "NOTICE: {pct}% of the run budget is used. Commit ready artifacts and submit them for review now, then stop."
START = "Begin. Follow your protocol."
CONTINUE = "Continue."

MAX_FAILURES = 3
TICK_S = 1.0


@dataclass(frozen=True)
class RunResult:
    status: Literal["done", "budget", "timeout", "stalled"]
    spent_usd: float
    elapsed_s: float
    done: DoneStatus
    episodes: dict[str, int]
    retired: list[str]
    exhausted: list[str] = field(default_factory=list)
    unreviewed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class SwarmRunner:
    def __init__(
        self,
        roster: RosterConfig,
        ledger: Ledger,
        peers: dict[str, Any],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable] = asyncio.sleep,
        grace_s: float = 30.0,
    ):
        self.roster, self.ledger, self.peers = roster, ledger, peers
        self.clock, self.sleep, self.grace_s = clock, sleep, grace_s
        self.ids = [p.id for p in roster.peers]
        self.episodes = {pid: 0 for pid in self.ids}
        self.retired: list[str] = []
        self.exhausted: list[str] = []
        self._failures = {pid: 0 for pid in self.ids}
        self._started = {pid: False for pid in self.ids}
        self._nudge = {pid: False for pid in self.ids}
        self._nudged = {pid: False for pid in self.ids}  # a NUDGE was delivered and no note has followed
        self._backoff: set[str] = set()  # peers currently inside a failure back-off sleep
        self._noop_streak = {pid: 0 for pid in self.ids}
        self._warnings: dict[str, list[str]] = {pid: [] for pid in self.ids}
        self._mid: set[str] = set()
        self._stopping = False
        self.errors: dict[str, str] = {}

    # ---- public --------------------------------------------------------------
    async def run(self) -> RunResult:
        self.ledger.mail.register(self.ids)
        start = self.clock()
        loops = [asyncio.create_task(self._peer_loop(i, pid)) for i, pid in enumerate(self.ids)]
        try:
            status = await self._monitor(start)
            self._stopping = True
            self.ledger.tasks.close()
            await self._grace()
            if evaluate_done(self.ledger).done:
                status = "done"  # done wins: status == "done" iff result.done.done
        finally:
            for t in loops:
                t.cancel()
            results = await asyncio.gather(*loops, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):  # a bug in a loop must not vanish silently
                raise r
        return RunResult(
            status=status,
            spent_usd=self.ledger.budget.spent(),
            elapsed_s=self.clock() - start,
            done=evaluate_done(self.ledger),
            episodes=dict(self.episodes),
            retired=list(self.retired),
            exhausted=list(self.exhausted),
            unreviewed=sorted(t.id for t in self.ledger.tasks.list()
                              if not t.required and t.kind != "review" and t.status != "done"),
            errors=dict(self.errors),
        )

    # ---- peer loop -----------------------------------------------------------
    def _has_work(self, pid: str) -> bool:
        family = self.roster.model_for(pid).family
        tasks = self.ledger.tasks
        return bool(
            tasks.held_by(pid)
            or tasks.claimable(pid, family)
            or self.ledger.mail.pending(pid, urgent=False) > 0  # urgent mail is the middleware's job
            or self._nudge[pid]
            or self._warnings[pid]
        )

    def _build_input(self, pid: str) -> str:
        parts: list[str] = []
        if not self._started[pid]:
            parts.append(START)
        mail = self.ledger.mail.take(pid, urgent_only=False, non_urgent_only=True)
        if mail:
            parts.append("NEW MESSAGES\n" + wrap_lines([f"{m.sender}: {m.text}" for m in mail]))
        if self._nudge[pid]:
            parts.append(NUDGE)
            self._nudged[pid] = True
        parts.extend(self._warnings[pid])
        self._nudge[pid] = False
        self._warnings[pid] = []
        return "\n\n".join(parts) if parts else CONTINUE

    async def _peer_loop(self, index: int, pid: str) -> None:
        budget = self.roster.budget
        if index:
            await self.sleep(index * budget.stagger_s)
        while not self._stopping and pid not in self.retired and pid not in self.exhausted:
            if self._check_exhausted(pid):
                return
            if not self._has_work(pid):
                await self.sleep(budget.idle_poll_s)
                continue
            text = self._build_input(pid)
            self._started[pid] = True
            before = self.ledger.board.last_note_id(pid)
            fp_before = self._fingerprint()
            failed = False
            self._mid.add(pid)
            try:
                await asyncio.wait_for(
                    self.peers[pid].ainvoke(
                        {"messages": [("user", text)]},
                        {"configurable": {"thread_id": f"{self.roster.run_name}:{pid}"},
                         "recursion_limit": budget.episode_recursion_limit},
                    ),
                    timeout=budget.stuck_turn_s,
                )
            except GraphRecursionError:
                pass  # a normal episode end
            except asyncio.TimeoutError:
                failed = True
                self.errors[pid] = "TimeoutError: episode exceeded stuck_turn_s"
            except Exception as e:
                failed = True
                self.errors[pid] = f"{type(e).__name__}: {e}"[:200]
            finally:
                self._mid.discard(pid)
            self.episodes[pid] += 1
            if self._check_exhausted(pid):
                return
            if failed:
                self._failures[pid] += 1
                if self._failures[pid] >= MAX_FAILURES:
                    self._retire(pid)
                    return
                self._backoff.add(pid)
                try:
                    await self.sleep(min(5 * self._failures[pid], 60))
                finally:
                    self._backoff.discard(pid)
                continue
            self._failures[pid] = 0
            wrote_note = self.ledger.board.last_note_id(pid) != before
            if wrote_note:
                self._nudged[pid] = False
            # At most one NUDGE per no-note streak, and only to a peer that still has something to do.
            elif not self._nudged[pid] and self._has_work(pid):
                self._nudge[pid] = True
            if not wrote_note and self._fingerprint() == fp_before:
                self._noop_streak[pid] += 1
                await self.sleep(budget.idle_poll_s)  # cooldown after an episode that changed nothing
            else:
                self._noop_streak[pid] = 0
                await self.sleep(0)  # always yield between episodes

    def _peer_usd(self, pid: str) -> float:
        spec = next(p for p in self.roster.peers if p.id == pid)
        return spec.peer_usd if spec.peer_usd is not None else self.roster.budget.peer_usd

    def _check_exhausted(self, pid: str) -> bool:
        """A peer at its budget cap is stopped for good: held tasks go back to open, no more episodes."""
        if pid in self.exhausted:
            return True
        if not self.ledger.budget.peer_exhausted(pid, self._peer_usd(pid)):
            return False
        self.exhausted.append(pid)
        for t in self.ledger.tasks.held_by(pid):
            try:
                self.ledger.tasks.release(t.id, pid, "peer budget exhausted")
            except LedgerError:
                pass
        try:
            self.ledger.board.write_note("runner", "OBSERVED", f"PEER_BUDGET_EXHAUSTED {pid}")
        except LedgerError:
            pass
        return True

    def _retire(self, pid: str) -> None:
        self.retired.append(pid)
        # in_review tasks are left alone: the ledger does not sweep them.
        for t in self.ledger.tasks.held_by(pid):
            try:
                self.ledger.tasks.release(t.id, pid, "peer retired")
            except LedgerError:
                pass
        try:
            self.ledger.board.write_note("runner", "OBSERVED", f"PEER_RETIRED {pid}")
        except LedgerError:
            pass

    # ---- monitor -------------------------------------------------------------
    def _fingerprint(self) -> tuple:
        top = self.ledger.db.read("SELECT COALESCE(MAX(id), 0) AS m FROM notes")[0]["m"]
        versions = sum(t.version for t in self.ledger.tasks.list())
        count = self.ledger.db.read("SELECT COUNT(*) AS c FROM messages")[0]["c"]
        return (top, versions, count)

    def _warn(self, template: str, threshold: float) -> None:
        text = template.format(pct=round(threshold * 100))
        self.ledger.mail.send("runner", None, text, urgent=True)
        for pid in self.ids:
            if pid not in self.retired and pid not in self.exhausted:
                self._warnings[pid].append(text)

    async def _monitor(self, start: float) -> str:
        budget = self.roster.budget
        templates = (WARN_1, WARN_2)
        warned = [False, False]
        fp = self._fingerprint()
        changed_at = self.clock()
        while True:
            self.ledger.tasks.sweep_expired()
            now = self.clock()
            elapsed = now - start
            spent = self.ledger.budget.spent()
            frac = max(elapsed / budget.wall_clock_s, spent / budget.swarm_usd)
            for k, threshold in enumerate(budget.warn_fractions):
                if not warned[k] and frac >= threshold:
                    warned[k] = True
                    self._warn(templates[k], threshold)
            new_fp = self._fingerprint()
            if new_fp != fp:
                fp, changed_at = new_fp, now
            if evaluate_done(self.ledger).done:
                return "done"
            if spent >= budget.swarm_usd:
                return "budget"
            if elapsed >= budget.wall_clock_s:
                return "timeout"
            if now - changed_at >= budget.stall_after_s and self._quiescent():
                return "stalled"
            await self.sleep(TICK_S)

    def _quiescent(self) -> bool:
        """Every live peer is between episodes or has been repeatedly no-op."""
        return all(
            pid in self.retired
            or pid in self.exhausted
            or (pid not in self._mid and pid not in self._backoff)
            or self._noop_streak[pid] >= 2
            for pid in self.ids
        )

    async def _grace(self) -> None:
        began = self.clock()
        while self._mid and self.clock() - began < self.grace_s:
            await self.sleep(TICK_S)
