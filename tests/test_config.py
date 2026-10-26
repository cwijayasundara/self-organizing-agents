import copy
from pathlib import Path

import pytest
import yaml

from agora.config import ConfigError, load_roster

EXAMPLE = Path(__file__).resolve().parent.parent / "roster.example.yaml"


def _raw():
    return copy.deepcopy(yaml.safe_load(EXAMPLE.read_text()))


def _write(tmp_path, raw):
    p = tmp_path / "roster.yaml"
    p.write_text(yaml.safe_dump(raw))
    return p


def test_example_roster_loads():
    r = load_roster(EXAMPLE)
    assert len(r.peers) == 10
    assert r.model_for("P03").id == "claude-haiku-5-5"
    assert r.models["deepseek"].temperature == 1.0
    assert [p.peer_usd for p in r.peers if p.model == "minimax"] == [0.6, 0.6]
    assert r.models["haiku"].tiers[0].above_prompt_tokens == 100000


def test_more_than_ten_peers_rejected(tmp_path):
    raw = _raw()
    raw["peers"].append({"id": "P11", "model": "glm"})
    with pytest.raises(ConfigError, match="at most 10 peers"):
        load_roster(_write(tmp_path, raw))


def test_duplicate_peer_ids_rejected(tmp_path):
    raw = _raw()
    raw["peers"][1]["id"] = "P01"
    with pytest.raises(ConfigError, match="P01"):
        load_roster(_write(tmp_path, raw))


def test_unknown_model_ref_rejected(tmp_path):
    raw = _raw()
    raw["peers"][0]["model"] = "nope"
    with pytest.raises(ConfigError, match="nope"):
        load_roster(_write(tmp_path, raw))


def test_single_family_roster_rejected(tmp_path):
    raw = _raw()
    for p in raw["peers"]:
        p["model"] = "deepseek"
    with pytest.raises(ConfigError, match="reviewer"):
        load_roster(_write(tmp_path, raw))


def test_anthropic_temperature_rejected(tmp_path):
    raw = _raw()
    raw["models"]["haiku"]["temperature"] = 0.2
    with pytest.raises(ConfigError, match="temperature"):
        load_roster(_write(tmp_path, raw))


def test_openai_tools_need_responses_api(tmp_path):
    raw = _raw()
    raw["models"]["luna"]["api"] = "chat"
    raw["models"]["luna"]["reasoning_effort"] = "low"
    with pytest.raises(ConfigError, match="responses"):
        load_roster(_write(tmp_path, raw))


def test_auto_requires_experiment_flag(tmp_path):
    raw = _raw()
    raw["models"]["deepseek"]["id"] = "auto"
    with pytest.raises(ConfigError, match="experiment"):
        load_roster(_write(tmp_path, raw))
    raw["models"]["deepseek"]["experiment"] = True
    assert load_roster(_write(tmp_path, raw)).models["deepseek"].id == "auto"
