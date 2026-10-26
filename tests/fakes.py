"""Test doubles: a scripted chat model and helpers to build a peer around it."""
from __future__ import annotations

import itertools
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from agora.config import PeerSpec, load_roster
from agora.peer import make_peer

_ids = itertools.count(1)


class ScriptedChatModel(BaseChatModel):
    script: list[AIMessage] = Field(default_factory=list)
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[list[str]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kw: Any):
        names = [t["name"] if isinstance(t, dict) else t.name for t in tools]
        self.bound_tools.append(names)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        msg = self.script.pop(0) if self.script else AIMessage("done")
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


def call(name: str, args: dict | None = None) -> dict:
    return {"name": name, "args": args or {}, "id": f"call_{next(_ids)}", "type": "tool_call"}


def tool_call(name: str, args: dict | None = None) -> AIMessage:
    return AIMessage("", tool_calls=[call(name, args)])


def cfg(agent_id: str) -> dict:
    return {"configurable": {"thread_id": f"t:{agent_id}"}, "recursion_limit": 25}


def peer_for(model, ledger, peer_usd: float | None = None, data_dir: str | None = None,
             max_prompt_tokens: int | None = None):
    roster = load_roster("roster.example.yaml")
    peer: PeerSpec = next(p for p in roster.peers if p.id == "P01").model_copy(update={"peer_usd": peer_usd})
    spec = roster.models[peer.model]
    if max_prompt_tokens is not None:
        spec = spec.model_copy(update={"max_prompt_tokens": max_prompt_tokens})
    ledger.mail.register([p.id for p in roster.peers])
    return make_peer(peer, spec, model, ledger, roster.budget, len(roster.peers), "Test brief",
                     InMemorySaver(), data_dir=data_dir)
