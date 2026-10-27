"""Programmatic entry point: run a swarm on seeded tasks and return the outcome."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from agora.config import ConfigError, RosterConfig
from agora.ledger import Ledger, open_ledger
from agora.ledger.board import Admission
from agora.ledger.types import TaskSpec
from agora.models import build_model
from agora.peer import make_peer
from agora.runner import RunResult, SwarmRunner
from agora.templates import seed_tasks
from agora.validators import Validator


@dataclass(frozen=True)
class SwarmOutcome:
    result: RunResult
    ledger: Ledger
    db_path: str


async def arun_swarm(
    roster: RosterConfig,
    specs: list[TaskSpec],
    brief: str,
    db_path: str,
    *,
    models: dict[str, BaseChatModel] | None = None,
    validators: Sequence[Validator] = (),
    admission: Sequence[Admission] = (),
    runner_kwargs: dict | None = None,
) -> SwarmOutcome:
    used = list(dict.fromkeys(p.model for p in roster.peers))  # only models that peers use
    if models is None:
        models = {key: build_model(roster.models[key]) for key in used}
    else:
        missing = [k for k in used if k not in models]
        if missing:
            raise ConfigError(f"no chat model supplied for roster model(s): {', '.join(missing)}")

    ledger = open_ledger(
        db_path,
        lease_s=roster.budget.lease_s,
        prices=roster.models,
        reviewer_family_must_differ=roster.review_policy.reviewer_family_must_differ,
        validators=validators,
        admission=admission,
    )
    seed_tasks(ledger, specs)
    ledger.meta.put("brief", brief)
    checkpointer = InMemorySaver()
    peers = {
        p.id: make_peer(
            p, roster.models[p.model], models[p.model], ledger, roster.budget,
            len(roster.peers), brief, checkpointer, data_dir=roster.data_dir,
        )
        for p in roster.peers
    }
    result = await SwarmRunner(roster, ledger, peers, **(runner_kwargs or {})).run()
    return SwarmOutcome(result=result, ledger=ledger, db_path=db_path)


def run_swarm(
    roster: RosterConfig,
    specs: list[TaskSpec],
    brief: str,
    db_path: str,
    *,
    models: dict[str, BaseChatModel] | None = None,
    validators: Sequence[Validator] = (),
    admission: Sequence[Admission] = (),
    runner_kwargs: dict | None = None,
) -> SwarmOutcome:
    return asyncio.run(arun_swarm(
        roster, specs, brief, db_path, models=models, validators=validators,
        admission=admission, runner_kwargs=runner_kwargs,
    ))
