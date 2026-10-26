"""Domain checks for the EU market-entry example: data-room citations and the dossier summary block."""
from __future__ import annotations

import json
import math
import os
import re

from agora.config import ConfigError
from agora.ledger.board import Admission
from agora.ledger.types import Artifact, Task
from agora.validators import Validator, non_empty

# Linear-time: the path class excludes '[' and ']', so each '[' starts at most one O(n) scan.
CITATION_RE = re.compile(r"\[([A-Za-z0-9_./-]+\.(?:csv|md))(?::[^\[\]\n]*)?\]")

SUMMARY_KEYS = (
    "recommendation", "country_order", "blocker_country",
    "anomaly_segment", "undercutting_competitor", "arith_mismatch_eur",
)


def extract_citations(text: str) -> list[str]:
    return [m.group(1) for m in CITATION_RE.finditer(text)]


def _resolves(data_dir: str, cited: str) -> bool:
    """True if `cited` is a relative path to an existing file contained in data_dir."""
    try:
        if cited.startswith("/") or ".." in cited.split("/"):
            return False
        root = os.path.realpath(data_dir)
        full = os.path.normpath(os.path.join(root, cited))
        real = os.path.realpath(full)
        if os.path.commonpath([root, real]) != root:
            return False
        return os.path.isfile(real)
    except (OSError, ValueError):
        return False


def citations_resolve(data_dir: str, min_citations: int = 1) -> Validator:
    def check(task: Task, artifact: Artifact) -> list[str]:
        if task.kind not in ("work", "integration"):
            return []
        cites = extract_citations(artifact.content)
        errors = []
        if len(cites) < min_citations:
            errors.append(
                f"citations_resolve: needs at least {min_citations} data-room citations, found {len(cites)}"
            )
        seen: set[str] = set()
        for c in cites:
            if c in seen:
                continue
            seen.add(c)
            if not _resolves(data_dir, c):
                errors.append(f"citations_resolve: citation [{c}] does not resolve to a file in the data room")
        return errors

    return check


def fact_citation_admission(data_dir: str) -> Admission:
    def check(author: str, type: str, text: str, detail: str | None) -> list[str]:
        if type != "FACT":
            return []
        if any(_resolves(data_dir, c) for c in extract_citations(detail or "")):
            return []
        return ["FACT needs a data-room citation in detail"]

    return check


def _valid_summary(obj: object) -> bool:
    if not isinstance(obj, dict) or not all(k in obj for k in SUMMARY_KEYS):
        return False
    order = obj["country_order"]
    if not (isinstance(order, list) and len(order) == 5 and all(isinstance(c, str) for c in order)):
        return False
    if obj["recommendation"] not in ("enter", "hold"):
        return False
    n = obj["arith_mismatch_eur"]
    return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)


def parse_dossier_summary(text: str) -> dict | None:
    lines = text.splitlines()
    found: dict | None = None
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip() != "DOSSIER_SUMMARY":
            i += 1
            continue
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n or lines[j].strip() not in ("```json", "```"):
            i += 1
            continue
        k = j + 1
        while k < n and lines[k].strip() != "```":
            k += 1
        if k >= n:
            break  # unclosed fence: no later block can close either
        try:
            obj = json.loads("\n".join(lines[j + 1:k]))
        except Exception:  # bad JSON, recursion limits, etc.
            obj = None
        if _valid_summary(obj):
            found = obj
        i = k + 1
    return found


def dossier_summary_block() -> Validator:
    def check(task: Task, artifact: Artifact) -> list[str]:
        if task.id != "dossier":
            return []
        if parse_dossier_summary(artifact.content) is None:
            return ["dossier_summary_block: missing or invalid DOSSIER_SUMMARY block"]
        return []

    return check


def build_domain(name: str, data_dir: str) -> tuple[list[Validator], list[Admission]]:
    registry = {
        "eu_market_entry": lambda: (
            [non_empty(), citations_resolve(data_dir), dossier_summary_block()],
            [fact_citation_admission(data_dir)],
        ),
    }
    if name not in registry:
        raise ConfigError(f"unknown domain '{name}'; known: {', '.join(sorted(registry))}")
    return registry[name]()
