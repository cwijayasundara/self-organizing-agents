"""What a finished run shows: the problem it was given, and the final artifact."""
from __future__ import annotations

from typing import Sequence


def _kind(task) -> str:
    return task["kind"] if isinstance(task, dict) else task.kind


def _required(task) -> bool:
    return bool(task["required"] if isinstance(task, dict) else task.required)


def choose_final_tasks(tasks: Sequence) -> list:
    """Integration tasks are the deliverable. Without one, every required task is."""
    integration = [t for t in tasks if _kind(t) == "integration"]
    if integration:
        return list(integration)
    return [t for t in tasks if _required(t) and _kind(t) != "review"]


def format_final_output(brief: str, parts: Sequence[tuple[str, str]]) -> str:
    """parts are (heading, content) for each committed final artifact."""
    lines = ["======== problem ========", brief.rstrip(), ""]
    if not parts:
        lines.append("======== final output: none committed ========")
    else:
        for heading, content in parts:
            lines.append(f"======== final output: {heading} ========")
            lines.append(content.rstrip())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def final_output_text(ledger, brief: str) -> str:
    parts = []
    for task in choose_final_tasks(ledger.tasks.list()):
        art = ledger.artifacts.latest(task.id)
        if art is not None:
            parts.append((f"{art.id} ({task.title})", art.content))
    return format_final_output(brief, parts)
