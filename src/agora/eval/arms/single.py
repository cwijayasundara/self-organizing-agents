"""Single-agent baseline arm, plus the episode driver shared with the supervisor arm."""
from __future__ import annotations

import asyncio
import re
import time

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.errors import GraphRecursionError
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
- Cite every factual claim with the source file, relative to the data-room root, in square brackets, e.g. [crm_pipeline.csv].
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


def _is_final(reply: str) -> bool:
    """True if the reply is just FINAL, ignoring case, whitespace, punctuation, * ` and quotes."""
    return re.sub(r"[\W_]+", "", reply).upper() == "FINAL" and len(reply.split()) == 1


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
                      meter: SpendMeter, clock=time.monotonic, max_episodes: int = 20,
                      stop_fraction: float = 0.9) -> tuple[str, str, int, str]:
    """Run episodes until FINAL (with a dossier), spend/episode/wall-clock limits.

    Returns (status, last_reply, episodes, stop). stop is one of "final", "episode_cap",
    "spend_fraction", "budget_cap", "timeout". A GraphRecursionError ends the episode like a
    normal one (the swarm runner does the same). Episodes count attempts, including cut-off ones. Status: "finished" (FINAL with a dossier, or the
    episode cap was reached), "budget" (spend reached stop_fraction of budget, or the meter's
    cap raised BudgetExceeded), "timeout" (wall clock). Other exceptions propagate."""
    start = clock()
    reply, episodes, message = "", 0, first_message
    while True:
        remaining = budget.wall_clock_s - (clock() - start)
        if remaining <= 0:
            return "timeout", reply, episodes, "timeout"
        episodes += 1
        try:
            result = await asyncio.wait_for(
                agent.ainvoke({"messages": [("user", message)]}, config=config), timeout=remaining)
            messages = result.get("messages")
        except asyncio.TimeoutError:
            return "timeout", reply, episodes, "timeout"
        except BudgetExceeded:
            return "budget", reply, episodes, "budget_cap"
        except GraphRecursionError:
            messages = (await agent.aget_state(config)).values.get("messages")
        reply = _last_ai_text(messages)
        state = await agent.aget_state(config)
        has_file = _read_file(state.values.get("files") or {}, DOSSIER_PATH) is not None
        if _is_final(reply) and has_file:
            return "finished", reply, episodes, "final"
        if meter.total_usd >= stop_fraction * budget.usd:
            return "budget", reply, episodes, "spend_fraction"
        if episodes >= max_episodes:
            return "finished", reply, episodes, "episode_cap"
        message = continuation


async def run_single_arm(arm: str, spec: ModelSpec, model: BaseChatModel, brief: str, data_dir: str,
                         budget: ArmBudget, meter: SpendMeter, variant: int, seed: int,
                         clock=time.monotonic, max_episodes: int = 20) -> ArmOutcome:
    if meter.cap_usd != budget.usd:
        raise ValueError(f"meter cap ${meter.cap_usd} must equal arm budget ${budget.usd}")
    if meter.total_usd != 0:
        raise ValueError(f"meter must be fresh, but already holds ${meter.total_usd}")
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
        config = {"configurable": {"thread_id": f"{arm}:{variant}:{seed}"}, "recursion_limit": budget.episode_recursion_limit}
        status, reply, episodes, stop = await drive_agent(
            agent, config, FIRST_MESSAGE, CONTINUATION, budget, meter, clock=clock,
            max_episodes=max_episodes)
        state = await agent.aget_state(config)  # partial work survives budget stops and timeouts
        text = _read_file(state.values.get("files") or {}, DOSSIER_PATH)
        if text is None:
            text = _last_ai_text(state.values.get("messages")) or reply
    finally:
        detach_all(model)
    return ArmOutcome(arm=arm, variant=variant, seed=seed, status=status, final_text=text,
                      spend_usd=meter.total_usd, elapsed_s=clock() - t0,
                      notes={"episodes": episodes, "model": spec.key, "stop": stop,
                           "episode_recursion_limit": budget.episode_recursion_limit,
                           "max_episodes": max_episodes})
