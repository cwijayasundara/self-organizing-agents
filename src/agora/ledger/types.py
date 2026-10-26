"""Frozen value types shared by every ledger component."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NoteType = Literal["FACT", "OBSERVED", "FAIL", "CLAIM", "PATCH_SUMMARY", "REVIEW", "DISSENT", "DECISION"]
TaskStatus = Literal["open", "claimed", "in_review", "done"]
TaskKind = Literal["work", "integration", "review"]


class LedgerError(Exception):
    pass


class ClaimRejected(LedgerError):
    pass


@dataclass(frozen=True)
class Note:
    id: int
    author: str
    type: NoteType
    text: str
    task_id: str | None
    detail: str | None
    created_at: float
    invalidated: bool


@dataclass(frozen=True)
class TaskSpec:
    id: str
    title: str
    objective: str
    output_format: str
    acceptance: list[str]
    deps: list[str]
    required: bool = True
    kind: TaskKind = "work"


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    objective: str
    output_format: str
    acceptance: list[str]
    deps: list[str]
    required: bool
    kind: TaskKind
    status: TaskStatus
    owner: str | None
    owner_family: str | None
    lease_until: float | None
    review_of: str | None
    author_family: str | None
    artifact_id: str | None
    version: int


@dataclass(frozen=True)
class Artifact:
    id: str
    task_id: str
    author: str
    version: int
    content: str
    created_at: float


@dataclass(frozen=True)
class Message:
    id: int
    sender: str
    recipient: str | None
    text: str
    urgent: bool
    created_at: float


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
