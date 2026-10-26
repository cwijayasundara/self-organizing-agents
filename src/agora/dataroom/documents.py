"""Deterministic interview and regulatory-memo writers for the data room."""
from __future__ import annotations

import csv
import io
import random

from agora.dataroom.models import PlantedFact

N_INTERVIEWS = 20
MISLEADING_PHRASE = "we would pay 40% more"

ROLES = ["Head of Operations", "Finance Director", "Data Lead", "CTO", "Procurement Manager"]
CONSISTENT_OPENERS = [
    "Our budget is tight and price is a regular topic in renewals.",
    "We compared several tools last year and cost decided the shortlist.",
    "The team likes the product but finance reviews every seat.",
    "Price matters to us, though we value the dashboards.",
]
CONSISTENT_CLAIMS = [
    "We would pay 5% more for the features we use daily, but not beyond that.",
    "We would pay 8% more if support response times improved.",
    "We would pay 10% more for an annual plan with fixed pricing.",
    "A rise of about 6% would be acceptable, anything bigger goes to review.",
]
CLOSERS = [
    "We would look at alternatives if the price moved sharply.",
    "A clear price list would help our planning.",
    "Discounts for multi-year terms are important to us.",
]

MEMO_TEMPLATES_OK = [
    "A national data-processing licence is required. Applications are routinely "
    "approved and the typical timeline is {n} months.",
    "Operators must hold a local data-processing licence. The regulator publishes "
    "a standard procedure and issues licences in about {n} months.",
]
MEMO_BLOCKED = (
    "A mandatory local data-processing licence applies to foreign analytics "
    "providers. Under the current procedure the licence cannot be obtained "
    "within 18 months, and operating without it is not permitted."
)
MEMO_REGISTER = {
    "Germany": "the federal data-protection conferences",
    "France": "the national data-protection authority",
    "Netherlands": "the Dutch data-protection authority",
    "Spain": "the Spanish data-protection agency",
    "Poland": "the Polish personal-data protection office",
}


CHURN_MARKERS = ["higher", "highest", "elevated", "anomal", "spike", "triple",
                 "three times", "3x", "outlier"]


def parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def misleading_number(variant: int) -> int:
    return (variant * 7) % N_INTERVIEWS + 1


def _pick_accounts(rng: random.Random, crm: list[dict]) -> tuple[list[str], str]:
    ok = sorted(r["account_id"] for r in crm if r["stage"] == "customer" and r["churned"] == "0")
    churned = sorted(r["account_id"] for r in crm
                     if r["stage"] == "customer" and r["churned"] == "1")
    return [rng.choice(ok) for _ in range(N_INTERVIEWS)], rng.choice(churned)


def _interview(n: int, account: str, rng: random.Random, misleading: bool) -> str:
    claim = (f"Honestly, {MISLEADING_PHRASE} for the same product." if misleading
             else rng.choice(CONSISTENT_CLAIMS))
    lines = [f"# Customer interview {n:02d}", "",
             f"Account: {account}",
             f"Interviewee role: {rng.choice(ROLES)}", "",
             "Topic: price sensitivity", "",
             rng.choice(CONSISTENT_OPENERS), claim, rng.choice(CLOSERS)]
    return "\n".join(lines) + "\n"


def interview_files(variant: int, crm: list[dict]) -> dict[str, str]:
    rng = random.Random(f"{variant}:docs")
    accounts, bad_account = _pick_accounts(rng, crm)
    bad = misleading_number(variant)
    files = {}
    for n in range(1, N_INTERVIEWS + 1):
        acct = bad_account if n == bad else accounts[n - 1]
        files[f"interviews/interview_{n:02d}.md"] = _interview(n, acct, rng, n == bad)
    return files


def memo_files(variant: int, countries: list[str], blocker: str) -> dict[str, str]:
    rng = random.Random(f"{variant}:memos")
    files = {}
    for c in countries:
        if c == blocker:
            body = MEMO_BLOCKED
        else:
            body = rng.choice(MEMO_TEMPLATES_OK).format(n=rng.randint(3, 8))
        text = (f"# Regulatory memo: {c}\n\nRegulator: {MEMO_REGISTER[c]}.\n\n{body}\n")
        files[f"regulatory/{c}.md"] = text
    return files


def document_index(countries: list[str]) -> list[tuple[str, str]]:
    idx = [(f"interviews/interview_{n:02d}.md", "customer interview on price sensitivity")
           for n in range(1, N_INTERVIEWS + 1)]
    idx += [(f"regulatory/{c}.md", f"regulatory memo for {c}") for c in countries]
    return idx


def country_order(crm: list[dict], costs: list[dict], countries: list[str],
                  blocker: str) -> list[str]:
    entry = {r["item"]: float(r["eur_per_year"]) for r in costs}
    ratio = {c: sum(r["country"] == c and r["stage"] in ("lead", "qualified") for r in crm)
             / entry[f"entry_cost_{c}"] for c in countries}
    rest = sorted((c for c in countries if c != blocker), key=lambda c: -ratio[c])
    return rest + [blocker]


def planted_facts(blocker: str, segment: str, competitor: str, delta: int,
                  stem: str) -> list[PlantedFact]:
    b, s, k, m = blocker.lower(), segment.lower(), competitor.lower(), stem.lower()
    return [
        PlantedFact("reg_blocker",
                    f"A mandatory licence in {blocker} cannot be obtained within 18 months.",
                    [[b, "18 month"], [b, "block"], [b, "cannot obtain"],
                     [b, "unobtainable"], [b, "not obtainable"],
                     [b, "cannot be obtained"]]),
        PlantedFact("churn_anomaly",
                    f"The {segment} segment churns far more than the others.",
                    [[s, "churn", x] for x in CHURN_MARKERS]),
        PlantedFact("undercut", f"{competitor} prices about 30% below Lumen.",
                    [[k, "undercut"], [k, "cheaper"], [k, "lower price"],
                     [k, "lowest price"], [k, "underpric"]]),
        PlantedFact("arith_mismatch",
                    f"The hiring summary total differs from the detail by {delta} EUR.",
                    [["hiring", "inconsisten"], ["hiring", "mismatch"],
                     ["hiring", "discrepan"], ["hiring", str(delta)],
                     ["hiring", f"{delta:,}"]]),
        PlantedFact("misleading_quote",
                    f"{stem} claims a 40% price rise is acceptable, contradicting the CRM.",
                    [[m, "contradict"], [m, "misleading"], [m, "inconsisten"],
                     [m, "outlier"]]),
    ]
