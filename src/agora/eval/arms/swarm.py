"""Swarm arm: the supervisor-free swarm on the EU task, with configurable team size and review policy.

Arm properties (deliberate):
- peer_usd = usd/4 is above the example roster's 0.6: a single peer cannot hold the whole pool,
  but swarm_usd is the binding cap.
- The swarm enforces the domain validators and admission checks (citations, dossier summary block)
  in the ledger; the single and supervisor arms only receive them as instructions. This is a
  property of the arm under evaluation, not an accident.
- Spend is measured at the model (SpendMeter) like the other arms; the ledger figure is kept in
  notes. The runner's grace period is 0 by default so wall clock and spend are hard-cut like the baselines.
"""
from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

from agora.api import arun_swarm
from agora.config import BudgetSpec, ModelSpec, PeerSpec, ReviewPolicy, RosterConfig
from agora.domain import build_domain
from agora.eval.arms.types import ArmOutcome
from agora.eval.config import ArmBudget
from agora.eval.meter import SpendMeter, detach_all
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


def _final_text(ledger) -> tuple[str, str]:
    dossier = ledger.artifacts.latest("dossier") if _has_task(ledger, "dossier") else None
    if dossier is not None:
        done = ledger.tasks.get("dossier").status == "done"
        return dossier.content, "dossier" if done else "dossier_unaccepted"
    parts = []
    for t in sorted(ledger.tasks.list("done"), key=lambda t: t.id):
        art = ledger.artifacts.latest(t.id)
        if art is not None:
            parts.append(art.content)
    return ("\n\n---\n\n".join(parts), "sections") if parts else ("", "empty")


def _has_task(ledger, task_id: str) -> bool:
    return any(t.id == task_id for t in ledger.tasks.list())


async def run_swarm_arm(arm: str, n_peers: int, same_family_review: bool,
                        models: dict[str, tuple[ModelSpec, BaseChatModel]], brief: str, template_path: str,
                        data_dir: str, budget: ArmBudget, db_path: str, variant: int, seed: int,
                        runner_kwargs: dict | None = None) -> ArmOutcome:
    if os.path.exists(db_path):
        raise ValueError(f"db_path already exists: {db_path}")
    if budget.wall_clock_s != int(budget.wall_clock_s):
        raise ValueError(f"wall_clock_s must be a whole number of seconds, got {budget.wall_clock_s}")
    wall = int(budget.wall_clock_s)
    roster = build_swarm_roster(
        n_peers, {key: spec.model_copy(update={"key": key}) if spec.key != key else spec
                  for key, (spec, _) in models.items()},
        BudgetSpec(swarm_usd=budget.usd, peer_usd=round(budget.usd / 4, 2),
                   wall_clock_s=wall, episode_recursion_limit=budget.episode_recursion_limit),
        data_dir, reviewer_family_must_differ=not same_family_review,
    )
    specs = load_template(template_path)
    validators, admission = build_domain("eu_market_entry", data_dir)
    kwargs = {"grace_s": 0.0, **(runner_kwargs or {})}
    meter = SpendMeter(cap_usd=float("inf"))
    attached: list[BaseChatModel] = []
    try:
        for spec, model in models.values():
            if not any(model is m for m in attached):
                attached.append(model)
            meter.attach(model, spec)
        outcome = await arun_swarm(
            roster, specs, brief, db_path,
            models={key: model for key, (_, model) in models.items()},
            validators=validators, admission=admission, runner_kwargs=kwargs,
        )
    finally:
        for m in attached:
            detach_all(m)
    ledger, result = outcome.ledger, outcome.result
    try:
        text, source = _final_text(ledger)
        ledger_usd = ledger.budget.spent()
        tasks = {t.id: t.status for t in ledger.tasks.list()}
    finally:
        ledger.db.close()
    metered = meter.total_usd
    return ArmOutcome(
        arm=arm, variant=variant, seed=seed, status=result.status, final_text=text,
        spend_usd=metered, elapsed_s=result.elapsed_s,
        notes={"unreviewed": result.unreviewed, "retired": result.retired, "exhausted": result.exhausted,
               "errors": result.errors, "episodes": result.episodes, "db_path": db_path,
               "n_peers": n_peers, "same_family_review": same_family_review,
               "episode_recursion_limit": budget.episode_recursion_limit, "tasks": tasks,
               "final_source": source, "ledger_usd": ledger_usd, "metered_usd": metered,
               "grace_s": kwargs["grace_s"]},
    )
