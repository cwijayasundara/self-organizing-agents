import json
import os
import time

import pytest

from agora.config import ConfigError
from agora.domain import (
    SUMMARY_KEYS, build_domain, citations_resolve, dossier_summary_block,
    extract_citations, fact_citation_admission, parse_dossier_summary,
)
from agora.ledger.types import Artifact, Task


def _task(tid="T", kind="work"):
    return Task(id=tid, title="t", objective="o", output_format="f", acceptance=[], deps=[],
                required=True, kind=kind, status="claimed", owner="P01", owner_family="x",
                lease_until=None, review_of=None, author_family=None, artifact_id=None, version=1)


def _art(text, tid="T"):
    return Artifact(id="a1", task_id=tid, author="P01", version=1, content=text, created_at=0.0)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    (d / "interviews").mkdir(parents=True)
    (d / "crm_pipeline.csv").write_text("a,b\n1,2\n")
    (d / "interviews" / "interview_07.md").write_text("hi")
    (tmp_path / "secret.md").write_text("s")
    return str(d)


def _summary(**over):
    s = {"recommendation": "enter", "country_order": ["DE", "FR", "NL", "ES", "IT"],
         "blocker_country": "FR", "anomaly_segment": "smb", "undercutting_competitor": "Acme",
         "arith_mismatch_eur": 1200}
    s.update(over)
    return s


def _block(s, fence="```json"):
    return "DOSSIER_SUMMARY\n\n" + fence + "\n" + json.dumps(s) + "\n```\n"


def test_extract_citations():
    text = ("See [interviews/interview_07.md] and [crm_pipeline.csv:rows 1-40], "
            "[x] [see below] again [crm_pipeline.csv].")
    assert extract_citations(text) == ["interviews/interview_07.md", "crm_pipeline.csv", "crm_pipeline.csv"]


def test_citations_resolve_accepts_existing_files(data_dir):
    v = citations_resolve(data_dir)
    assert v(_task(), _art("x [crm_pipeline.csv:rows 1-3] [interviews/interview_07.md]")) == []
    assert v(_task(kind="integration"), _art("[crm_pipeline.csv]")) == []


def test_citations_reject_missing_traversal_and_absolute(data_dir):
    v = citations_resolve(data_dir)
    for bad in ("[nope.csv]", "[../secret.md]", "[/etc/passwd.md]", "[interviews/../../secret.md]"):
        errs = v(_task(), _art("ok [crm_pipeline.csv] " + bad))
        assert errs and all(e.startswith("citations_resolve:") for e in errs)
        assert bad.strip("[]") in errs[0]
    # a directory is not a file
    assert v(_task(), _art("[interviews.md]"))


def test_symlink_escape_rejected(data_dir, tmp_path):
    try:
        os.symlink(str(tmp_path / "secret.md"), os.path.join(data_dir, "link.md"))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported")
    errs = citations_resolve(data_dir)(_task(), _art("[link.md]"))
    assert errs and "link.md" in errs[0]


def test_min_citations_enforced(data_dir):
    v = citations_resolve(data_dir, min_citations=2)
    assert v(_task(), _art("[crm_pipeline.csv]")) == [
        "citations_resolve: needs at least 2 data-room citations, found 1"]
    assert v(_task(), _art("[crm_pipeline.csv] [interviews/interview_07.md]")) == []


def test_validator_skips_review_tasks(data_dir):
    assert citations_resolve(data_dir)(_task(kind="review"), _art("no cites")) == []


def test_fact_admission_requires_detail_citation(data_dir):
    adm = fact_citation_admission(data_dir)
    msg = "FACT needs a data-room citation in detail"
    assert adm("P01", "FACT", "t", None) == [msg]
    assert adm("P01", "FACT", "t", "no cite") == [msg]
    assert adm("P01", "FACT", "t", "[nope.csv]") == [msg]
    assert adm("P01", "FACT", "t", "[../secret.md]") == [msg]
    assert adm("P01", "FACT", "t", "[crm_pipeline.csv:rows 2]") == []


def test_fact_admission_ignores_other_types(data_dir):
    adm = fact_citation_admission(data_dir)
    for t in ("OBSERVED", "FAIL", "CLAIM", "DECISION"):
        assert adm("P01", t, "t", None) == []


def test_parse_summary_valid():
    s = _summary()
    assert parse_dossier_summary("intro\n  DOSSIER_SUMMARY  \n\n\n" + "```json\n" + json.dumps(s) + "\n```") == s
    assert parse_dossier_summary(_block(s, "```")) == s
    assert set(SUMMARY_KEYS) <= set(s)
    assert parse_dossier_summary(_block(_summary(arith_mismatch_eur=1.5)))["arith_mismatch_eur"] == 1.5


def test_parse_summary_rejects_missing_key_wrong_order_length_and_bad_json():
    s = _summary()
    missing = {k: v for k, v in s.items() if k != "blocker_country"}
    assert parse_dossier_summary(_block(missing)) is None
    assert parse_dossier_summary(_block(_summary(country_order=["DE"] * 4))) is None
    assert parse_dossier_summary(_block(_summary(country_order=["DE"] * 6))) is None
    assert parse_dossier_summary(_block(_summary(country_order=["DE", "FR", "NL", "ES", 5]))) is None
    assert parse_dossier_summary(_block(_summary(country_order="DE,FR,NL,ES,IT"))) is None
    assert parse_dossier_summary(_block(_summary(recommendation="maybe"))) is None
    assert parse_dossier_summary(_block(_summary(arith_mismatch_eur="12"))) is None
    assert parse_dossier_summary("DOSSIER_SUMMARY\n```json\n{not json\n```") is None
    assert parse_dossier_summary("DOSSIER_SUMMARY\n```json\n[1]\n```") is None
    # block before the marker line does not count; marker must be followed by the fence
    assert parse_dossier_summary("```json\n" + json.dumps(s) + "\n```\nDOSSIER_SUMMARY\ntext") is None
    assert parse_dossier_summary("") is None


def test_last_valid_block_wins():
    a, b = _summary(blocker_country="AA"), _summary(blocker_country="BB")
    text = _block(a) + "\n" + _block(b) + "\nDOSSIER_SUMMARY\n```json\n{bad\n```\n"
    assert parse_dossier_summary(text)["blocker_country"] == "BB"


def test_booleans_rejected_for_arith_mismatch():
    assert parse_dossier_summary(_block(_summary(arith_mismatch_eur=True))) is None
    assert parse_dossier_summary(_block(_summary(arith_mismatch_eur=False))) is None


def test_dossier_summary_block_only_for_dossier_task():
    v = dossier_summary_block()
    assert v(_task("other"), _art("nothing")) == []
    assert v(_task("dossier"), _art("nothing")) == [
        "dossier_summary_block: missing or invalid DOSSIER_SUMMARY block"]
    assert v(_task("dossier"), _art(_block(_summary()))) == []


def test_build_domain_registry_and_unknown_name(data_dir):
    validators, admissions = build_domain("eu_market_entry", data_dir)
    assert len(validators) == 3 and len(admissions) == 1
    errs = [e for v in validators for e in v(_task("dossier"), _art("short"))]
    assert any(e.startswith("non_empty:") for e in errs)
    assert any(e.startswith("citations_resolve:") for e in errs)
    assert any(e.startswith("dossier_summary_block:") for e in errs)
    with pytest.raises(ConfigError, match="eu_market_entry"):
        build_domain("nope", data_dir)


def test_pathological_and_garbage_input_is_fast_and_never_raises(data_dir):
    v = citations_resolve(data_dir)
    t0 = time.time()
    for text in ("[" * 1_000_000, "[a" * 500_000, "[" + "a" * 1_000_000, "DOSSIER_SUMMARY\n" * 100_000,
                 "\x00\ud800[‮.md]", "[a\x00b.md]", "[" + "../" * 100_000 + "x.md]"):
        assert isinstance(v(_task(), _art(text)), list)
        parse_dossier_summary(text)
        assert isinstance(dossier_summary_block()(_task("dossier"), _art(text)), list)
        assert isinstance(fact_citation_admission(data_dir)("P", "FACT", "t", text), list)
    assert time.time() - t0 < 1.0
