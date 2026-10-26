import pytest

from agora.config import ConfigError, load_roster
from agora.models import build_model

ROSTER = "roster.example.yaml"


def test_fireworks_model(monkeypatch):
    monkeypatch.setenv("FIREWORKS_API_KEY", "dummy")
    m = build_model(load_roster(ROSTER).models["deepseek"])
    assert type(m).__name__ == "ChatFireworks"
    assert m.model_name.endswith("deepseek-v4p1-flash-1017")


def test_anthropic_model_has_no_sampling_params(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    m = build_model(load_roster(ROSTER).models["haiku"])
    assert type(m).__name__ == "ChatAnthropic" and m.model == "claude-haiku-5-5"
    assert m.temperature is None and m.top_p is None and m.top_k is None


def test_openai_model_uses_responses_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    m = build_model(load_roster(ROSTER).models["luna"])
    assert type(m).__name__ == "ChatOpenAI" and m.use_responses_api is True


def test_missing_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="FIREWORKS_API_KEY"):
        build_model(load_roster(ROSTER).models["glm"])
