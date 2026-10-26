"""Built-in artifact validators: deterministic checks run before a review can approve."""
from __future__ import annotations

from typing import Callable

from agora.ledger.types import Artifact, Task

Validator = Callable[[Task, Artifact], list[str]]


def non_empty(min_chars: int = 200) -> Validator:
    def check(task: Task, artifact: Artifact) -> list[str]:
        n = len(artifact.content.strip())
        if n < min_chars:
            return [f"non_empty: artifact has {n} chars; at least {min_chars} required"]
        return []

    return check


def mentions_acceptance() -> Validator:
    def check(task: Task, artifact: Artifact) -> list[str]:
        text = artifact.content.lower()
        errors = []
        for criterion in task.acceptance:
            lead = " ".join(criterion.lower().split()[:3])
            if lead not in text:
                errors.append(f"mentions_acceptance: missing acceptance criterion '{criterion}'")
        return errors

    return check
