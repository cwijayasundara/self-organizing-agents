"""Deterministic generator for the synthetic Lumen Analytics data room."""
from __future__ import annotations

import os
import random
from pathlib import Path

from agora.dataroom.models import GoldKey

COUNTRIES = ["Germany", "France", "Netherlands", "Spain", "Poland"]
SEGMENTS = ["SMB", "Mid-market", "Enterprise"]
COMPETITORS = ["Notiva", "Veridia", "Quanta Metrics", "Brightline"]
OWN_NAME = "Lumen Analytics"
OWN_PRICE = 49.0
ROLES = ["Sales Lead", "Customer Success", "Engineer"]
HIRING_FILES = ["hiring_costs_by_country.csv", "hiring_costs_summary.csv"]
CRM_ROWS = 600
BASE_CHURN = 0.08
ANOMALY_CHURN = 0.32

README_LINES = [
    ("README.md", "this index of the data room"),
    ("crm_pipeline.csv", "CRM export of accounts by country, segment, stage and churn"),
    ("cost_structure.csv", "company cost lines and per-country market entry costs"),
    ("competitor_prices.md", "per-seat monthly list prices of four competitors and Lumen"),
    ("hiring_costs_by_country.csv", "planned hires per country with annual cost"),
    ("hiring_costs_summary.csv", "per-country hiring totals with a grand total"),
]


def _write(root: Path, name: str, text: str) -> None:
    (root / name).write_bytes(text.encode("utf-8"))


def _csv(header: str, rows: list[list]) -> str:
    return "\n".join([header] + [",".join(str(c) for c in r) for r in rows]) + "\n"


def _crm(rng: random.Random, anomaly: str) -> str:
    rows = []
    for i in range(CRM_ROWS):
        seg = SEGMENTS[i % 3]  # balanced segments
        stage = rng.choices(["lead", "qualified", "customer"], [3, 2, 5])[0]
        arr = {"SMB": 9000, "Mid-market": 40000, "Enterprise": 150000}[seg]
        arr = int(arr * rng.uniform(0.6, 1.4))
        months = rng.randint(1, 48) if stage == "customer" else 0
        rows.append([f"A{i + 1:04d}", rng.choice(COUNTRIES), seg, arr, stage, months, 0])
    for seg in SEGMENTS:
        idx = [i for i, r in enumerate(rows) if r[2] == seg and r[4] == "customer"]
        rate = ANOMALY_CHURN if seg == anomaly else BASE_CHURN
        for i in rng.sample(idx, round(rate * len(idx))):
            rows[i][6] = 1
    return _csv("account_id,country,segment,arr_eur,stage,months_active,churned", rows)


def _costs(rng: random.Random) -> str:
    rows = [
        ["cloud_hosting", "infrastructure", rng.randrange(180000, 260000, 1000)],
        ["support_staff", "people", rng.randrange(400000, 600000, 1000)],
        ["marketing_baseline", "go_to_market", rng.randrange(250000, 400000, 1000)],
        ["compliance_tooling", "legal", rng.randrange(60000, 120000, 1000)],
    ]
    rows += [[f"entry_cost_{c}", "market_entry", rng.randrange(150000, 450000, 5000)]
             for c in COUNTRIES]
    return _csv("item,category,eur_per_year", rows)


def _prices(rng: random.Random, undercutter: str) -> str:
    lines = ["# Competitor price sheet", "",
             "Per-seat monthly list prices in EUR.", "",
             "| Competitor | EUR per seat per month |", "| --- | --- |"]
    for name in COMPETITORS:
        factor = rng.uniform(0.55, 0.65) if name == undercutter else rng.uniform(0.85, 1.25)
        lines.append(f"| {name} | {OWN_PRICE * factor:.2f} |")
    lines.append(f"| {OWN_NAME} | {OWN_PRICE:.2f} |")
    return "\n".join(lines) + "\n"


def _hiring(rng: random.Random, delta: int) -> tuple[str, str]:
    rows, totals = [], []
    for c in COUNTRIES:
        total = 0
        for role in ROLES:
            cost = rng.randrange(60000, 160000, 1000)
            heads = rng.randint(1, 4)
            rows.append([c, role, heads, cost * heads])
            total += cost * heads
        totals.append([c, total])
    stated = sum(t[1] for t in totals) + delta
    totals.append(["TOTAL", stated])
    return (_csv("country,role,headcount,eur_per_year", rows),
            _csv("country,total_eur_per_year", totals))


def _readme() -> str:
    lines = ["# Lumen Analytics EU market-entry data room", "",
             "Files in this data room:", ""]
    lines += [f"- `{n}`: {d}" for n, d in README_LINES]
    return "\n".join(lines) + "\n"


def _refuse_gold_in_room(out: Path, gold_file: Path) -> None:
    """Refuse when any existing ancestor of gold_file is the data room (inode check)."""
    for cand in [gold_file, *gold_file.parents]:
        if cand.exists() and os.path.samefile(cand, out):
            raise ValueError("gold_path must not be inside the data room")


def generate_dataroom(variant: int, out_dir: str, gold_path: str) -> GoldKey:
    out = Path(out_dir).resolve()
    gold_file = Path(gold_path).resolve()
    if gold_file.is_relative_to(out):
        raise ValueError("gold_path must not be inside the data room")
    rng = random.Random(variant)
    anomaly = SEGMENTS[variant % 3]
    undercutter = COMPETITORS[variant % len(COMPETITORS)]
    delta = rng.randint(20000, 120000)
    by_country, summary = _hiring(rng, delta)
    out.mkdir(parents=True, exist_ok=True)
    _refuse_gold_in_room(out, gold_file)
    gold_file.parent.mkdir(parents=True, exist_ok=True)
    _refuse_gold_in_room(out, gold_file)
    _write(out, "crm_pipeline.csv", _crm(rng, anomaly))
    _write(out, "cost_structure.csv", _costs(rng))
    _write(out, "competitor_prices.md", _prices(rng, undercutter))
    _write(out, "hiring_costs_by_country.csv", by_country)
    _write(out, "hiring_costs_summary.csv", summary)
    _write(out, "README.md", _readme())
    gold = GoldKey(
        variant=variant, countries=list(COUNTRIES),
        blocker_country=COUNTRIES[(variant * 2) % 5], anomaly_segment=anomaly,
        undercutting_competitor=undercutter, mismatch_delta_eur=float(delta),
        mismatch_files=list(HIRING_FILES), misleading_interview="",
        country_order=[], planted=[],
    )
    gold_file.write_bytes(gold.to_json().encode("utf-8"))
    return gold
