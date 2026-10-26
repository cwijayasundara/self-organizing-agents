import json

import pytest

from agora.dataroom.generate import generate_dataroom
from agora.dataroom.models import GoldKey, PlantedFact
from agora.eval.scoring import Scores, score_dossier

ORDER = ["France", "Germany", "Netherlands", "Spain", "Poland"]


def _gold() -> GoldKey:
    return GoldKey(
        variant=0, countries=sorted(ORDER), blocker_country="Poland",
        anomaly_segment="SMB", undercutting_competitor="Notiva",
        mismatch_delta_eur=12000.0, mismatch_files=["a.csv", "b.csv"],
        misleading_interview="interview_07.md", country_order=ORDER,
        planted=[
            PlantedFact("reg_blocker", "d", [["poland", "licen"], ["poland", "block"]]),
            PlantedFact("churn_anomaly", "d", [["smb", "churn", "higher"]]),
            PlantedFact("undercut", "d", [["notiva", "cheaper"], ["notiva", "below"]]),
            PlantedFact("arith_mismatch", "d", [["summary", "inconsistent"]]),
            PlantedFact("misleading_quote", "d", [["interview_07", "contradict"]]),
        ])


FACT_LINES = [
    "Poland: the mandatory licence cannot be obtained in time.",
    "SMB churn is far higher than in other segments.",
    "Notiva is cheaper than Lumen.",
    "The hiring summary is inconsistent with the by-country rows.",
    "interview_07 is misleading: it contradicts the CRM.",
]


def _summary(**over) -> str:
    d = {"recommendation": "hold", "country_order": ORDER, "blocker_country": "Poland",
         "anomaly_segment": "SMB", "undercutting_competitor": "Notiva",
         "arith_mismatch_eur": 12000}
    d.update(over)
    return "DOSSIER_SUMMARY\n```json\n" + json.dumps(d) + "\n```\n"


def test_all_planted_facts_found():
    s = score_dossier("\n".join(FACT_LINES), _gold(), "/nonexistent")
    assert isinstance(s, Scores)
    assert s.recall == 1.0 and s.missed == []
    assert s.found == [p.id for p in _gold().planted]


def test_country_without_licence_not_found():
    s = score_dossier("Poland is a large market with strong demand.", _gold(), "/x")
    assert "reg_blocker" in s.missed and s.recall == 0.0


def test_facts_need_same_line():
    s = score_dossier("Poland\nlicence\nSMB churn\nhigher", _gold(), "/x")
    assert s.recall == 0.0


def test_case_insensitive():
    s = score_dossier("\n".join(l.upper() for l in FACT_LINES), _gold(), "/x")
    assert s.recall == 1.0


def test_recall_fraction_and_order():
    s = score_dossier(FACT_LINES[2] + "\n" + FACT_LINES[0], _gold(), "/x")
    assert s.recall == pytest.approx(0.4)
    assert s.found == ["reg_blocker", "undercut"]
    assert s.missed == ["churn_anomaly", "arith_mismatch", "misleading_quote"]


@pytest.mark.parametrize("variant", [0, 1, 2])
def test_real_gold_positive_and_naive(tmp_path, variant):
    gold = generate_dataroom(variant, str(tmp_path / "room"), str(tmp_path / "g" / "gold.json"))
    d = int(gold.mismatch_delta_eur)
    text = "\n".join([
        f"{gold.blocker_country}: the mandatory licence cannot be obtained within 18 months",
        f"{gold.anomaly_segment} churn is three times higher than other segments",
        f"{gold.undercutting_competitor} is cheaper than Lumen",
        f"the hiring summary total is inconsistent with the by-country rows (off by {d:,})",
        f"{gold.misleading_interview} is misleading: it contradicts the CRM",
    ])
    s = score_dossier(text, gold, str(tmp_path / "room"))
    assert s.recall == 1.0, s.missed
    assert score_dossier("Nothing to report.", gold, str(tmp_path / "room")).recall == 0.0


@pytest.mark.parametrize("key,bad", [
    ("blocker_country", "France"),
    ("anomaly_segment", "Enterprise"),
    ("undercutting_competitor", "Veridia"),
    ("country_order", list(reversed(ORDER))),
    ("arith_mismatch_eur", 99999),
])
def test_summary_accuracy_each_key(key, bad):
    ok = score_dossier(_summary(), _gold(), "/x")
    assert ok.summary_present and ok.summary_accuracy == 1.0
    s = score_dossier(_summary(**{key: bad}), _gold(), "/x")
    assert s.summary_accuracy == pytest.approx(0.8)


def test_summary_case_insensitive_and_stripped():
    s = score_dossier(_summary(blocker_country=" poland ", anomaly_segment="smb"), _gold(), "/x")
    assert s.summary_accuracy == 1.0


def test_country_order_checks_first_and_last_only():
    mid = [ORDER[0], ORDER[3], ORDER[2], ORDER[1], ORDER[4]]
    assert score_dossier(_summary(country_order=mid), _gold(), "/x").summary_accuracy == 1.0
    swapped_end = [ORDER[0], ORDER[1], ORDER[2], ORDER[4], ORDER[3]]
    assert score_dossier(_summary(country_order=swapped_end), _gold(), "/x").summary_accuracy == pytest.approx(0.8)


def test_mismatch_tolerance():
    assert score_dossier(_summary(arith_mismatch_eur=12000.5), _gold(), "/x").summary_accuracy == 1.0
    assert score_dossier(_summary(arith_mismatch_eur=12002), _gold(), "/x").summary_accuracy == pytest.approx(0.8)


def test_missing_summary_block():
    s = score_dossier("just prose", _gold(), "/x")
    assert not s.summary_present and s.summary_accuracy == 0.0


def test_invalid_summary_block():
    bad = 'DOSSIER_SUMMARY\n```json\n{"recommendation": "hold", "blocker_country": "Poland"}\n```\n'
    s = score_dossier(bad, _gold(), "/x")
    assert not s.summary_present and s.summary_accuracy == 0.0


def test_citation_validity_counts_existing_files(tmp_path):
    gold = generate_dataroom(0, str(tmp_path / "room"), str(tmp_path / "g" / "gold.json"))
    files = sorted(p.name for p in (tmp_path / "room").iterdir() if p.suffix in (".csv", ".md"))
    text = f"A [{files[0]}] B [{files[0]}:3] C [missing_file.csv] D [../etc.md]\n"
    s = score_dossier(text, gold, str(tmp_path / "room"))
    assert s.citations == 4
    assert s.citation_validity == pytest.approx(0.5)


def test_no_citations_scores_zero():
    s = score_dossier("no cites here", _gold(), "/x")
    assert s.citations == 0 and s.citation_validity == 0.0


@pytest.mark.parametrize("text", [
    "", "a" * (5 * 1024 * 1024), "x\x00y\x00\n" * 1000, "[" * (1024 * 1024),
    "DOSSIER_SUMMARY\n" * 5000, "�\x01\x02" * 1000,
])
def test_never_raises_on_garbage(text):
    s = score_dossier(text, _gold(), "/nonexistent")
    assert 0.0 <= s.recall <= 1.0 and 0.0 <= s.summary_accuracy <= 1.0
    assert 0.0 <= s.citation_validity <= 1.0


@pytest.mark.parametrize("dets", [[[""]], [[]], [["", "x"]]])
def test_found_in_ignores_empty_detector_groups(dets):
    assert not PlantedFact("f", "d", dets).found_in("anything at all\nx")
