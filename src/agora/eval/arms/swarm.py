"""Swarm arm: the supervisor-free swarm on the EU task, with configurable team size and review policy."""
from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

from agora.api import arun_swarm
from agora.config import BudgetSpec, ModelSpec, PeerSpec, ReviewPolicy, RosterConfig
from agora.domain import build_domain
from agora.eval.arms.types import ArmOutcome
from agora.eval.config import ArmBudget
from agora.templates import load_template

# Even positions: judgment-heavy lenses (deepseek peers); odd positions: breadth lenses (glm peers).
# Positions 10 and 11 exist only to keep the tuple at 12; rosters are capped at 10 peers.
LENSES: tuple[str, ...] = (
    "financial model and unit economics",
    "market sizing",
    "go/no-go recommendation and scenario logic",
    "competitor landscape and price benchmarking",
    "regulatory and data-protection risk",
    "go-to-market and sales capacity",
    "cross-section validation and review",
    "customer-interview evidence",
    "pricing and packaging",
    "operations cost and integration editing",
    "risk register and mitigation planning",
    "partner and channel ecosystem",
)

_FAMILIES = ("deepseek", "glm")


def build_swarm_roster(n_peers: int, models: dict[str, ModelSpec], budget: BudgetSpec, data_dir: str,
                       reviewer_family_must_differ: bool = True, run_name: str = "eval") -> RosterConfig:
    if not 3 <= n_peers <= 10:
        raise ValueError(f"n_peers must be between 3 and 10, got {n_peers}")
    if set(models) != set(_FAMILIES):
        raise ValueError(f"models must have exactly the keys {list(_FAMILIES)}, got {sorted(models)}")
    peers = [PeerSpec(id=f"P{i + 1:02d}", model=_FAMILIES[i % 2], lens=LENSES[i]) for i in range(n_peers)]
    return RosterConfig(
        run_name=run_name, models=models, peers=peers, budget=budget,
        review_policy=ReviewPolicy(reviewer_family_must_differ=reviewer_family_must_differ),
        data_dir=data_dir,
    )


def _final_text(ledger) -> str:
    dossier = ledger.artifacts.latest("dossier") if _has_task(ledger, "dossier") else None
    if dossier is not None:
        return dossier.content
    parts = []
    for t in sorted(ledger.tasks.list("done"), key=lambda t: t.id):
        art = ledger.artifacts.latest(t.id)
        if art is not None:
            parts.append(art.content)
    return "\n\n---\n\n".join(parts)


def _has_task(ledger, task_id: str) -> bool:
    return any(t.id == task_id for t in ledger.tasks.list())


async def run_swarm_arm(arm: str, n_peers: int, same_family_review: bool,
                        models: dict[str, tuple[ModelSpec, BaseChatModel]], brief: str, template_path: str,
                        data_dir: str, budget: ArmBudget, db_path: str, variant: int, seed: int,
                        runner_kwargs: dict | None = None) -> ArmOutcome:
    if os.path.exists(db_path):
        raise ValueError(f"db_path already exists: {db_path}")
    roster = build_swarm_roster(
        n_peers, {key: spec.model_copy(update={"key": key}) if spec.key != key else spec
                  for key, (spec, _) in models.items()},
        BudgetSpec(swarm_usd=budget.usd, peer_usd=round(budget.usd / 4, 2),
                   wall_clock_s=budget.wall_clock_s, episode_recursion_limit=budget.episode_recursion_limit),
        data_dir, reviewer_family_must_differ=not same_family_review,
    )
    specs = load_template(template_path)
    validators, admission = build_domain("eu_market_entry", data_dir)
    outcome = await arun_swarm(
        roster, specs, brief, db_path,
        models={key: model for key, (_, model) in models.items()},
        validators=validators, admission=admission, runner_kwargs=runner_kwargs,
    )
    ledger, result = outcome.ledger, outcome.result
    try:
        text = _final_text(ledger)
        spend = ledger.budget.spent()
        tasks = {t.id: t.status for t in ledger.tasks.list()}
    finally:
        ledger.db.close()
    return ArmOutcome(
        arm=arm, variant=variant, seed=seed, status=result.status, final_text=text,
        spend_usd=spend, elapsed_s=result.elapsed_s,
        notes={"unreviewed": result.unreviewed, "retired": result.retired, "exhausted": result.exhausted,
               "errors": result.errors, "episodes": result.episodes, "db_path": db_path,
               "n_peers": n_peers, "same_family_review": same_family_review,
               "episode_recursion_limit": budget.episode_recursion_limit, "tasks": tasks},
    )
