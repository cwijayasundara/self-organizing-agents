import csv
import hashlib
import re
from pathlib import Path

import pytest

from agora.dataroom.generate import generate_dataroom
from agora.dataroom.models import GoldKey

COUNTRIES = ["Germany", "France", "Netherlands", "Spain", "Poland"]
SEGMENTS = {"SMB", "Mid-market", "Enterprise"}


def _gen(tmp_path, variant, name=None):
    root = tmp_path / (name or f"v{variant}")
    out = root / "room"
    gold = root / "gold" / "gold.json"
    return generate_dataroom(variant, str(out), str(gold)), out, gold


def _hashes(d: Path) -> dict:
    return {
        p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(d.rglob("*"))
        if p.is_file()
    }


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_same_variant_is_byte_identical(tmp_path):
    _, a, ga = _gen(tmp_path, 3, "a")
    _, b, gb = _gen(tmp_path, 3, "b")
    assert _hashes(a) == _hashes(b)
    assert ga.read_bytes() == gb.read_bytes()
    _, c, _ = _gen(tmp_path, 4, "c")
    assert _hashes(a) != _hashes(c)


def test_gold_inside_dataroom_refused(tmp_path):
    out = tmp_path / "room"
    with pytest.raises(ValueError):
        generate_dataroom(0, str(out), str(out / "sub" / "gold.json"))


def _case_insensitive(tmp_path) -> bool:
    d = tmp_path / "CaseProbe"
    d.mkdir()
    return (tmp_path / "caseprobe").exists()


def test_gold_inside_dataroom_refused_by_case_variant(tmp_path):
    if not _case_insensitive(tmp_path):
        pytest.skip("case-sensitive filesystem")
    out = tmp_path / "room"
    with pytest.raises(ValueError):
        generate_dataroom(0, str(out), str(tmp_path / "ROOM" / "g.json"))


def test_gold_inside_dataroom_refused_by_symlink(tmp_path):
    out = tmp_path / "room"
    out.mkdir()
    link = tmp_path / "link"
    link.symlink_to(out)
    with pytest.raises(ValueError):
        generate_dataroom(0, str(out), str(link / "g.json"))
    assert not (out / "g.json").exists()


def test_countries_and_segments_fixed(tmp_path):
    gold, out, _ = _gen(tmp_path, 1)
    assert gold.countries == COUNTRIES
    rows = _rows(out / "crm_pipeline.csv")
    assert {r["segment"] for r in rows} == SEGMENTS
    assert {r["country"] for r in rows} == set(COUNTRIES)


@pytest.mark.parametrize("variant", range(5))
def test_anomaly_segment_has_triple_churn(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    rates = {}
    for seg in SEGMENTS:
        cust = [r for r in _rows(out / "crm_pipeline.csv")
                if r["segment"] == seg and r["stage"] == "customer"]
        rates[seg] = sum(int(r["churned"]) for r in cust) / len(cust)
    for seg, rate in rates.items():
        if seg != gold.anomaly_segment:
            assert rates[gold.anomaly_segment] >= 2.5 * rate


@pytest.mark.parametrize("variant", range(5))
def test_hiring_summary_mismatch_matches_gold(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    by_country = sum(float(r["eur_per_year"])
                     for r in _rows(out / "hiring_costs_by_country.csv"))
    summary = _rows(out / "hiring_costs_summary.csv")
    total = float(next(r for r in summary if r["country"] == "TOTAL")["total_eur_per_year"])
    assert 20000 <= gold.mismatch_delta_eur <= 120000
    assert abs(total - by_country) == gold.mismatch_delta_eur
    assert gold.mismatch_files == ["hiring_costs_by_country.csv", "hiring_costs_summary.csv"]


@pytest.mark.parametrize("variant", range(5))
def test_undercutter_is_30_percent_below(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    prices = {}
    for line in (out / "competitor_prices.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|", line)
        if m:
            prices[m.group(1)] = float(m.group(2))
    ours = prices.pop("Lumen Analytics")
    assert len(prices) == 4
    below = {n for n, p in prices.items() if p <= 0.7 * ours}
    assert below == {gold.undercutting_competitor}


def test_readme_indexes_existing_files(tmp_path):
    gold, out, gold_path = _gen(tmp_path, 2)
    readme = (out / "README.md").read_text(encoding="utf-8")
    named = re.findall(r"`([A-Za-z0-9_./-]+\.(?:csv|md|txt))`", readme)
    assert named
    for name in named:
        assert (out / name).is_file(), name
    for p in out.rglob("*"):
        if p.is_file():
            assert p.relative_to(out).as_posix() in named
    again = GoldKey.from_json(gold_path.read_text(encoding="utf-8"))
    assert again == gold
    assert GoldKey.from_json(gold.to_json()).to_json() == gold.to_json()
    assert not any(p.name == gold_path.name for p in out.rglob("*"))


def test_no_gold_words_in_dataroom(tmp_path):
    for variant in range(5):
        _, out, _ = _gen(tmp_path, variant)
        for p in out.rglob("*"):
            if p.is_file():
                text = p.read_text(encoding="utf-8").lower()
                for word in ("undercut", "planted", "gold", "blocker",
                          "mismatch", "answer", "anomal"):
                    assert word not in text, (p.name, word)


PHRASE = "we would pay 40% more"
LEAK_WORDS = ("undercut", "planted", "gold", "blocker", "mismatch", "answer", "anomal")
NEW_VARIANTS = [*range(10), 100]


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_twenty_interviews_one_misleading(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    files = sorted((out / "interviews").glob("interview_*.md"))
    assert [f.name for f in files] == [f"interview_{i:02d}.md" for i in range(1, 21)]
    crm = {r["account_id"]: r for r in _rows(out / "crm_pipeline.csv")}
    hits = [f for f in files if PHRASE in f.read_text(encoding="utf-8")]
    assert len(hits) == 1
    assert hits[0].stem == gold.misleading_interview
    assert gold.misleading_interview == f"interview_{(variant * 7) % 20 + 1:02d}"
    for f in files:
        text = f.read_text(encoding="utf-8")
        ids = re.findall(r"A\d{4}", text)
        assert len(ids) == 1 and ids[0] in crm, f.name
        if f in hits:
            assert crm[ids[0]]["stage"] == "customer" and crm[ids[0]]["churned"] == "1"
        else:
            assert "40%" not in text


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_only_blocker_memo_has_blocker_phrase(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    for c in COUNTRIES:
        text = (out / "regulatory" / f"{c}.md").read_text(encoding="utf-8")
        low = text.lower()
        if c == gold.blocker_country:
            assert "licence" in low and "18 months" in low
        else:
            assert "18 months" not in low
        for w in ("blocker", "planted", "gold", "answer"):
            assert w not in low, (c, w)


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_gold_has_five_planted_facts_with_lowercase_detectors(tmp_path, variant):
    gold, _, _ = _gen(tmp_path, variant)
    assert [p.id for p in gold.planted] == [
        "reg_blocker", "churn_anomaly", "undercut", "arith_mismatch", "misleading_quote"]
    for p in gold.planted:
        assert p.description and p.detectors
        for group in p.detectors:
            for s in group:
                assert s == s.lower()
    by_id = {p.id: p.detectors for p in gold.planted}
    b = gold.blocker_country.lower()
    assert by_id["reg_blocker"] == [[b, x] for x in (
        "18 month", "block", "cannot obtain", "unobtainable", "not obtainable",
        "cannot be obtained")] + [[b, "18+"], [b, "18-"]]
    seg = gold.anomaly_segment.lower()
    assert by_id["churn_anomaly"] == [[seg, "churn", x] for x in (
        "higher", "highest", "elevated", "anomal", "spike", "triple",
        "three times", "3x", "outlier", "four times", "4x", "quadruple")]
    comp = gold.undercutting_competitor.lower()
    assert by_id["undercut"] == [[comp, "undercut"], [comp, "cheaper"],
                                 [comp, "lower price"], [comp, "lowest price"],
                                 [comp, "underpric"], [comp, "cheapest"],
                                 [comp, "lower than"]]
    d = int(gold.mismatch_delta_eur)
    assert by_id["arith_mismatch"][-2:] == [["hiring", str(d)], ["hiring", f"{d:,}"]]
    assert by_id["arith_mismatch"][:3] == [["hiring", "inconsisten"],
                                           ["hiring", "mismatch"], ["hiring", "discrepan"]]
    s = gold.misleading_interview
    assert by_id["misleading_quote"] == [[s, "contradict"], [s, "misleading"],
                                         [s, "inconsisten"], [s, "outlier"]]


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_country_order_blocker_last_and_complete(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    order = gold.country_order
    assert sorted(order) == sorted(COUNTRIES)
    assert order[-1] == gold.blocker_country
    crm = _rows(out / "crm_pipeline.csv")
    cost = {r["item"]: float(r["eur_per_year"]) for r in _rows(out / "cost_structure.csv")}
    ratio = {c: sum(r["country"] == c and r["stage"] in ("lead", "qualified") for r in crm)
             / cost[f"entry_cost_{c}"] for c in COUNTRIES}
    rest = order[:-1]
    assert all(ratio[a] >= ratio[b] for a, b in zip(rest, rest[1:]))


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_no_planted_answer_in_dataroom_text(tmp_path, variant):
    gold, out, _ = _gen(tmp_path, variant)
    for p in out.rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8").lower()
            for w in LEAK_WORDS:
                assert w not in text, (p.name, w)
    memo = (out / "regulatory" / f"{gold.blocker_country}.md").read_text(encoding="utf-8")
    assert "blocker" not in memo.lower() and "planted" not in memo.lower()


def test_found_in_per_line_semantics():
    from agora.dataroom.models import PlantedFact
    f = PlantedFact("x", "d", [["poland", "block"]])
    assert not f.found_in("Poland\nblocked")
    assert not f.found_in("")
    assert f.found_in("POLAND is blocked")
    assert f.found_in("a\n\nPoland blocked here")


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_naive_dossier_finds_nothing(tmp_path, variant):
    gold, _, _ = _gen(tmp_path, variant)
    naive = (f"All five markets ({', '.join(COUNTRIES)}) require a data-processing "
             f"licence.\nChurn by segment: SMB, Mid-market, Enterprise reviewed.\n"
             f"Competitors Notiva, Veridia, Quanta Metrics, Brightline price below or "
             f"near Lumen. {gold.undercutting_competitor} {gold.blocker_country} "
             f"{gold.anomaly_segment}\n")
    by_id = {p.id: p for p in gold.planted}
    for k in ("reg_blocker", "churn_anomaly", "undercut"):
        assert not by_id[k].found_in(naive), k


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_positive_texts_match(tmp_path, variant):
    gold, _, _ = _gen(tmp_path, variant)
    d = int(gold.mismatch_delta_eur)
    sentences = {
        "reg_blocker": f"{gold.blocker_country}: the mandatory licence cannot be "
                       f"obtained within 18 months",
        "churn_anomaly": f"{gold.anomaly_segment} churn is three times higher than "
                         f"other segments",
        "undercut": f"{gold.undercutting_competitor} is cheaper than Lumen",
        "arith_mismatch": f"the hiring summary total is inconsistent with the "
                          f"by-country rows (off by {d:,})",
        "misleading_quote": f"{gold.misleading_interview} is misleading: it "
                            f"contradicts the CRM",
    }
    for fid, sent in sentences.items():
        for p in gold.planted:
            assert p.found_in(sent) == (p.id == fid), (fid, p.id)


@pytest.mark.parametrize("variant", NEW_VARIANTS)
def test_new_detector_phrasings_match_only_their_fact(tmp_path, variant):
    gold, _, _ = _gen(tmp_path, variant)
    sentences = {
        "churn_anomaly": f"{gold.anomaly_segment} churn is 4x the other segments",
        "reg_blocker": f"{gold.blocker_country}: the licence takes 18+ months",
        "undercut": f"{gold.undercutting_competitor} is the cheapest option",
    }
    for fid, sent in sentences.items():
        for p in gold.planted:
            assert p.found_in(sent) == (p.id == fid), (fid, p.id)
    for sent in (f"{gold.anomaly_segment} churn is four times the rest",
                 f"{gold.anomaly_segment} churn is quadruple the rest"):
        assert {p.id for p in gold.planted if p.found_in(sent)} == {"churn_anomaly"}
    assert {p.id for p in gold.planted if p.found_in(
        f"{gold.blocker_country} takes 18- months")} == {"reg_blocker"}
    assert {p.id for p in gold.planted if p.found_in(
        f"{gold.undercutting_competitor} is lower than Lumen")} == {"undercut"}
