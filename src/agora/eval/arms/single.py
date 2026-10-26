"""Single-agent baseline arm, plus the episode driver shared with the supervisor arm."""
from __future__ import annotations

import asyncio
import time

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from agora.config import ModelSpec
from agora.eval.arms.types import ArmOutcome
from agora.eval.config import ArmBudget
from agora.eval.meter import BudgetExceeded, SpendMeter, detach_all

DOSSIER_PATH = "/dossier.md"

SINGLE_PROMPT = """You are a research analyst working alone on the assignment below.

=== BRIEF ===
{brief}
=== END BRIEF ===

How to work:
- You work alone; no one else will help you or review your output.
- The data room is mounted read-only under /data/. Read its README first, then the files you need.
- Plan with the todo tool and keep the plan current.
- Write the final dossier to /dossier.md (Markdown). It must end with the DOSSIER_SUMMARY block exactly as the brief specifies.
- Cite every factual claim with the source file, relative to the data-room root, in square brackets, e.g. [market/sizes.csv].
"""

FIRST_MESSAGE = "Produce the dossier now and save it to /dossier.md."
CONTINUATION = (
    "Re-check your dossier against the brief and the data room. Fix errors and missing items and "
    "rewrite /dossier.md. If it is final, reply with the single word FINAL."
)


def _read_file(files: dict, path: str) -> str | None:
    """Content of a virtual file from deepagents state. In 0.7.32 an entry is
    {'content': str, 'encoding', 'created_at', 'modified_at'}; older versions used a list of lines."""
    entry = (files or {}).get(path)
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry
    content = entry.get("content") if isinstance(entry, dict) else None
    if isinstance(content, list):
        return "\n".join(content)
    return content if isinstance(content, str) else None


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b if isinstance(b, str) else b.get("text", "") for b in content
                       if isinstance(b, (str, dict)))
    return str(content or "")


def _last_ai_text(messages) -> str:
    for m in reversed(messages or []):
        if getattr(m, "type", None) == "ai":
            return _text(m.content)
    return ""


async def drive_agent(agent, config: dict, first_message: str, continuation: str, budget: ArmBudget,
                      meter: SpendMeter, clock=time.monotonic, max_episodes: int = 8,
                      stop_fraction: float = 0.9) -> tuple[str, str, int]:
    """Run episodes until FINAL (with a dossier), spend/episode/wall-clock limits.

    Returns (status, last_reply, episodes). Status: "finished" (FINAL with a dossier, or the
    episode cap was reached), "budget" (spend reached stop_fraction of budget, or the meter's
    cap raised BudgetExceeded), "timeout" (wall clock). Other exceptions propagate."""
    start = clock()
    reply, episodes, message = "", 0, first_message
    while True:
        remaining = budget.wall_clock_s - (clock() - start)
        if remaining <= 0:
            return "timeout", reply, episodes
        try:
            result = await asyncio.wait_for(
                agent.ainvoke({"messages": [("user", message)]}, config=config), timeout=remaining)
        except asyncio.TimeoutError:
            return "timeout", reply, episodes
        except BudgetExceeded:
            return "budget", reply, episodes
        episodes += 1
        reply = _last_ai_text(result.get("messages"))
        state = await agent.aget_state(config)
        has_file = _read_file(state.values.get("files") or {}, DOSSIER_PATH) is not None
        if reply.strip().upper() == "FINAL" and has_file:
            return "finished", reply, episodes
        if meter.total_usd >= stop_fraction * budget.usd:
            return "budget", reply, episodes
        if episodes >= max_episodes:
            return "finished", reply, episodes
        message = continuation


async def run_single_arm(arm: str, spec: ModelSpec, model: BaseChatModel, brief: str, data_dir: str,
                         budget: ArmBudget, meter: SpendMeter, variant: int, seed: int,
                         clock=time.monotonic) -> ArmOutcome:
    t0 = clock()
    meter.attach(model, spec)
    try:
        agent = create_deep_agent(
            model=model,
            system_prompt=SINGLE_PROMPT.replace("{brief}", brief),
            middleware=[TodoListMiddleware()],
            backend=CompositeBackend(
                default=StateBackend(),
                routes={"/data/": FilesystemBackend(root_dir=data_dir, virtual_mode=True)},
            ),
            permissions=[FilesystemPermission(operations=["write"], paths=["/data/**"], mode="deny")],
            checkpointer=InMemorySaver(),
            name=arm,
        )
        config = {"configurable": {"thread_id": f"{arm}:{variant}:{seed}"}, "recursion_limit": 200}
        status, reply, episodes = await drive_agent(
            agent, config, FIRST_MESSAGE, CONTINUATION, budget, meter, clock=clock)
        state = await agent.aget_state(config)  # partial work survives budget stops and timeouts
        text = _read_file(state.values.get("files") or {}, DOSSIER_PATH)
        if text is None:
            text = _last_ai_text(state.values.get("messages")) or reply
    finally:
        detach_all(model)
    return ArmOutcome(arm=arm, variant=variant, seed=seed, status=status, final_text=text,
                      spend_usd=meter.total_usd, elapsed_s=clock() - t0,
                      notes={"episodes": episodes, "model": spec.key})
