# Fireworks-hosted GLM 5.3 Flash, DeepSeek V4.1 Flash, MiniMax M3.1 Flash: comparison and LangChain integration for heterogeneous multi-agent systems

Research date: 2026-10-26. Sources are mainly Fireworks model pages and docs (primary), plus third-party aggregators where Fireworks lists nothing (flagged as such).

## Q1. Do the exact model IDs exist on Fireworks, and what are their core specs?

### Takeaway
Two of the three IDs are confirmed on Fireworks' own model pages: `accounts/fireworks/models/glm-5p3-flash` and `accounts/fireworks/models/minimax-m3p1-flash`. For DeepSeek, Fireworks' page lists `accounts/fireworks/models/deepseek-v4p1-flash`, and its URL for `deepseek-v4p1-flash-1017` returned 404. Only a third-party aggregator lists the `-1017` ID, so it is **unverified on Fireworks**. All three are sparse MoE models with roughly 1M-token context, serverless pay-per-token access and supported function calling. Per 1M tokens, GLM costs $0.15 in / $0.50 out, MiniMax $0.15 / $0.60, and DeepSeek $0.30 / $1.20.

### Cited Findings

**Comparison sheet (Fireworks figures unless noted)**

| | GLM 5.3 Flash | DeepSeek V4.1 Flash (1017) | MiniMax M3.1 Flash |
|---|---|---|---|
| Fireworks ID | `accounts/fireworks/models/glm-5p3-flash` (confirmed) | `accounts/fireworks/models/deepseek-v4p1-flash` (confirmed); `...-v4p1-flash-1017` (third-party only) | `accounts/fireworks/models/minimax-m3p1-flash` (confirmed) |
| Vendor / HF | Z.ai, `zai-org/GLM-5.3-Flash` | DeepSeek, `deepseek-ai/DeepSeek-V4.1-Flash` | MiniMax, `MiniMaxAI/MiniMax-M3.1-Flash` |
| Architecture | MoE, 320B total / 18B active, hybrid attention arch + mHC | MoE, 552B "backbone", 8B active prefill / 16B active decode (causal encoder-decoder) | MoE, 428B total / ~23B active |
| Modalities | text + image in | text + image in | text + image in ("native multimodal") |
| Context | 1040k (1,048,576) | 1040k (1M) | 1040k (1M) |
| Max output | not listed by Fireworks; aggregators conflict (131,072 vs 1,048,576) | not listed by Fireworks; 384K (393,216) per model card/aggregators | not listed by Fireworks; 524,288 per Vals |
| Function calling | Supported | Supported | Supported |
| Reasoning | not described on FW page | thinking + non-thinking modes (aggregator) | always on, effort "low" to "max" |
| Price in / cached / out (per 1M) | $0.15 / $0.03 / $0.50 | $0.30 / $0.006 / $1.20 | $0.15 / $0.015 / $0.60 |
| Serverless | Yes | Yes | Yes |
| Fine-tuning (LoRA) | Yes | Yes | No |
| FW "created on" | 26 Aug 2026 | 10 Sep 2026 (base V4.1 Flash) | 17 Oct 2026 |
| License | open weights (HF) | MIT | open weights |

- GLM 5.3 Flash: Z.ai, MoE 320B total / 18B active, "first natively multimodal model in the GLM-5 series". Over GLM-5.2 it adds a hybrid architecture that cuts long-context serving cost, plus Manifold-Constrained Hyper-Connections (mHC). Context 1040k, function calling and image input supported, LoRA fine-tuning, serverless and on-demand. $0.15 input / $0.03 cached / $0.50 output per 1M. The page lists no benchmarks and no max output. — [Fireworks model page](https://fireworks.ai/models/fireworks/glm-5p3-flash)
- GLM 5.3 Flash max output: aggregators conflict, one giving 131,072 and another 1,048,576 "max tokens". Fireworks gives no figure. — [Fireworks/aggregator search summary](https://www.getmaxim.ai/bifrost/model-library/compare/fireworks_ai/glm-5p3-flash.md); [TypingMind guide](https://www.typingmind.com/guide/fireworks-ai/accounts-fireworks-models-glm-5p3-flash)
- DeepSeek V4.1 Flash on Fireworks: path `accounts/fireworks/models/deepseek-v4p1-flash`, 552B backbone, 8B active (prefill) / 16B active (decode), 1040k context, function calling, image input, fine-tuning, serverless. $0.30 / $0.006 cached / $1.20 per 1M. Created 10 Sep 2026. **The page lists no -1017 variant.** — [Fireworks model page](https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash)
- `https://fireworks.ai/models/fireworks/deepseek-v4p1-flash-1017` returned HTTP 404 (tested 2026-10-26). — direct fetch
- LLMReference lists `accounts/fireworks/models/deepseek-v4p1-flash-1017`: 552B MoE, 1M context, up to 384K output, tool calling, structured/JSON output, thinking and non-thinking modes, vision, prompt caching. $0.30 / $1.20, cache read $0.006. Release 2026-10-17, MIT license. — [LLMReference](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)
- Maxim/Bifrost lists `deepseek-v4p1-flash` at $0.22 / $0.66 with 1,048,576 input and 393,216 max output. Flags: function calling, vision, reasoning, prompt caching, response schema, tool choice. Parallel function calling is **not** flagged. This price conflicts with Fireworks' own $0.30 / $1.20. — [Maxim Bifrost](https://www.getmaxim.ai/bifrost/model-library/compare/fireworks_ai/deepseek-v4p1-flash.md)
- Fireworks is deprecating DeepSeek-V4-Flash-0731 on serverless from Sept 25, 2026, with migration recommended to DeepSeek V4.1 Flash. — [Fireworks V4-Flash-0731 page](https://fireworks.ai/models/deepseek-ai/deepseek-v4-flash-0731)
- DeepSeek V4.1 Flash 1017 itself: released Oct 17, 2026 on HF under MIT, and the API alias `deepseek-flash` now points to it. Context 1M, max output 384K, and the card recommends allowing ≥256K output tokens. Recommended temperature 1.0 and top_p 1.0. No Jinja chat template ships in this version; production use goes through `deepseek-recipe`. The article gives 763B params, which conflicts with Fireworks' 552B. — [Pillitteri news](https://pasqualepillitteri.it/en/news/24844/deepseek-releases-41-flash-1017-mit-weights-shorter-outputs)
- MiniMax M3.1 Flash on Fireworks: 428B total / ~23B active MoE, 1040k context, function calling, image input, reasoning "always on with adjustable effort from low to max". $0.15 / $0.015 cached / $0.60. Serverless and on-demand, no fine-tuning, created 17 Oct 2026. — [Fireworks model page](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- MiniMax M3.1 Flash per Vals: open-weight, released Oct 20, 2026. 1M context, 524,288 max output (262k used in testing), inputs text/image/video/file, $0.15 / $0.60. — [Vals AI](https://www.vals.ai/models/minimax_MiniMax-M3.1-flash)

### Inferences
- If the `-1017` ID fails on your account, use `accounts/fireworks/models/deepseek-v4p1-flash`. Fireworks may have updated the base path in place to the 1017 weights, but nothing confirms that. Run `firectl get model` or a test call before hardcoding either ID.
- All three fall in Fireworks' "Small" (<800B) rate-limit class (see Q4), so throughput ceilings are the same across them.

### Gaps
- Fireworks-published max output for all three models.
- Whether Fireworks' `deepseek-v4p1-flash` serves the Sept or the Oct (1017) weights.
- Total parameters for DeepSeek V4.1 Flash: 552B (Fireworks, Azure) vs 763B (Pillitteri) vs ~748B (other press).

## Q2. Agentic and tool-use benchmarks, strengths and weaknesses

### Takeaway
None of the sources report BFCL or tau2-bench for any of the three models. The comparable agentic numbers are DeepSWE v1.1 and AutomationBench. DeepSeek V4.1 Flash 1017 leads on vendor-reported agentic coding (DeepSWE 77.0, AutomationBench 60.5). MiniMax M3.1 Flash is close (DeepSWE 73.7, AutomationBench-AA 62.8 per Fireworks). GLM 5.3 Flash trails (DeepSWE 63.4, AutomationBench 48.8) but is the cheapest on output.

### Cited Findings
- DeepSeek V4.1 Flash, Sept build → 1017 build (DeepSeek-reported): Terminal-Bench 4.0 31.2→42.3 (1017 run on the Claude Code harness), DeepSWE v1.1 74.2→77.0 (Mini-SWE-V2), ProgramBench 20.3→29.1, NL2Repo-Bench 65.4→68.2, Automation-Bench v1.0.6 54.8→60.5, Agents' Last Exam 31.8→35.4, Apex Bench v1.1 64.6→72.1, HLE no-tools 36.8→42.6, Chartography (tools) 78.9→83.0, BabyVision (tools) 89.6→92.5, ZeroBench-main (tools) 49.0→51.0. The vendor also claims "shorter outputs" and faster task completion, without quantifying either. — [Pillitteri news](https://pasqualepillitteri.it/en/news/24844/deepseek-releases-41-flash-1017-mit-weights-shorter-outputs)
- DeepSeek V4.1 Flash (Sept): Terminal-Bench 2.1 90.6 and CyberGym 88.1. Weak on HLE (36.8 vs Opus 5 56.3). TNW had not independently verified the figures. — [TNW](https://thenextweb.com/news/deepseek-v4-1-flash-launch-v4-pro-retired-price-cut); [ProPakistani](https://propakistani.pk/2026/09/11/deepseek-v4-1-flash-launches-with-lower-prices-and-native-vision/)
- DeepSeek V4.1 Flash 1017 ranks #14 of 50 on the independent Vals Index at 56.58%. — [Vals AI](https://www.vals.ai/models/deepseek_deepseek-v4.1-flash-1017) (via search summary)
- MiniMax M3.1 Flash: Fireworks lists AutomationBench-AA 62.8 and DeepSWE v1.1 73.7%. — [Fireworks model page](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- MiniMax M3.1 Flash (independent, Vals, compute effort max): Vals Index 53.78% (17/27), Finance Agent v2.1 58.83%, Terminal-Bench 4.0 25.25% (24/55), Vibe Code Bench v1.1 73.94%, Tax Agent Bench 32.14%, Legal Research Bench 34.13%. Latency per run is 43 min 18 s. The page is internally inconsistent: rank 17/27 vs "#15 of 22", and cost $0.66 vs $4.46. — [Vals AI](https://www.vals.ai/models/minimax_MiniMax-M3.1-flash)
- GLM 5.3 Flash (Z.ai-reported): Terminal-Bench 2.1 84.3, DeepSWE v1.1 63.4, AutomationBench v1.0.6 48.8. Artificial Analysis Intelligence Index 57. AA Tau3 Banking 47.2% (a tau3 variant, not tau2-bench). — [BenchLM](https://benchlm.ai/md/models/glm-5-3-flash.md); [DataCamp](https://www.datacamp.com/blog/glm-5-3-flash) (via search summary)

### Inferences
- **DeepSeek V4.1 Flash:** strongest agentic coding and automation numbers, the most output headroom (384K), and the cheapest cached input ($0.006). It also has the highest list price at 2x output vs MiniMax. Its numbers are vendor-reported, and the harness changes between builds (Terminal-Bench 3.0 vs 4.0, Claude Code harness) make comparisons noisy.
- **MiniMax M3.1 Flash:** near-DeepSeek agentic scores at half the price. But reasoning cannot be turned off, so expect higher token usage and latency (43-minute Vals run). On independent Terminal-Bench 4.0 it scores 25.25 vs DeepSeek's vendor-reported 42.3; the harnesses differ.
- **GLM 5.3 Flash:** the cheapest and fewest active params (18B), so likely the fastest per token. Its hybrid long-context architecture suits 1M-token synthesis. It has the weakest agentic scores of the three.

### Gaps
- No BFCL, tau2-bench or SWE-bench Verified numbers for any of the three, and no independent tool-call reliability rates (malformed-JSON frequency, parallel call accuracy).
- No measured Fireworks throughput or latency (TPS, TTFT) for these models.

## Q3. Reasoning modes, structured output and tool calling via the Fireworks API

### Takeaway
Fireworks returns reasoning in `message.reasoning_content` (and in `delta.reasoning_content` when streaming). Depth is controlled with `reasoning_effort` (strings such as low/medium/high; MiniMax goes up to "max") or with the Anthropic-style `thinking={"type":"enabled","budget_tokens":>=1024}`, but not both. In agent loops you must send `reasoning_content` back on assistant turns so interleaved thinking survives tool calls. Using `response_format: json_schema` disables reasoning output.

### Cited Findings
- `reasoning_content` holds the internal reasoning that would otherwise sit in `<think>` tags in `content`. Some models still put it in `content`. — [Fireworks reasoning guide](https://docs.fireworks.ai/guides/reasoning.md)
- `reasoning_effort` accepts strings "like" low/medium/high (no complete list). `thinking` with `budget_tokens` ≥1024 is the Anthropic-compatible alternative. Sending both raises a validation error. — [Fireworks reasoning guide](https://docs.fireworks.ai/guides/reasoning.md)
- Interleaved thinking applies when the last message is `role: "tool"`. You must include `reasoning_content` from earlier assistant turns, or the model loses its prior reasoning. `reasoning_history="preserved"` keeps reasoning across earlier user turns. — [Fireworks reasoning guide](https://docs.fireworks.ai/guides/reasoning.md)
- NIM/vLLM-style `chat_template_kwargs.enable_thinking` maps to `reasoning_effort` automatically. The Anthropic-compatible base URL is `https://api.fireworks.ai/inference`. — [Fireworks reasoning guide](https://docs.fireworks.ai/guides/reasoning.md)
- MiniMax M3.1 Flash reasoning is "always on with adjustable effort from low to max". — [Fireworks model page](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- DeepSeek V4.1 Flash 1017 supports thinking and non-thinking modes. — [LLMReference](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)
- Structured output: `response_format` supports `json_object` and `json_schema` (recommended), with GBNF grammar mode on a separate page. On reasoning models, `json_schema` disables reasoning output. To get both, put the schema in the prompt, omit `response_format`, and strip markdown fences. External `$ref` is unsupported and `pattern` is best-effort. If `finish_reason=="length"` the JSON may be truncated. Always ask for JSON in the prompt, or the model may emit endless whitespace. Tool calling turns JSON mode on automatically. — [Fireworks structured output](https://docs.fireworks.ai/structured-responses/structured-response-formatting)
- Tool calling: `tool_choice` accepts auto, none, required, or a named function. Parallel tool calling is only "some models", with no documented toggle. Streaming tool-call args must be accumulated per `index` and are complete when `finish_reason=="tool_calls"`. Tool names allow `[a-zA-Z0-9_-]` up to 64 chars. Use temperature 0.0–0.3 to reduce hallucinated args. Validate malformed JSON in `arguments`. `$ref` supports only in-document `#/...` refs, and anything else returns 400. — [Fireworks function calling](https://docs.fireworks.ai/guides/function-calling)

### Inferences
- In Deep Agents, a subagent that must return a typed result should either run without reasoning (for DeepSeek, low or non-thinking effort) under `json_schema`, or use tool-call-based structured output, since tool calling enables JSON mode without killing reasoning.
- DeepSeek's recommended temperature of 1.0 conflicts with Fireworks' 0.0–0.3 advice for tool calling. Test both settings for worker agents.

### Gaps
- No per-model matrix of `reasoning_effort` values. Whether GLM 5.3 Flash exposes thinking on/off is unconfirmed (the Fireworks page doesn't say).
- Whether parallel tool calls work on each of the three models is undocumented.

## Q4. Calling Fireworks from LangChain (ChatFireworks, init_chat_model, ChatOpenAI) and gotchas

### Takeaway
Use `langchain-fireworks` `ChatFireworks` with `FIREWORKS_API_KEY`. It supports tool calling, structured output, streaming, async, token usage and logprobs, and passes `reasoning_effort` through (requires `langchain-fireworks>=1.5.2`). This is better than `ChatOpenAI` pointed at `https://api.fireworks.ai/inference/v1`, which likely drops Fireworks-specific `reasoning_content` (see Inferences).

### Cited Findings
- Install `pip install -qU langchain-fireworks` and set the env var `FIREWORKS_API_KEY`. Constructor parameters include `model`, `temperature`, `max_tokens`, `timeout` and `max_retries`. — [LangChain ChatFireworks docs](https://docs.langchain.com/oss/python/integrations/chat/fireworks)
- `reasoning_effort` is passed through unchanged, can be set at construction or per call, and needs `langchain-fireworks>=1.5.2`. `model.profile["reasoning_effort_levels"]` lists the levels a model supports. — [LangChain ChatFireworks docs](https://docs.langchain.com/oss/python/integrations/chat/fireworks)
- Feature table: tool calling yes, structured output yes, image input yes (vision models), audio/video no, token streaming yes, native async yes, token usage yes, logprobs yes. — [LangChain ChatFireworks docs](https://docs.langchain.com/oss/python/integrations/chat/fireworks)

```python
from langchain_fireworks import ChatFireworks
planner = ChatFireworks(model="accounts/fireworks/models/deepseek-v4p1-flash",  # or -1017 if it resolves
                        reasoning_effort="high", max_tokens=32000, max_retries=4)
worker  = ChatFireworks(model="accounts/fireworks/models/minimax-m3p1-flash",
                        reasoning_effort="low", temperature=0.2)
synth   = ChatFireworks(model="accounts/fireworks/models/glm-5p3-flash", max_tokens=16000)
# Prompt-cache stickiness per agent/session (Fireworks feature, see Q5); passing via
# default_headers / model_kwargs is an assumption to verify with your langchain-fireworks version:
# ChatFireworks(..., model_kwargs={"user": session_id})
```

### Inferences (not directly sourced; verify)
- `init_chat_model("fireworks:accounts/fireworks/models/glm-5p3-flash")` should resolve to `ChatFireworks` by LangChain's standard `provider:model` convention. The fetched page didn't document it. Deep Agents (`create_deep_agent(model=...)`) accepts either a model string or a chat model instance, so passing preconfigured `ChatFireworks` objects per subagent gives control over `reasoning_effort`.
- `ChatOpenAI(base_url="https://api.fireworks.ai/inference/v1", api_key=FIREWORKS_API_KEY)` handles basic chat and tool calls. langchain-openai doesn't parse non-standard `reasoning_content` from Chat Completions, so reasoning would be lost. That breaks Fireworks' interleaved-thinking requirement to send `reasoning_content` back on tool turns.
- Even with ChatFireworks, confirm that `reasoning_content` round-trips in `AIMessage.additional_kwargs` back into the next request in a tool loop. Otherwise multi-step reasoning quality degrades silently.
- `with_structured_output(method="json_schema")` on these reasoning models disables reasoning (Fireworks behavior, Q3). Prefer `method="function_calling"` for reasoning-heavy roles.
- Streaming: tool-call chunks must be merged by `index` (LangChain does this in `AIMessageChunk`). Ensure tool args are parsed only at `finish_reason=="tool_calls"`.

### Gaps
- Official LangChain docs on `bind_tools` parallel calls, `reasoning_content` round-tripping and `init_chat_model` for Fireworks weren't retrieved.

## Q5. Fireworks platform features relevant to multi-agent (caching, rate limits, batch, structured outputs)

### Takeaway
Prompt caching is automatic and prefix-based, with default ~50% discount on serverless; these models' cached rates are 80–98% off. Caching needs session affinity (`x-session-affinity` header or `user` field). Rate limits are per account and per model, adaptive TPM within tier ceilings, and all three models sit in the "Small" class (216M total prompt / 54M uncached prompt / 2.16M generated TPM at Tier 3+), under an account-wide cap of 6,000 RPM.

### Cited Findings
- Prompt caching is on by default for all models, reuses the longest cached exact prefix, and lasts minutes to hours. The serverless discount defaults to 50% and varies per model. On dedicated deployments cached tokens are "nearly free". The cache lives per replica, so use `x-session-affinity` or `user` for stickiness; `x-prompt-cache-isolation-key` isolates tenants. Put tools, instructions and examples first and keep timestamps out of system prompts. Tools count as part of the prompt. — [Fireworks prompt caching](https://docs.fireworks.ai/guides/prompt-caching)
- Serverless TPM classes at Tier 3+: Small (<800B) 216M total prompt / 54M uncached / 2.16M generated TPM. The class explicitly includes DeepSeek V4.1 Flash, GLM 5.3 Flash and MiniMax M3. Limits adapt: +25% when 1-minute usage is above 50% of the limit, at most once per 15 min; decay after low use; reset after 72h idle. Elastic Burst is not guaranteed. Honor `Retry-After` on 429. Limits are scoped per account and per model. Headers: `X-Ratelimit-Limit-Tokens-Prompt`, `-Uncached-Prompt`, `-Generated`, `-Cache-Adjusted-Prompt`. 503s are still possible, and Priority tier reduces them. — [Fireworks serverless rate limits](https://docs.fireworks.ai/serverless/rate-limits.md)
- Spend tiers: Tier 1 $50/mo cap, Tier 2 $500, Tier 3 $5,000, Tier 4 $50,000, Unlimited via sales. The account-wide limit is 10 RPM without a payment method and 6,000 RPM with credits. Dedicated deployments aren't TPM-limited but count toward RPM; default GPU quotas are 16 each of H100/H200/B200/B300. — [Fireworks rate limits](https://docs.fireworks.ai/guides/quotas_usage/rate-limits)
- Structured outputs: JSON object, JSON schema and GBNF grammar modes (see Q3). — [Fireworks structured output](https://docs.fireworks.ai/structured-responses/structured-response-formatting)

### Inferences
- Because limits are per model, spreading agent roles across three different models triples the effective serverless TPM headroom. That argues for a heterogeneous design at high concurrency.
- Give each agent a stable session key for cache affinity, and keep a byte-identical shared system prompt and tool list across workers of the same role.
- Generated TPM (2.16M) is the binding constraint for always-on reasoners like MiniMax M3.1 Flash.

### Gaps
- Batch API pricing or discount for these models, and whether it exists for them, wasn't found.
- No documented concurrency (in-flight request) limit beyond RPM and TPM.

## Q6. Recommendations: which model for which agent role

### Takeaway
DeepSeek V4.1 Flash (1017) as the planner, critic and hard-coding agent. MiniMax M3.1 Flash as the high-volume agentic tool-using worker, at low effort. GLM 5.3 Flash as the cheap long-context synthesizer, summarizer, router or reader. Validate tool-call reliability empirically, because no BFCL or tau-bench evidence exists.

### Cited Findings
- DeepSeek has the best vendor-reported agentic scores (DeepSWE 77.0, AutomationBench 60.5, Apex 72.1), 384K max output, and $0.006 cached input, at $0.30 / $1.20. — [Pillitteri](https://pasqualepillitteri.it/en/news/24844/deepseek-releases-41-flash-1017-mit-weights-shorter-outputs); [Fireworks](https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash)
- MiniMax: DeepSWE 73.7 and AutomationBench-AA 62.8 at $0.15 / $0.60, with reasoning effort adjustable down to low. — [Fireworks](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- GLM: 18B active, a hybrid architecture that reduces long-context serving cost, 1040k context, $0.15 / $0.03 / $0.50, and LoRA fine-tuning. — [Fireworks](https://fireworks.ai/models/fireworks/glm-5p3-flash)

### Inferences
| Role | Primary | Why | Settings |
|---|---|---|---|
| Planner / orchestrator / critic | DeepSeek V4.1 Flash | highest agentic scores, large output budget for plans and reviews | `reasoning_effort="high"`, return `reasoning_content` on tool turns |
| High-volume tool worker (coding, browsing, API calls) | MiniMax M3.1 Flash | near-top DeepSWE/AutomationBench at half DeepSeek's price | `reasoning_effort="low"`, temp 0.2, retries, JSON-arg validation |
| Long-context synthesizer / summarizer / retrieval reader | GLM 5.3 Flash | cheapest output, long-context-efficient architecture, vision | moderate `max_tokens`; cache shared corpus prefix |
| Structured extractor / router | GLM 5.3 Flash (or DeepSeek non-thinking) | `json_schema` disables reasoning anyway, so the cheapest model wins | `with_structured_output(method="json_schema")` |
| Fine-tuned specialist | GLM 5.3 Flash or DeepSeek | both allow LoRA (MiniMax does not) | — |
- Fallbacks: chain MiniMax and GLM (`with_fallbacks`) to absorb per-model 429s/503s.

### Gaps
- No head-to-head tool-call reliability or latency data on Fireworks. Run a small internal eval (for example 100 multi-tool tasks per model) before fixing role assignments.
