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
                for word in ("undercut", "planted", "gold"):
                    assert word not in text, (p.name, word)
