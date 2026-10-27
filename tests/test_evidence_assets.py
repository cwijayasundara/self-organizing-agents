import csv
import json
import re
from pathlib import Path

import pytest
import yaml

from agora.config import load_roster
from agora.domain import (
    RESEARCH_SUMMARY_KEYS, _resolves, build_domain, extract_citations, parse_research_summary,
    research_summary_block,
)
from agora.ledger.types import Artifact, Task
from agora.templates import load_template

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "evidence_review"
ROOM = EX / "sources"
GOLD = json.loads((EX / "gold.json").read_text())
FORBIDDEN = ["retracted", "inflated", "40%", "72,000", "72000", "Customer Support", "okafor", "flexweek"]


def _summary(**over):
    return {**GOLD, **over}


def _block(obj) -> str:
    return "Memo text.\n\nRESEARCH_SUMMARY\n```json\n" + json.dumps(obj) + "\n```\n"


def test_template_is_four_leaves_and_one_integration():
    specs = {s.id: s for s in load_template(str(EX / "template.yaml"))}
    leaves = ["productivity", "wellbeing_retention", "cost_ops", "source_quality"]
    assert list(specs) == leaves + ["synthesis"]
    for i in leaves:
        assert list(specs[i].deps) == [] and specs[i].kind == "work"
    assert specs["synthesis"].kind == "integration"
    assert set(specs["synthesis"].deps) == set(leaves)
    for s in specs.values():
        assert 3 <= len(s.acceptance) <= 4


def test_roster_has_one_peer_per_leaf_and_two_families():
    r = load_roster(str(EX / "roster.yaml"))
    assert len(r.peers) == 4
    fams = [r.models[p.model].family for p in r.peers]
    assert sorted(fams) == ["deepseek", "deepseek", "zhipu", "zhipu"]
    assert Path(ROOT / r.data_dir).resolve() == ROOM.resolve()
    assert r.budget.wall_clock_s <= 600 and r.budget.stagger_s <= 5


def test_readme_lists_every_file_and_nothing_else():
    listed = set(re.findall(r"^- `([^`]+)`", (ROOM / "README.md").read_text(), re.M))
    present = {str(p.relative_to(ROOM)) for p in ROOM.rglob("*") if p.is_file()}
    assert listed == present


def test_gold_is_outside_room_and_matches_evidence():
    assert not (EX / "gold.json").resolve().is_relative_to(ROOM.resolve())
    assert not any(p.name.startswith("gold") for p in ROOM.rglob("*"))
    assert parse_research_summary(_block(GOLD)) == GOLD
    for k in ("retracted_source", "inflated_claim_source"):
        assert _resolves(str(ROOM), GOLD[k])
    assert "Okafor" in (ROOM / "retraction_notices.md").read_text()
    rows = list(csv.DictReader((ROOM / "cost_model.csv").open()))
    items = sum(int(r["annual_cost_eur"]) for r in rows if r["line_item"] != "TOTAL")
    total = next(int(r["annual_cost_eur"]) for r in rows if r["line_item"] == "TOTAL")
    assert items - total == GOLD["cost_mismatch_eur"]
    survey = {r["department"]: r for r in csv.DictReader((ROOM / "staff_survey.csv").open())}
    assert sum(int(r["headcount"]) for r in survey.values()) == 600
    assert GOLD["harmed_group"] in survey


def test_brief_and_template_do_not_leak_answers():
    for name in ("brief.md", "template.yaml"):
        text = (EX / name).read_text()
        for k in RESEARCH_SUMMARY_KEYS:
            text = text.replace(k, "")
        low = text.lower()
        for w in FORBIDDEN:
            assert w.lower() not in low, (name, w)
    brief = (EX / "brief.md").read_text()
    for k in RESEARCH_SUMMARY_KEYS:
        assert k in brief
    assert "RESEARCH_SUMMARY" in brief and "/data/" in brief
    assert parse_research_summary(brief) is None


def test_example_citations_resolve():
    for name in ("brief.md", "template.yaml"):
        for c in extract_citations((EX / name).read_text()):
            assert _resolves(str(ROOM), c), (name, c)


def test_word_limits_agree():
    brief = (EX / "brief.md").read_text()
    synth = yaml.safe_load((EX / "template.yaml").read_text())["tasks"][-1]
    assert re.search(r"memo under (\d+) words", brief).group(1) == "450"
    assert "under 450 words" in synth["output_format"]


@pytest.mark.parametrize("bad", [
    {"verdict": "maybe"},
    {"cost_mismatch_eur": "72000"},
    {"cost_mismatch_eur": True},
    {"harmed_group": ""},
    {"retracted_source": None},
])
def test_research_summary_rejects_invalid_fields(bad):
    assert parse_research_summary(_block(_summary(**bad))) is None


def test_research_summary_parsing_edge_cases():
    missing = dict(GOLD)
    del missing["verdict"]
    assert parse_research_summary(_block(missing)) is None
    assert parse_research_summary(_block(GOLD).replace("RESEARCH_SUMMARY", "DOSSIER_SUMMARY")) is None
    assert parse_research_summary(_block(_summary(cost_mismatch_eur=72000.0)))["cost_mismatch_eur"] == 72000.0
    assert parse_research_summary("RESEARCH_SUMMARY\n" + json.dumps(GOLD)) == GOLD
    assert parse_research_summary("") is None


def _task(tid: str, kind: str = "integration") -> Task:
    return Task(id=tid, title="t", objective="o", output_format="f", acceptance=[], deps=[],
                required=True, kind=kind, status="claimed", owner="R1", owner_family="x",
                lease_until=None, review_of=None, author_family=None, artifact_id=None, version=1)


def _artifact(tid: str, content: str) -> Artifact:
    return Artifact(id=f"{tid}@v1", task_id=tid, author="R1", version=1, content=content, created_at=0.0)


def test_research_summary_block_validator_only_checks_synthesis():
    check = research_summary_block()
    assert check(_task("synthesis"), _artifact("synthesis", _block(GOLD))) == []
    assert check(_task("synthesis"), _artifact("synthesis", "no block")) == [
        "research_summary_block: missing or invalid RESEARCH_SUMMARY block"]
    assert check(_task("productivity", "work"), _artifact("productivity", "no block")) == []


def test_build_domain_evidence_review():
    validators, admissions = build_domain("evidence_review", str(ROOM))
    assert len(validators) == 3 and len(admissions) == 1
    ok = "x" * 200 + " [staff_survey.csv]\n" + _block(GOLD)
    assert all(v(_task("synthesis"), _artifact("synthesis", ok)) == [] for v in validators)
    assert admissions[0]("R1", "FACT", "retraction", "[retraction_notices.md]") == []
    assert admissions[0]("R1", "FACT", "retraction", "no citation") != []


def test_validator_names_the_offending_field():
    check = research_summary_block()
    msg = check(_task("synthesis"), _artifact("synthesis", _block(_summary(cost_mismatch_eur="72000"))))
    assert len(msg) == 1
    assert "cost_mismatch_eur must be a JSON number without quotes" in msg[0] and '"72000"' in msg[0]
    msg = check(_task("synthesis"), _artifact("synthesis", _block(_summary(verdict="maybe"))))
    assert "verdict must be one of" in msg[0]
    missing = {k: v for k, v in GOLD.items() if k != "harmed_group"}
    assert "missing key harmed_group" in check(_task("synthesis"), _artifact("synthesis", _block(missing)))[0]


def test_briefs_show_the_number_field_unquoted():
    for path, key in ((EX / "brief.md", "cost_mismatch_eur"),
                      (ROOT / "examples" / "eu_market_entry" / "brief.md", "arith_mismatch_eur")):
        text = path.read_text()
        assert f'"{key}": <number>' in text and "no quotes" in text
