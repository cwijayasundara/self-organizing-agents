import json

import pytest

from agora import cli
from agora.config import load_roster
from agora.runner import RunResult
from agora.done import DoneStatus
from agora.templates import load_template
from fakes import ScriptedChatModel

ROSTER = """
run_name: clitest
models:
  a: {{provider: fireworks, id: x/a, family: fa, price: {{in_per_m: 1, cached_per_m: 0.1, out_per_m: 1}}}}
  b: {{provider: fireworks, id: x/b, family: fb, price: {{in_per_m: 1, cached_per_m: 0.1, out_per_m: 1}}}}
  unused: {{provider: openai, id: x/c, family: fc, reasoning_effort: none, price: {{in_per_m: 1, cached_per_m: 0.1, out_per_m: 1}}}}
peers:
  - {{id: A01, model: a}}
  - {{id: B01, model: b}}
budget: {{swarm_usd: 1, peer_usd: 0.5, wall_clock_s: {wall}, stall_after_s: 1000}}
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


def write(tmp_path, wall=2):
    (tmp_path / "roster.yaml").write_text(ROSTER.format(wall=wall))
    (tmp_path / "template.yaml").write_text(TEMPLATE)
    (tmp_path / "brief.md").write_text("Brief text.")
    return [
        "run", "--roster", str(tmp_path / "roster.yaml"), "--template", str(tmp_path / "template.yaml"),
        "--brief", str(tmp_path / "brief.md"), "--db", str(tmp_path / "x.sqlite"), "--run-id", "t1",
    ]


def test_cli_offline(tmp_path, monkeypatch, capsys):
    built = []
    monkeypatch.setattr(cli, "build_model", lambda spec: built.append(spec.key) or ScriptedChatModel())
    code = cli.main(write(tmp_path))
    out = capsys.readouterr().out
    assert code == 3
    assert json.loads(out.split("\n\n")[0])["status"] == "timeout"
    assert "summary" in out
    assert sorted(built) == ["a", "b"]  # the unused model is never built


@pytest.mark.parametrize("status,code", [("done", 0), ("budget", 2), ("timeout", 3), ("stalled", 4)])
def test_exit_codes(tmp_path, monkeypatch, capsys, status, code):
    monkeypatch.setattr(cli, "build_model", lambda spec: ScriptedChatModel())

    async def fake_run(self):
        return RunResult(status, 0.5, 1.0, DoneStatus(status == "done", []), {"A01": 1}, [])

    monkeypatch.setattr(cli.SwarmRunner, "run", fake_run)
    assert cli.main(write(tmp_path)) == code
    assert json.loads(capsys.readouterr().out.split("\n\n")[0])["status"] == status


def test_config_error(tmp_path, capsys):
    args = write(tmp_path)
    (tmp_path / "template.yaml").write_text("tasks: []")
    assert cli.main(args) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_malformed_yaml(tmp_path, capsys):
    args = write(tmp_path)
    (tmp_path / "roster.yaml").write_text("a: [unclosed")
    assert cli.main(args) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_missing_file(tmp_path, capsys):
    args = write(tmp_path)
    (tmp_path / "brief.md").unlink()
    assert cli.main(args) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_missing_api_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    assert cli.main(write(tmp_path)) == 1
    err = capsys.readouterr().err
    assert err.startswith("error:") and "FIREWORKS_API_KEY" in err


def test_key_value_not_leaked(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FIREWORKS_API_KEY", "sk-secret-123")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(cli, "build_model", lambda spec: ScriptedChatModel())

    async def fake_run(self):
        return RunResult("done", 0, 0, DoneStatus(True, []), {}, [])

    monkeypatch.setattr(cli.SwarmRunner, "run", fake_run)
    cli.main(write(tmp_path))
    cap = capsys.readouterr()
    assert "sk-secret-123" not in cap.out + cap.err


def test_toy_rosters_load():
    for name in ("roster.yaml", "roster.fireworks.yaml"):
        r = load_roster(f"examples/toy_dossier/{name}")
        assert [p.id for p in r.peers] == ["T01", "T02", "T03"]
        assert r.budget.swarm_usd == 2 and r.budget.peer_usd == 0.8 and r.budget.wall_clock_s == 1200
    assert {p.model for p in load_roster("examples/toy_dossier/roster.fireworks.yaml").peers} == {"deepseek", "minimax", "glm"}
    tasks = load_template("examples/toy_dossier/template.yaml")
    assert [t.id for t in tasks] == ["competitors", "pricing", "summary"]
    assert all(len(t.acceptance) == 3 for t in tasks)


@pytest.mark.parametrize("argv", [["run", "--roster", "x"], ["bogus"], ["run", "--nope"], []])
def test_usage_errors_return_1(argv, capsys):
    assert cli.main(argv) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_help_returns_0(capsys):
    assert cli.main(["--help"]) == 0


def test_existing_ledger_rejected_before_models(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "build_model", lambda spec: calls.append(spec) or ScriptedChatModel())

    async def fake_run(self):
        return RunResult("done", 0, 0, DoneStatus(True, []), {}, [])

    monkeypatch.setattr(cli.SwarmRunner, "run", fake_run)
    args = write(tmp_path)
    assert cli.main(args) == 0
    n = len(calls)
    capsys.readouterr()
    assert cli.main(args) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ledger") and "already exists" in err
    assert len(calls) == n


def test_default_run_ids_differ():
    assert cli._default_run_id() != cli._default_run_id()
