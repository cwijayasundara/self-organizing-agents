import os
from pathlib import Path

import pytest
import yaml

from agora.config import ConfigError
from agora.eval import cli
from agora.eval.config import load_eval_config
from agora.eval.runner import ResultRow, RunEvalResult

YAML = "examples/eu_market_entry/eval.yaml"


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    for k in ("FIREWORKS_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_dry_run_prints_matrix_and_worst_case_without_keys(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--config", str(Path(__file__).parent.parent / YAML), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "7 runs" in out and "$21.00" in out and out.count("run: arm=") == 7
    assert list(tmp_path.iterdir()) == []


def test_live_run_requires_max_total_usd(capsys):
    assert cli.main(["--config", YAML]) == 1
    assert "error: --max-total-usd is required for a live run (use --dry-run to preview cost)" in capsys.readouterr().err


def test_max_total_smaller_than_one_run_rejected(capsys):
    assert cli.main(["--config", YAML, "--max-total-usd", "2.5"]) == 1
    assert "smaller than one run" in capsys.readouterr().err


def test_cli_exit_5_on_cap(tmp_path, monkeypatch, capsys):
    cfg = yaml.safe_load(Path(YAML).read_text())
    cfg["out_dir"] = str(tmp_path / "out")
    p = tmp_path / "e.yaml"
    p.write_text(yaml.safe_dump(cfg))

    async def fake(c, *, max_total_usd, **k):
        row = ResultRow("c1-10", 0, 0, "done", 1.0, 1.0, 0.5, 0.5, True, 1.0, 1, [], [], 3.0, "haiku", 0.0, "", {})
        Path(c.out_dir).mkdir(parents=True, exist_ok=True)
        (Path(c.out_dir) / "results.jsonl").write_text(row.to_json() + "\n")
        return RunEvalResult([row], True, 1.0)

    monkeypatch.setattr(cli, "run_eval", fake)
    assert cli.main(["--config", str(p), "--max-total-usd", "5"]) == 5
    assert (tmp_path / "out" / "report.md").exists()
    assert "stopped by cap: True" in capsys.readouterr().out


def test_usage_errors_exit_1(capsys):
    assert cli.main([]) == 1
    assert cli.main(["--config", YAML, "--dry-run", "--arms", "bogus"]) == 1
    assert cli.main(["--config", YAML, "--dry-run", "--variants", "x"]) == 1
    assert cli.main(["--config", YAML, "--dry-run", "--seeds", "0"]) == 1
    assert cli.main(["--config", "/nonexistent.yaml", "--dry-run"]) == 1
    assert cli.main(["--config", YAML, "--dry-run", "--arms", "c1-10", "--seeds", "2"]) == 0
    assert "2 runs" in capsys.readouterr().out


def test_eval_yaml_loads():
    c = load_eval_config(YAML)
    assert len(c.arms) == 7 and sorted(c.judges) == ["haiku", "luna"]
    assert sorted(c.team_models) == ["deepseek", "glm"]
    assert (c.budget_usd, c.wall_clock_s, c.variants, c.seeds) == (3, 1500, [0], 1)


def _load(tmp_path, **over):
    d = yaml.safe_load(Path(YAML).read_text())
    d.update(over)
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(d))
    return load_eval_config(p)


def test_eval_config_validation(tmp_path):
    d = yaml.safe_load(Path(YAML).read_text())
    with pytest.raises(ConfigError):
        _load(tmp_path, judges={"glm": d["judges"]["haiku"]})
    with pytest.raises(ConfigError):
        _load(tmp_path, arms=["c1-10", "nope"])
    with pytest.raises(ConfigError):
        _load(tmp_path, arms=["c1-10", "c1-10"])
    with pytest.raises(ConfigError):
        _load(tmp_path, team_models={"deepseek": d["team_models"]["deepseek"]})
    with pytest.raises(ConfigError):
        _load(tmp_path, budget_usd=0)


def test_missing_key_exit_1_names_env_var_not_value(tmp_path, monkeypatch, capsys):
    cfg = yaml.safe_load(Path(YAML).read_text())
    cfg.update(out_dir=str(tmp_path / "o"), data_root=str(tmp_path / "d"), gold_root=str(tmp_path / "g"),
               arms=["c0-glm"])
    p = tmp_path / "e.yaml"
    p.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    assert cli.main(["--config", str(p), "--max-total-usd", "5"]) == 1
    err = capsys.readouterr().err
    assert "FIREWORKS_API_KEY" in err and "sk-secret-value" not in err
