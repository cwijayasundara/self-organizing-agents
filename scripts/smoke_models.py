#!/usr/bin/env python
"""Phase 0 smoke check: tool calling, tool loop and metadata for each roster model."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agora.config import load_roster
from agora.models import _KEY_ENV, build_model

COLUMNS = [
    "key", "served_model", "tool_call_ok", "tool_loop_ok",
    "reasoning_roundtrip", "usage_reported", "max_input_tokens", "latency_s",
]


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def _has_reasoning(msg: AIMessage) -> bool:
    if msg.additional_kwargs.get("reasoning_content"):
        return True
    if isinstance(msg.content, list):
        return any(isinstance(b, dict) and b.get("type") in ("thinking", "reasoning") for b in msg.content)
    return False


def _text(msg: AIMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    return "".join(b.get("text", "") for b in msg.content if isinstance(b, dict))


async def check_model(key: str, spec) -> dict:
    row = dict.fromkeys(COLUMNS, "-")
    row["key"] = key
    env = _KEY_ENV[spec.provider]
    if not os.environ.get(env):
        row.update(served_model=f"skipped (no {env})", skipped=True)
        return row
    row["skipped"] = False
    start = time.monotonic()
    tool_call_ok = tool_loop_ok = reasoning = False
    try:
        model = build_model(spec)
        profile = getattr(model, "profile", None)
        row["max_input_tokens"] = (profile.get("max_input_tokens") if isinstance(profile, dict) else None)
        bound = model.bind_tools([add])
        messages = [HumanMessage("Use the add tool to add 17 and 25")]
        first = await bound.ainvoke(messages)
        meta = first.response_metadata or {}
        row["served_model"] = meta.get("model_name") or meta.get("model")
        row["usage_reported"] = bool(first.usage_metadata)
        tool_call_ok = bool(first.tool_calls) and first.tool_calls[0]["args"] == {"a": 17, "b": 25}
        if tool_call_ok:
            messages += [first, ToolMessage("42", tool_call_id=first.tool_calls[0]["id"])]
            second = await bound.ainvoke(messages)
            tool_loop_ok = "42" in _text(second)
            reasoning = _has_reasoning(first)
    except Exception as e:  # report, don't crash the other models
        row["error"] = f"{type(e).__name__}: {e}"[:200]
    row.update(
        tool_call_ok=tool_call_ok,
        tool_loop_ok=tool_loop_ok,
        reasoning_roundtrip=reasoning and tool_loop_ok,
        latency_s=round(time.monotonic() - start, 2),
    )
    return row


async def run(roster) -> list[dict]:
    return list(await asyncio.gather(*(check_model(k, s) for k, s in roster.models.items())))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", required=True)
    args = parser.parse_args(argv)
    rows = asyncio.run(run(load_roster(args.roster)))

    print(" | ".join(COLUMNS))
    for r in rows:
        print(" | ".join(str(r[c]) for c in COLUMNS))
        if r.get("error"):
            print(f"  error ({r['key']}): {r['error']}")
    skipped = [r["key"] for r in rows if r["skipped"]]
    failed = [r["key"] for r in rows if not r["skipped"] and not (r["tool_call_ok"] and r["tool_loop_ok"])]
    if failed:
        print(f"FAILED: {', '.join(failed)}")
    print(f"skipped (unverified): {', '.join(skipped) if skipped else 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
