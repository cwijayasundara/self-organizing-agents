"""Build LangChain chat models from roster entries."""
from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

from agora.config import ConfigError, ModelSpec

_KEY_ENV = {
    "fireworks": "FIREWORKS_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def build_model(spec: ModelSpec) -> BaseChatModel:
    env = _KEY_ENV[spec.provider]
    if not os.environ.get(env):
        raise ConfigError(f"model {spec.key!r} needs {env} to be set")

    if spec.provider == "fireworks":
        from langchain_fireworks import ChatFireworks

        kwargs: dict = {"model": spec.id}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        if spec.reasoning_effort is not None:
            kwargs["reasoning_effort"] = spec.reasoning_effort
        return ChatFireworks(**kwargs)

    if spec.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        # No temperature/top_p/top_k: Haiku 5.5 rejects them.
        # ChatAnthropic has no `effort` field, so it goes through model_kwargs.
        kwargs = {
            "model": spec.id,
            "max_tokens": 16000,
            "thinking": {"type": "adaptive"},
        }
        if spec.effort is not None:
            kwargs["model_kwargs"] = {"output_config": {"effort": spec.effort}}
        return ChatAnthropic(**kwargs)

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=spec.id,
        use_responses_api=True,
        reasoning={"effort": spec.reasoning_effort or "low"},
    )
