"""Persist agent configuration and the first effective model request for the viewer."""
from __future__ import annotations

import json

from langchain.agents.middleware import AgentMiddleware
from langchain_core.utils.function_calling import convert_to_openai_tool

from agora.ledger import Ledger


class AgentProfileMiddleware(AgentMiddleware):
    """Capture prompt/tool metadata, without persisting private conversation state."""

    def __init__(self, ledger: Ledger, profile: dict, tools: list):
        super().__init__()
        self.ledger = ledger
        self.profile = {**profile, "recorded": True, "effective_system_prompt": None,
                        "tools": self._tools(tools), "tools_source": "configured ledger tools"}
        self._captured = False
        self._save()

    @staticmethod
    def _tools(tools):
        return [convert_to_openai_tool(t)["function"] for t in tools]

    def _save(self):
        with self.ledger.db.write() as conn:
            conn.execute("INSERT OR REPLACE INTO agent_profiles(agent_id, detail) VALUES (?, ?)",
                         (self.profile["id"], json.dumps(self.profile)))

    def _capture(self, request):
        if self._captured:
            return
        self.profile.update(
            effective_system_prompt=request.system_message.content if request.system_message else "",
            tools=self._tools(request.tools), tools_source="first model request",
        )
        self._save()
        self._captured = True

    def wrap_model_call(self, request, handler):
        self._capture(request)
        return handler(request)

    async def awrap_model_call(self, request, handler):
        self._capture(request)
        return await handler(request)
