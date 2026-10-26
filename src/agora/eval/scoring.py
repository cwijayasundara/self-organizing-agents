"""Deterministic dossier scorer. Recall matching lives in PlantedFact.found_in."""
from __future__ import annotations

from dataclasses import dataclass

from agora.dataroom.models import GoldKey
from agora.domain import extract_citations, parse_dossier_summary, resolve_citation


@dataclass(frozen=True)
class Scores:
    recall: float
    found: list[str]
    missed: list[str]
    summary_present: bool
    summary_accuracy: float
    citation_validity: float
    citations: int


def _norm(v: object) -> str:
    return v.strip().lower() if isinstance(v, str) else ""


def _summary_accuracy(summary: dict, gold: GoldKey) -> float:
    ok = 0
    for key in ("blocker_country", "anomaly_segment", "undercutting_competitor"):
        ok += _norm(summary.get(key)) == _norm(getattr(gold, key))
    order = summary.get("country_order")
    if isinstance(order, list) and order and gold.country_order:
        ok += (_norm(order[0]) == _norm(gold.country_order[0])
               and _norm(order[-1]) == _norm(gold.country_order[-1]))
    n = summary.get("arith_mismatch_eur")
    if isinstance(n, (int, float)) and not isinstance(n, bool):
        try:
            ok += abs(float(n) - gold.mismatch_delta_eur) <= 1.0
        except (OverflowError, ValueError):
            pass
    return ok / 5


def score_dossier(text: str, gold: GoldKey, data_dir: str) -> Scores:
    try:
        text = text if isinstance(text, str) else str(text)
        found = [p.id for p in gold.planted if p.found_in(text)]
        missed = [p.id for p in gold.planted if p.id not in found]
        recall = len(found) / len(gold.planted) if gold.planted else 0.0
        summary = parse_dossier_summary(text)
        present = summary is not None
        acc = _summary_accuracy(summary, gold) if summary else 0.0
        cites = extract_citations(text)
        valid = sum(1 for c in cites if resolve_citation(data_dir, c))
        return Scores(recall, found, missed, present, acc,
                      valid / len(cites) if cites else 0.0, len(cites))
    except Exception:  # never raise on garbage input
        ids = [p.id for p in gold.planted]
        return Scores(0.0, [], ids, False, 0.0, 0.0, 0)
