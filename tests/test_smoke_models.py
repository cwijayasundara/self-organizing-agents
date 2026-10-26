"""Hermetic unit tests for scripts/smoke_models.py using fake models."""
import importlib.util
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parent.parent


def _load_script():
    spec = importlib.util.spec_from_file_location("smoke_models", ROOT / "scripts" / "smoke_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeModel:
    def __init__(self, call_tool: bool):
        self.call_tool = call_tool
        self.profile = {"max_input_tokens": 1000}
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        meta = {"model_name": "fake"}
        if self.calls == 1 and self.call_tool:
            return AIMessage(
                content="",
                tool_calls=[{"name": "add", "args": {"a": 17, "b": 25}, "id": "c1"}],
                response_metadata=meta,
                usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            )
        return AIMessage(content="The answer is 42", response_metadata=meta)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("FIREWORKS_API_KEY", "dummy-not-a-key")


def test_skipped_provider_is_not_a_failure(env, monkeypatch, capsys):
    mod = _load_script()
    monkeypatch.setattr(mod, "build_model", lambda spec: FakeModel(call_tool=True))
    rc = mod.main(["--roster", str(ROOT / "roster.example.yaml")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skipped (no ANTHROPIC_API_KEY)" in out
    assert "skipped (no OPENAI_API_KEY)" in out
    assert "haiku" in out.splitlines()[-1] and "luna" in out.splitlines()[-1]


def test_no_tool_call_fails(env, monkeypatch):
    mod = _load_script()
    monkeypatch.setattr(mod, "build_model", lambda spec: FakeModel(call_tool=False))
    assert mod.main(["--roster", str(ROOT / "roster.example.yaml")]) != 0
