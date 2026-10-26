from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PlantedFact:
    id: str
    description: str
    detectors: list[list[str]]  # OR of AND-groups of lowercase substrings


@dataclass(frozen=True)
class GoldKey:
    variant: int
    countries: list[str]
    blocker_country: str
    anomaly_segment: str
    undercutting_competitor: str
    mismatch_delta_eur: float
    mismatch_files: list[str]
    misleading_interview: str
    country_order: list[str]
    planted: list[PlantedFact]

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, indent=2) + "\n"

    @classmethod
    def from_json(cls, s: str) -> "GoldKey":
        d = json.loads(s)
        d["planted"] = [PlantedFact(**p) for p in d["planted"]]
        return cls(**d)
