"""Build one peer: a deepagents agent wired to the ledger tools and coordination middleware."""
from __future__ import annotations

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware.summarization import SummarizationMiddleware, compute_summarization_defaults
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from agora.config import BudgetSpec, ModelSpec, PeerSpec
from agora.ledger import Ledger
from agora.middleware import (
    BudgetMiddleware,
    HideToolsMiddleware,
    PeerNoticeMiddleware,
    TurnStartDeltaMiddleware,
)
from agora.protocol import render_protocol
from agora.tools import make_peer_tools


def make_peer(
    peer: PeerSpec,
    spec: ModelSpec,
    model: BaseChatModel,
    ledger: Ledger,
    budget: BudgetSpec,
    n_peers: int,
    brief: str,
    checkpointer,
    data_dir: str | None = None,
) -> CompiledStateGraph:
    peer_usd = peer.peer_usd if peer.peer_usd is not None else budget.peer_usd
    extra: dict = {}
    backend = StateBackend()
    if data_dir is not None:
        backend = CompositeBackend(
            default=StateBackend(),
            routes={"/data/": FilesystemBackend(root_dir=data_dir, virtual_mode=True)},
        )
        extra["permissions"] = [FilesystemPermission(operations=["write"], paths=["/data/**"], mode="deny")]
        extra["backend"] = backend

    middleware = [
        TodoListMiddleware(),
        HideToolsMiddleware(),
        TurnStartDeltaMiddleware(peer.id, spec.family, ledger, peer_usd, budget.swarm_usd),
        PeerNoticeMiddleware(peer.id, ledger),
        BudgetMiddleware(peer.id, spec.key, ledger, peer_usd),
    ]
    if spec.max_prompt_tokens is not None:
        # Same name as deepagents' default, so it replaces that one in place (see _apply_custom_middleware).
        middleware.append(SummarizationMiddleware(
            model=model,
            backend=backend,
            trigger=("tokens", spec.max_prompt_tokens),
            keep=compute_summarization_defaults(model)["keep"],
        ))
    return create_deep_agent(
        model=model,
        system_prompt=render_protocol(peer.id, n_peers, peer.lens, brief),
        tools=make_peer_tools(peer.id, spec.family, ledger),
        middleware=middleware,
        checkpointer=checkpointer,
        name=peer.id,
        **extra,
    )
