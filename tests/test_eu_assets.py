import importlib.util
import json
import re
from pathlib import Path

import pytest

from agora import api, cli
from agora.config import ConfigError, load_roster
from agora.dataroom.generate import generate_dataroom
from agora.runner import RunResult
from agora.done import DoneStatus
from agora.templates import load_template
from fakes import ScriptedChatModel

ROOT = Path(__file__).resolve().parent.parent
EU = ROOT / "examples" / "eu_market_entry"
SUMMARY_KEYS = ["recommendation", "country_order", "blocker_country", "anomaly_segment",
                "undercutting_competitor", "arith_mismatch_eur"]
FORBIDDEN = ["planted", "gold", "undercut", "mismatch", "anomal", "blocker"]


def _script():
    spec = importlib.util.spec_from_file_location("make_dataroom", ROOT / "scripts" / "make_dataroom.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_template_loads_with_expected_dag():
    specs = {s.id: s for s in load_template(str(EU / "template.yaml"))}
    assert len(specs) == 12
    base = ["sizing", "competitors", "pricing", "gtm", "customer_evidence", "regulatory", "ops_cost"]
    for i in base:
        assert list(specs[i].deps) == []
    assert set(specs["country_sequence"].deps) == {"sizing", "regulatory", "ops_cost"}
    assert set(specs["pnl_3yr"].deps) == {"sizing", "pricing", "gtm", "ops_cost"}
    assert set(specs["risk_register"].deps) == {"regulatory", "competitors", "customer_evidence"}
    assert set(specs["recommendation"].deps) == {"country_sequence", "pnl_3yr", "risk_register"}
    integ = [s for s in specs.values() if s.kind == "integration"]
    assert [s.id for s in integ] == ["dossier"]
    assert set(specs["dossier"].deps) == set(specs) - {"dossier"}
    for s in specs.values():
        assert 3 <= len(s.acceptance) <= 4


def test_roster_loads_two_families_ten_peers():
    r = load_roster(str(EU / "roster.yaml"))
    assert [p.id for p in r.peers] == [f"P{i:02d}" for i in range(1, 11)]
    assert {m.family for m in r.models.values()} == {"deepseek", "zhipu"}
    assert r.data_dir == "data/eu/v0"


@pytest.mark.parametrize("variant", range(5))
def test_brief_has_summary_format_and_no_answers(tmp_path, variant):
    gold = generate_dataroom(variant, str(tmp_path / "room"), str(tmp_path / "gold.json"))
    for name in ("brief.md", "template.yaml"):
        text = (EU / name).read_text()
        for k in SUMMARY_KEYS:
            text = text.replace(k, "")
        low = text.lower()
        for w in FORBIDDEN:
            assert w not in low, (name, w)
        for c in ("Notiva", "Veridia", "Quanta Metrics", "Brightline"):
            assert c.lower() not in low
        assert gold.undercutting_competitor.lower() not in low
        assert str(int(gold.mismatch_delta_eur)) not in text
    brief = (EU / "brief.md").read_text()
    assert "DOSSIER_SUMMARY" in brief
    for k in SUMMARY_KEYS:
        assert k in brief
    assert "relative to the data-room root" in brief
    assert "/data/" in brief
    assert "## How to work with the evidence" in brief
    from agora.domain import parse_dossier_summary
    assert parse_dossier_summary(brief) is None


def test_template_criteria_are_neutral():
    import yaml
    for t in yaml.safe_load((EU / "template.yaml").read_text())["tasks"]:
        for text in [t["objective"], *t["acceptance"]]:
            assert not ("hiring_costs_by_country" in text and "hiring_costs_summary" in text), t["id"]
            assert not ("interview" in text and "crm_pipeline" in text), t["id"]
            assert not ("segment" in text.lower() and "churn" in text.lower()), t["id"]


def test_example_citations_resolve(tmp_path):
    from agora.domain import extract_citations, _resolves
    generate_dataroom(0, str(tmp_path / "room"), str(tmp_path / "gold.json"))
    for name in ("brief.md", "template.yaml"):
        for c in extract_citations((EU / name).read_text()):
            assert _resolves(str(tmp_path / "room"), c), (name, c)


def test_make_dataroom_script(tmp_path, capsys):
    mod = _script()
    out, gold_p = tmp_path / "room", tmp_path / "keys" / "gold.json"
    assert mod.main(["--variant", "2", "--out", str(out), "--gold", str(gold_p)]) == 0
    printed = capsys.readouterr().out
    gold = json.loads(gold_p.read_text())
    assert not gold_p.resolve().is_relative_to(out.resolve())
    assert (out / "README.md").exists()
    n = len([p for p in out.rglob("*") if p.is_file()])
    assert str(n) in printed and str(out) in printed
    for v in (gold["undercutting_competitor"], gold["blocker_country"], gold["anomaly_segment"],
              str(int(gold["mismatch_delta_eur"]))):
        assert v not in printed
    for c in ("Notiva", "Veridia", "Quanta Metrics", "Brightline"):
        assert c not in printed


def test_make_dataroom_script_refuses_gold_in_room(tmp_path, capsys):
    mod = _script()
    out = tmp_path / "room"
    assert mod.main(["--variant", "1", "--out", str(out), "--gold", str(out / "gold.json")]) == 1
    cap = capsys.readouterr()
    assert cap.err.startswith("error:") and cap.err.count("\n") == 1
    assert cap.out == ""


ROSTER = """
run_name: clitest
models:
  a: {{provider: fireworks, id: x/a, family: fa, price: {{in_per_m: 1, cached_per_m: 0.1, out_per_m: 1}}}}
  b: {{provider: fireworks, id: x/b, family: fb, price: {{in_per_m: 1, cached_per_m: 0.1, out_per_m: 1}}}}
peers:
  - {{id: A01, model: a}}
  - {{id: B01, model: b}}
budget: {{swarm_usd: 1, peer_usd: 0.5, wall_clock_s: 2, stall_after_s: 1000}}
{extra}
"""
TEMPLATE = """
tasks:
  - id: summary
    title: Summary
    objective: summarise
    output_format: markdown
    acceptance: [one, two, three]
    deps: []
    kind: integration
"""


def _args(tmp_path, extra="", domain="eu_market_entry"):
    (tmp_path / "roster.yaml").write_text(ROSTER.format(extra=extra))
    (tmp_path / "template.yaml").write_text(TEMPLATE)
    (tmp_path / "brief.md").write_text("Brief.")
    a = ["run", "--roster", str(tmp_path / "roster.yaml"), "--template", str(tmp_path / "template.yaml"),
         "--brief", str(tmp_path / "brief.md"), "--db", str(tmp_path / "x.sqlite"), "--run-id", "t1"]
    return a + (["--domain", domain] if domain else [])


def test_cli_domain_flag_requires_data_dir(tmp_path, capsys):
    assert cli.main(_args(tmp_path)) == 1
    assert "error: --domain needs a roster with data_dir" in capsys.readouterr().err


def test_cli_domain_missing_data_dir_path(tmp_path, capsys):
    assert cli.main(_args(tmp_path, extra=f"data_dir: {tmp_path / 'nope'}")) == 1
    err = capsys.readouterr().err
    assert "does not exist (run scripts/make_dataroom.py first)" in err
    assert not (tmp_path / "x.sqlite").exists()


def test_cli_domain_flag_wires_validators(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(api, "build_model", lambda spec: ScriptedChatModel())
    seen = {}
    vals, adm = ["V"], ["A"]

    def fake_build(name, data_dir):
        seen["b"] = (name, data_dir)
        return vals, adm

    real = cli.run_swarm

    def spy(roster, specs, brief, db, **kw):
        seen["kw"] = kw
        return real(roster, specs, brief, db, **{**kw, "validators": [], "admission": []})

    monkeypatch.setattr(cli, "build_domain", fake_build)
    monkeypatch.setattr(cli, "run_swarm", spy)
    (tmp_path / "some" / "dir").mkdir(parents=True)
    cli.main(_args(tmp_path, extra=f"data_dir: {tmp_path / 'some' / 'dir'}"))
    assert seen["b"] == ("eu_market_entry", str(tmp_path / "some" / "dir"))
    assert seen["kw"]["validators"] == vals and seen["kw"]["admission"] == adm


def test_cli_domain_unknown_name_exit_1(tmp_path, capsys):
    assert cli.main(_args(tmp_path, extra="data_dir: .", domain="nope")) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_brief_limit_matches_template_and_no_answer_like_citations():
    import re
    from agora.domain import extract_citations
    brief = (EU / "brief.md").read_text()
    assert "Keep the final dossier under 700 words (the DOSSIER_SUMMARY block does not count)." in brief
    tpl = (EU / "template.yaml").read_text()
    dossier = tpl[tpl.index("id: dossier"):]
    nb = re.search(r"dossier under (\d+) words", brief).group(1)
    nt = re.search(r"dossier, under (\d+) words", dossier).group(1)
    assert nb == nt == "700"
    for c in extract_citations(brief):
        assert not c.startswith(("interviews/", "regulatory/")), c
    assert "interviews/" not in brief and "regulatory/Poland" not in brief
