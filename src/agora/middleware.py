"""Coordination middleware joining the ledger to deepagents/langchain agents.

Prefix-cache rule: after a run starts, no middleware here changes the system message or any
earlier message. The turn-start snapshot is appended as ONE new HumanMessage; peer notices
are appended to the text of a fresh tool result.
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from dataclasses import replace

from langgraph.types import Command
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agora.ledger import Ledger
from agora.ledger.types import Usage
from agora.render import render_notes, render_snapshot, wrap_lines


class HideToolsMiddleware(AgentMiddleware):
    """Remove tools (default: deepagents' `task`) from what the model is shown."""

    def __init__(self, names: frozenset[str] = frozenset({"task"})) -> None:
        super().__init__()
        self.names = names

    def _filtered(self, request):
        keep = [t for t in request.tools if getattr(t, "name", None) not in self.names
                and not (isinstance(t, dict) and t.get("name") in self.names)]
        return request.override(tools=keep)

    def _blocked(self, request) -> ToolMessage | None:
        call = request.tool_call
        if call.get("name") not in self.names:
            return None
        return ToolMessage(content=f"Error: tool '{call['name']}' is not available",
                           tool_call_id=call["id"], name=call["name"], status="error")

    def wrap_tool_call(self, request, handler):
        return self._blocked(request) or handler(request)

    async def awrap_tool_call(self, request, handler):
        return self._blocked(request) or await handler(request)

    def wrap_model_call(self, request, handler):
        return handler(self._filtered(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._filtered(request))


class TurnStartDeltaMiddleware(AgentMiddleware):
    """At the start of each run, append one HumanMessage with the current shared-state snapshot."""

    def __init__(self, agent_id: str, family: str, ledger: Ledger, peer_usd: float, swarm_usd: float) -> None:
        super().__init__()
        self.agent_id, self.family, self.ledger = agent_id, family, ledger
        self.peer_usd, self.swarm_usd = peer_usd, swarm_usd

    def _update(self) -> dict[str, Any]:
        text = render_snapshot(self.ledger, self.agent_id, self.family, self.ledger.board.delta(self.agent_id),
                               peer_usd=self.peer_usd, swarm_usd=self.swarm_usd)
        return {"messages": [HumanMessage(text)]}

    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        return self._update()

    async def abefore_agent(self, state, runtime) -> dict[str, Any] | None:
        return self._update()


class PeerNoticeMiddleware(AgentMiddleware):
    """Append urgent DMs and new FAIL/CLAIM notes from other peers to tool results.

    The note baseline is reset at the start of each episode (the turn-start snapshot already covered
    older notes). Notices are only consumed when they are actually delivered into a tool result.
    """

    MAX_NOTICE_NOTES = 20

    def __init__(self, agent_id: str, ledger: Ledger) -> None:
        super().__init__()
        self.agent_id, self.ledger = agent_id, ledger
        self._last_shown = 0

    def _reset_baseline(self) -> None:
        newest = self.ledger.board.recent(limit=1)
        self._last_shown = newest[-1].id if newest else 0

    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        self._reset_baseline()
        return None

    async def abefore_agent(self, state, runtime) -> dict[str, Any] | None:
        self._reset_baseline()
        return None

    def _notice(self) -> str:
        blocks: list[str] = []
        dms = self.ledger.mail.take(self.agent_id, urgent_only=True)
        if dms:
            blocks.append(wrap_lines([f"URGENT DM from {m.sender}: {m.text}" for m in dms]))
        recent = self.ledger.board.recent(limit=200, since_id=self._last_shown)
        if recent:
            self._last_shown = max(n.id for n in recent)
        notes = [n for n in recent if n.author != self.agent_id and n.type in ("FAIL", "CLAIM")]
        if notes:
            blocks.append(render_notes(notes[-self.MAX_NOTICE_NOTES:]))
        return "PEER NOTICES:\n" + "\n".join(blocks) if blocks else ""

    @staticmethod
    def _with_notice(msg: ToolMessage, notice: str) -> ToolMessage:
        if isinstance(msg.content, str):
            content: Any = f"{msg.content}\n\n{notice}"
        else:
            content = [*msg.content, {"type": "text", "text": notice}]
        return msg.model_copy(update={"content": content})

    def _deliver(self, result):
        if isinstance(result, ToolMessage):
            notice = self._notice()
            return self._with_notice(result, notice) if notice else result
        if isinstance(result, Command) and isinstance(result.update, dict):
            msgs = list(result.update.get("messages") or [])
            idx = next((i for i in range(len(msgs) - 1, -1, -1) if isinstance(msgs[i], ToolMessage)), None)
            if idx is not None:
                notice = self._notice()
                if notice:
                    msgs[idx] = self._with_notice(msgs[idx], notice)
                    return replace(result, update={**result.update, "messages": msgs})
        return result  # nothing to attach to: do not consume notices

    def wrap_tool_call(self, request, handler):
        return self._deliver(handler(request))

    async def awrap_tool_call(self, request, handler):
        return self._deliver(await handler(request))


class BudgetMiddleware(AgentMiddleware):
    """Charge each model call's usage to the ledger; end the episode when the peer budget is spent."""

    def __init__(self, agent_id: str, model_key: str, ledger: Ledger, peer_usd: float) -> None:
        super().__init__()
        self.agent_id, self.model_key, self.ledger, self.peer_usd = agent_id, model_key, ledger, peer_usd

    def _after(self, state) -> dict[str, Any] | None:
        last = state["messages"][-1] if state.get("messages") else None
        usage = getattr(last, "usage_metadata", None) if isinstance(last, AIMessage) else None
        if usage:
            details = usage.get("input_token_details") or {}
            self.ledger.budget.charge(self.agent_id, self.model_key, Usage(
                input_tokens=int(usage.get("input_tokens", 0)),
                cached_input_tokens=int(details.get("cache_read", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0)),
            ))
        if self.ledger.budget.peer_exhausted(self.agent_id, self.peer_usd):
            return {"jump_to": "end"}
        return None

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime) -> dict[str, Any] | None:
        return self._after(state)

    @hook_config(can_jump_to=["end"])
    async def aafter_model(self, state, runtime) -> dict[str, Any] | None:
        return self._after(state)
