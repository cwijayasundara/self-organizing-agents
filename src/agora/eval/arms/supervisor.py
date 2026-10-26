"""Supervisor-led arm: one deepagents supervisor delegating to specialist subagents via `task`."""
from __future__ import annotations

import time

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from agora.config import ModelSpec
from agora.eval.arms.single import CONTINUATION, FIRST_MESSAGE, drive_agent, read_final_text
from agora.eval.arms.types import ArmOutcome
from agora.eval.config import ArmBudget
from agora.eval.meter import SpendMeter, detach_all

SUPERVISOR_PROMPT = """You are the supervisor of a small team of specialist researchers working on the assignment below.

=== BRIEF ===
{brief}
=== END BRIEF ===

How to work:
- Plan the work with the todo tool, then delegate research to your specialists with the `task` tool (market-analyst, financial-modeler, regulatory-analyst, customer-researcher). Give each a self-contained description of what to investigate.
- The data room is mounted read-only under /data/. Read its README first; you may read files yourself to verify the specialists' findings.
- Integrate their findings, resolve or flag discrepancies and contradictions, and verify key claims against the data room.
- Write the final dossier to /dossier.md (Markdown). It must end with the DOSSIER_SUMMARY block exactly as the brief specifies.
- Cite every factual claim with the source file, relative to the data-room root, in square brackets, e.g. [crm_pipeline.csv].
"""

_COMMON = (
    "Read the data room under /data/ (its README first, then the files relevant to your task). "
    "Cite every factual claim with the source file, relative to the data-room root, in square brackets, "
    "e.g. [crm_pipeline.csv]. Report any discrepancies or contradictions you find between files. "
    "Return your findings concisely to the supervisor; do not write the final dossier."
)

SUBAGENT_DEFS: list[dict] = [
    {"name": "market-analyst", "model": "glm",
     "description": "Analyses market size, growth, competitors and positioning from the data room.",
     "system_prompt": "You are a market analyst covering market size, growth, competitors and positioning. " + _COMMON},
    {"name": "financial-modeler", "model": "deepseek",
     "description": "Builds and checks the financial model, unit economics and funding needs from the data room.",
     "system_prompt": "You are a financial modeler covering revenue, costs, unit economics and funding needs. " + _COMMON},
    {"name": "regulatory-analyst", "model": "glm",
     "description": "Assesses regulatory, legal and compliance requirements and risks from the data room.",
     "system_prompt": "You are a regulatory analyst covering legal, compliance and licensing requirements and risks. " + _COMMON},
    {"name": "customer-researcher", "model": "deepseek",
     "description": "Examines customers, pipeline, demand signals and feedback from the data room.",
     "system_prompt": "You are a customer researcher covering customers, pipeline, demand signals and feedback. " + _COMMON},
]


async def run_supervisor_arm(arm: str, supervisor_spec: ModelSpec, supervisor_model: BaseChatModel,
                             subagent_models: dict[str, tuple[ModelSpec, BaseChatModel]], brief: str,
                             data_dir: str, budget: ArmBudget, meter: SpendMeter, variant: int, seed: int,
                             clock=time.monotonic, max_episodes: int = 20) -> ArmOutcome:
    if meter.cap_usd != budget.usd:
        raise ValueError(f"meter cap ${meter.cap_usd} must equal arm budget ${budget.usd}")
    if meter.total_usd != 0:
        raise ValueError(f"meter must be fresh, but already holds ${meter.total_usd}")
    missing = sorted({d["model"] for d in SUBAGENT_DEFS} - set(subagent_models))
    if missing:
        raise ValueError(f"subagent_models is missing model keys: {missing}")
    t0 = clock()
    attached: list[BaseChatModel] = []
    pairs = [(supervisor_spec, supervisor_model)] + [subagent_models[d["model"]] for d in SUBAGENT_DEFS]
    try:
        for spec, model in pairs:
            if not any(model is m for m in attached):
                attached.append(model)
            meter.attach(model, spec)  # idempotent per meter: a shared model is charged once
        permissions = [FilesystemPermission(operations=["write"], paths=["/data/**"], mode="deny")]
        subagents = [
            {"name": d["name"], "description": d["description"], "system_prompt": d["system_prompt"],
             "model": subagent_models[d["model"]][1], "permissions": permissions}
            for d in SUBAGENT_DEFS
        ]
        agent = create_deep_agent(
            model=supervisor_model,
            system_prompt=SUPERVISOR_PROMPT.replace("{brief}", brief),
            subagents=subagents,
            middleware=[TodoListMiddleware()],
            backend=CompositeBackend(
                default=StateBackend(),
                routes={"/data/": FilesystemBackend(root_dir=data_dir, virtual_mode=True)},
            ),
            permissions=permissions,
            checkpointer=InMemorySaver(),
            name=arm,
        )
        config = {"configurable": {"thread_id": f"{arm}:{variant}:{seed}"},
                  "recursion_limit": budget.episode_recursion_limit}
        status, reply, episodes, stop = await drive_agent(
            agent, config, FIRST_MESSAGE, CONTINUATION, budget, meter, clock=clock,
            max_episodes=max_episodes)
        text = await read_final_text(agent, config, reply)
    finally:
        for m in attached:
            detach_all(m)
    return ArmOutcome(arm=arm, variant=variant, seed=seed, status=status, final_text=text,
                      spend_usd=meter.total_usd, elapsed_s=clock() - t0,
                      notes={"episodes": episodes, "stop": stop, "model": supervisor_spec.key,
                             "subagents": [d["name"] for d in SUBAGENT_DEFS],
                             "subagent_models": {d["name"]: d["model"] for d in SUBAGENT_DEFS},
                             "episode_recursion_limit": budget.episode_recursion_limit,
                             "max_episodes": max_episodes})
