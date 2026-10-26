"""Domain checks for the EU market-entry example: data-room citations and the dossier summary block."""
from __future__ import annotations

import json
import math
import os
import re
from bisect import bisect_right

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
    if isinstance(n, bool):
        return False
    if isinstance(n, int):
        return True  # arbitrary-size ints are finite; never hand them to math.isfinite
    return isinstance(n, float) and math.isfinite(n)


_FENCE_OPEN = re.compile(r"```\s*(?:json)?\s*", re.IGNORECASE)
_MAX_PARSE_ATTEMPTS = 200  # bounds total work on adversarial inputs


def parse_dossier_summary(text: str) -> dict | None:
    try:
        return _parse_dossier_summary(text)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return None


def _parse_dossier_summary(text: str) -> dict | None:
    lines = text.split("\n")
    n = len(lines)
    offsets = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1
    closers = [idx for idx, ln in enumerate(lines) if ln.strip() == "```"]
    decoder = json.JSONDecoder()
    found: dict | None = None
    attempts = 0
    i = 0
    while i < n:
        if lines[i].strip() != "DOSSIER_SUMMARY":
            i += 1
            continue
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n:
            break
        first = lines[j].strip()
        obj: object = None
        nxt = i + 1  # on failure restart right after the marker
        if _FENCE_OPEN.fullmatch(first):
            c = bisect_right(closers, j)
            if c >= len(closers):
                i += 1
                continue  # unclosed fence here; a later marker may still be bare or closed
            k = closers[c]
            attempts += 1
            if attempts > _MAX_PARSE_ATTEMPTS:
                break
            try:
                obj = json.loads("\n".join(lines[j + 1:k]))
            except (ValueError, RecursionError):
                obj = None
            if _valid_summary(obj):
                nxt = k + 1
        elif first.startswith("{"):
            attempts += 1
            if attempts > _MAX_PARSE_ATTEMPTS:
                break
            start = offsets[j] + (len(lines[j]) - len(lines[j].lstrip()))
            try:
                obj, _ = decoder.raw_decode(text, start)
            except (ValueError, RecursionError):
                obj = None
            if _valid_summary(obj):
                nxt = j + 1
        if _valid_summary(obj):
            found = obj  # type: ignore[assignment]
        i = nxt
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
