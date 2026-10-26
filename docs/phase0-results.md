# Phase 0 live smoke results

Command: `uv run pytest -m live tests/test_smoke_live.py -s` (roster.example.yaml, run 2026-10-26)

```
key | served_model | tool_call_ok | tool_loop_ok | reasoning_roundtrip | usage_reported | max_input_tokens | latency_s
deepseek | accounts/fireworks/models/deepseek-v4p1-flash-1017 | True | True | False | True | None | 2.87
minimax | accounts/fireworks/models/minimax-m3p1-flash | True | True | False | True | None | 1.15
glm | accounts/fireworks/models/glm-5p3-flash | True | True | True | True | 1048573 | 3.8
haiku | skipped (no ANTHROPIC_API_KEY) | - | - | - | - | - | -
luna | skipped (no OPENAI_API_KEY) | - | - | - | - | - | -
skipped (unverified): haiku, luna
```

## Notes

- All three Fireworks models pass `tool_call_ok` and `tool_loop_ok`; exit code 0.
- `haiku` (Anthropic) and `luna` (OpenAI) were NOT verified: their API keys were not set in this environment. Re-run with those keys to verify them.
- `max_input_tokens` is `None` for deepseek and minimax: deepagents will fall back to its 170K summarization trigger for these models. Finding to handle in later tasks (e.g. via `max_prompt_tokens` in the roster).
- `reasoning_roundtrip` is False for deepseek and minimax: no reasoning content was surfaced on the first response (not a failure; the second call did not error).
