# Fireworks.ai agent LLMs: GLM-5.3 Flash vs DeepSeek V4.1 Flash (1017) vs MiniMax M3.1 Flash

Research date: 2026-10-26. All three Fireworks model IDs were confirmed to exist. Fireworks' own page for `deepseek-v4p1-flash-1017` could not be fetched (client error), so Fireworks-specific DeepSeek figures come from llmreference.com and OpenRouter's Fireworks rows. Most benchmark numbers are vendor-reported and have not been independently reproduced. Benchmark suites in late 2026 have moved on (Terminal-Bench 2.1/4.0, DeepSWE v1.1, AutomationBench, Toolathlon). Few sources report BFCL, tau2-bench, SWE-bench Verified or BrowseComp for these models.

## Q1. Specs, pricing and serving on Fireworks

### Takeaway
All three are sparse MoE models with ~1M context, image input, function calling and serverless per-token pricing on Fireworks.
- **Cheapest:** GLM-5.3 Flash ($0.15 in / $0.50 out) and MiniMax M3.1 Flash ($0.15 / $0.60).
- **DeepSeek V4.1 Flash 1017:** costs about 2x more ($0.30 / $1.20), but has the cheapest cached input ($0.006) and the most documented controls (thinking on/off, JSON schema structured outputs, 384K max output).

### Cited Findings

**GLM-5.3 Flash (`accounts/fireworks/models/glm-5p3-flash`)**
- **Release:** Z.ai released it on 26 Aug 2026. It is a newly trained base model, not a post-trained GLM-5.2. It mixes sparse and linear attention for long sequences and is "natively multimodal". — [DataNorth](https://datanorth.ai/news/z-ai-releases-glm-5-3-flash)
- **Size:** 320B total parameters, 18B active. — [DataNorth](https://datanorth.ai/news/z-ai-releases-glm-5-3-flash); [Fireworks model page](https://fireworks.ai/models/fireworks/glm-5p3-flash)
- **License and serving:** MIT-licensed weights on Hugging Face (zai-org/GLM-5.3-Flash). Serves on vLLM and SGLang. — [DataNorth](https://datanorth.ai/news/z-ai-releases-glm-5-3-flash)
- **Fireworks page:**
  - Created 26 Aug 2026.
  - MoE, 320B / 18B active, "hybrid architecture and Manifold-Constrained Hyper-Connections (mHC)".
  - Context listed as 1040k tokens.
  - Pricing per 1M tokens: $0.15 input / $0.03 cached input / $0.50 output.
  - Function calling and image input supported.
  - Serverless; on-demand dedicated deployment and LoRA fine-tuning available.
  - Max output not stated. How reasoning is toggled not stated.
  - — [Fireworks](https://fireworks.ai/models/fireworks/glm-5p3-flash)
- **Pricing claim:** Z.ai says the overall price is about 1/10 of GLM-5.2's. — [DataNorth](https://datanorth.ai/news/z-ai-releases-glm-5-3-flash)

**DeepSeek V4.1 Flash 1017 (`accounts/fireworks/models/deepseek-v4p1-flash-1017`)**
- **Release:** V4.1-Flash released 10 Sep 2026. The 1017 snapshot released 17 Oct 2026 as a "minor update". DeepSeek's API alias `deepseek-flash` now points to 1017. — [braindetox (summarising DeepSeek card/release note)](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html); [OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash)
- **Architecture:**
  - 552B backbone, 8B active per token at prefill and 16B at decode.
  - 40 layers using the "Causal Encoder-Decoder" (CED) design: a 20-layer encoder followed by a 20-layer decoder.
  - 384 routed experts plus 1 shared expert, 6 active per token.
  - KV cache of about 890 bytes/token, roughly 1/4 of V4-Flash.
  - Native vision encoder. MIT license.
  - — [braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html)
- **Context and output:** 1M context; max output 384K on DeepSeek's API, with recommended `max_tokens` of 256K or more. — [braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html)
  - **Conflict:** OpenRouter lists up to 1,048,576 completion tokens. — [OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash)
- **Fireworks pricing:** $0.30 input / $0.006 cache read / $1.20 output per 1M. Thinking and non-thinking modes, tools, JSON / structured outputs, vision and prompt caching are listed. Serverless and provisioned. — [llmreference](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)
- **Fireworks endpoints on OpenRouter:**

  | Endpoint | Input /M | Output /M | Cache read /M | Latency | Throughput | Uptime |
  |---|---|---|---|---|---|---|
  | Fireworks standard | $0.30 | $1.20 | $0.006 | 0.65 s | 84 tps | 99.92% |
  | Fireworks Spot | $0.21 | $0.84 | $0.0042 | 0.59 s | 225 tps | 100% |
  | Faster Fireworks tier | $0.45 | $1.80 | $0.009 | 0.28 s | 195 tps | n/a |

  The fastest providers on the same page are Together (0.19 s, 269 tps) and Baseten (0.19 s, 292 tps). — [OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash)
- **DeepSeek first-party pricing:** $0.15–0.30 input (cache miss), $0.003–0.006 cache hit, $0.60–1.20 output, depending on off-peak or peak hours. — [braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html)

**MiniMax M3.1 Flash (`accounts/fireworks/models/minimax-m3p1-flash`)**
- **Fireworks page:**
  - Created 17 Oct 2026.
  - MoE, about 428B total / about 23B active, natively multimodal.
  - Context 1040k (description says 1M).
  - Pricing per 1M tokens: $0.15 input / $0.015 cached input / $0.60 output.
  - Function calling and image input supported. Reasoning is "always on", with effort adjustable from low to max.
  - Serverless; on-demand deployment available. No fine-tuning.
  - Lists Hugging Face repo MiniMaxAI/MiniMax-M3.1-Flash.
  - Benchmarks shown: AutomationBench-AA 62.8, DeepSWE v1.1 73.7%.
  - — [Fireworks](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- **Preview launch:** It first appeared as a preview (`MiniMax-M3.1-Flash-Preview`) in MiniMax Code / Token Plan on 27 Sep 2026, with no open weights at that time. Input modalities: text, image and video. — [eesel](https://www.eesel.ai/blog/minimax-m3-1-flash)
- **Release date and openness conflict:** Artificial Analysis lists the release as 19 Oct 2026, the model as "proprietary" and parameters as undisclosed. — [Artificial Analysis](https://artificialanalysis.ai/de/models/minimax-m3-1-flash)
  - This contradicts Fireworks' HF repo link and 428B/23B figures. The likely explanation is that GA open weights followed the preview, but this was not verified from a MiniMax primary source.
- **Speed, latency and verbosity (Artificial Analysis):**
  - Output speed 112.8 tok/s; median of peers 116.2.
  - Time to first token 1.35 s.
  - Price $0.15 / $0.60 with a 90% cache discount.
  - Verbose: 180M output tokens on the Intelligence Index versus a 100M median.
  - — [Artificial Analysis](https://artificialanalysis.ai/de/models/minimax-m3-1-flash)

### Inferences
- **Cost per agent step:** with heavy cache reuse, as in a Deep Agents loop that re-sends a long system prompt, tools and files on every step:
  - DeepSeek's $0.006 cached input is cheapest for reading context, but its output costs 2x the others.
  - MiniMax's $0.015 cached input is the next cheapest for reading context; GLM's $0.03 is the most expensive of the three.
  - Because output tokens dominate the cost of reasoning models, GLM is likely the cheapest per step overall. MiniMax's verbosity (high AA token usage) partly cancels its low unit price.
- **Throughput:** DeepSeek's Fireworks standard endpoint (84 tps) looked slower than Fireworks Spot or other providers on OpenRouter. If latency matters, consider the Fireworks faster tier or a dedicated deployment.

### Gaps
- Fireworks max-output limits for GLM-5.3 Flash and MiniMax M3.1 Flash were not found.
- Fireworks serverless rate limits per model were not found. Fireworks' general account-tier limits apply; the MiniMax page notes only "no rate limits" for on-demand deployments.
- Fireworks-measured throughput for GLM-5.3 Flash and MiniMax M3.1 Flash was not found. Only AA's aggregate figure for MiniMax (113 tok/s) is available.
- The DeepSeek Fireworks page itself could not be fetched.

## Q2. Agent-relevant benchmarks

### Takeaway
On shared suites, DeepSeek V4.1 Flash 1017 leads:
- DeepSWE v1.1: 77.0, versus MiniMax 73.7 and GLM 63.4.
- Terminal-Bench 4.0: 42.3 (vendor), versus GLM 32.8 measured by AA.
- AutomationBench: DeepSeek 60.5 vendor-reported versus MiniMax 62.8 on Fireworks / AA. Similar AA figures for GLM are 60.4; GLM's own vendor figure is 48.8.
- Long context: DeepSeek AA-LCR 84.0 versus GLM 80.0.

GLM-5.3 Flash has the strongest vendor tool-use number (Toolathlon Verified 78.4). On the AA Intelligence Index, MiniMax M3.1 Flash is reported at 43, against roughly 42 for GLM and 39.5 for DeepSeek, but these are on differing scales and snapshots. BFCL, tau2-bench, SWE-bench Verified and BrowseComp were not reported for any of the three in the sources found.

### Cited Findings

**GLM-5.3 Flash** (Z.ai launch post, vendor-reported)
- Terminal-Bench 2.1: 84.3; DeepSWE 1.1: 63.4; Toolathlon Verified: 78.4; AutomationBench: 48.8; OfficeQA Pro: 62.4. — [DataNorth](https://datanorth.ai/news/z-ai-releases-glm-5-3-flash)
- Agents' Last Exam: 26.3; HLE with tools: 55.3; NL2Repo: 56.3. — [BenchLM](https://benchlm.ai/md/models/glm-5-3-flash.md)

**GLM-5.3 Flash** (independent, via BenchLM's aggregation)

| Benchmark | Score | Measured by |
|---|---|---|
| AA Tau3 Banking | 47.2% | Artificial Analysis |
| AA AutomationBench | 60.4% | Artificial Analysis |
| AA Terminal-Bench 4.0 | 32.8% | Artificial Analysis |
| AA-LCR (long context) | 80.0% | Artificial Analysis |
| AA EnterpriseOps-Gym | 33.2% | Artificial Analysis |
| AA ITBench | 51.2% | Artificial Analysis |
| AA Intelligence Index | 41.8 | Artificial Analysis |
| Terminal-Bench 2.1 | 62.9% | Vals AI |
| SWE-bench | 92.0% | Vals AI |
| Hermes Bench | 68.9% | Nous Research |

— [BenchLM](https://benchlm.ai/md/models/glm-5-3-flash.md)

- **Intelligence Index conflict:** DataNorth cites an AA Intelligence Index of 57 for GLM-5.3 Flash, which conflicts with BenchLM's 41.8. This is probably a different index version or scale. — [DataNorth](https://datanorth.ai/news/z-ai-releases-glm-5-3-flash)
- **Vendor versus independent Terminal-Bench 2.1:** Z.ai reports 84.3; Vals AI measured 62.9. Treat vendor numbers cautiously. — [BenchLM](https://benchlm.ai/md/models/glm-5-3-flash.md)

**DeepSeek V4.1 Flash 1017** (DeepSeek-reported; V4.1-Flash → 1017)

| Benchmark | V4.1-Flash | 1017 |
|---|---|---|
| Terminal-Bench 4.0 | 31.2 | 42.3 |
| DeepSWE v1.1 | 74.2 | 77.0 |
| AutomationBench v1.0.6 | 54.8 | 60.5 |
| Agents' Last Exam | 31.8 | 35.4 |
| NL2Repo | 65.4 | 68.2 |
| ProgramBench | 20.3 | 29.1 |
| HLE (no tools) | 36.8 | 42.6 |

— [braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html)

- **Harness sensitivity:** DeepSWE scored 74.2 with mini-SWE versus 65.5 with OpenCode on V4.1-Flash. — [braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html)
- **V4.1-Flash card:** Terminal-Bench 2.1: 90.6; HLE with tools: 63.9. — [BenchLM](https://benchlm.ai/md/models/deepseek-v4-1-flash.md)
- **Independent:**

  | Benchmark | Score | Measured by |
  |---|---|---|
  | Terminal-Bench 2.1 | 74.5% | Vals AI |
  | AA-LCR | 84.0% | Artificial Analysis |
  | AA ITBench | 46.9% | Artificial Analysis |
  | GDPval-AA | 55.0 | Artificial Analysis |
  | AA Intelligence Index | 39.5 | Artificial Analysis |
  | AA-Omniscience Hallucination Rate | 96.5% | Artificial Analysis |

  Note the very high AA-Omniscience Hallucination Rate: the model tends to answer rather than abstain on unknown facts. — [BenchLM](https://benchlm.ai/md/models/deepseek-v4-1-flash.md)

**MiniMax M3.1 Flash**
- AutomationBench-AA: 62.8; DeepSWE v1.1: 73.7%. — [Fireworks](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- AA Intelligence Index: 43, ranked #5 of 343. Per-benchmark scores (Terminal-Bench 4.0, AA-LCR, etc.) are not shown on the fetched page. — [Artificial Analysis](https://artificialanalysis.ai/de/models/minimax-m3-1-flash)
- At preview, no M3.1 Flash-specific benchmarks had been published. Figures circulating then belonged to M3. — [eesel](https://www.eesel.ai/blog/minimax-m3-1-flash)

### Inferences
- **Hardest work (worker/coder):** DeepSeek V4.1 Flash 1017 has the best coding and terminal scores (DeepSWE 77.0, Terminal-Bench 4.0 42.3) and the best long-context score (AA-LCR 84). That fits worker roles on code or terminal tasks, and summarizer or verifier roles over long transcripts.
- **Tool use:** GLM-5.3 Flash's Toolathlon 78.4 and Tau3 Banking 47.2 suggest solid multi-tool and function-calling reliability at the lowest output price. It is a candidate for high-volume tool-routing workers, or a claimer/planner that mostly emits structured tool calls.
- **Generalist:** MiniMax M3.1 Flash has the highest AA Intelligence Index and AutomationBench score, but is always-reasoning and verbose. It is a candidate for a planner or verifier, where judgment quality matters more than tokens. Its benchmark coverage is thin.
- **Head-to-head comparison:** no source evaluated all three together on one harness. The comparisons above are assembled from separate sources.

### Gaps
- No BFCL, tau2-bench, SWE-bench Verified, or BrowseComp scores were found for any of the three.
- No dedicated instruction-following scores (IFEval or IFBench) were found for any of them.
- No LMArena results were found.
- MiniMax per-benchmark AA scores were not visible on the fetched page.

## Q3. Reasoning modes, quirks, and Fireworks API behaviour

### Takeaway
The three models differ sharply in how reasoning is controlled:
- **MiniMax M3.1 Flash:** thinking cannot be disabled; only effort can be lowered.
- **DeepSeek V4.1 Flash:** thinking (the default) and non-thinking modes, with a numeric effort setting on DeepSeek's own API.
- **GLM-5.3 Flash:** no documented toggle found.

On Fireworks, reasoning comes back in `reasoning_content` and must be passed back with tool-call turns for interleaved thinking.

### Cited Findings
- **Fireworks reasoning API** — [Fireworks docs](https://docs.fireworks.ai/guides/reasoning.md):
  - Reasoning is returned in `reasoning_content`, including streamed `delta.reasoning_content`. Some models instead place it in `<think>` tags or directly in `content`.
  - Effort is set via `reasoning_effort` (e.g. "low", "medium", "high"), or Anthropic-style `thinking: {type: "enabled", budget_tokens >= 1024}`. Sending both raises a validation error.
  - `chat_template_kwargs.enable_thinking` maps onto `reasoning_effort`.
- **Multi-turn tool calling on Fireworks** — [Fireworks docs](https://docs.fireworks.ai/guides/reasoning.md):
  - Pass back the prior assistant message including `reasoning_content`. If you build dicts by hand, you must add it yourself.
  - Interleaved thinking triggers when the last message has role "tool".
  - `reasoning_history="preserved"` keeps reasoning from earlier turns.
  - Model-specific examples cover MiniMax-M2 and GLM-4.7 (predecessors, not the target models). DeepSeek is not mentioned.
- **MiniMax M3.1 Flash thinking:**
  - Always-on reasoning with effort levels low/medium/high/xhigh/max; default is `max`. — [eesel](https://www.eesel.ai/blog/minimax-m3-1-flash)
  - `thinking: {"type":"disabled"}` or `effort: "none"` returns HTTP 400 "requires adaptive thinking". — [eesel](https://www.eesel.ai/blog/minimax-m3-1-flash)
  - On MiniMax's own API, effort goes in `reasoning_effort` (OpenAI-compatible endpoint) or `output_config.effort` (Anthropic-compatible endpoint). — [eesel](https://www.eesel.ai/blog/minimax-m3-1-flash)
  - Fireworks confirms "always on, effort adjustable low to max". — [Fireworks](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- **DeepSeek V4.1 Flash 1017 thinking** — [braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html):
  - Thinking is the default; non-thinking mode is supported.
  - On DeepSeek's API, `reasoning_effort` is an integer 1–100; benchmarks used 100.
  - FIM completion works only in non-thinking mode.
  - The 1017 update produces shorter outputs and finishes faster (no numbers given).
  - Recommended temperature 1.0, top_p 1.0.
  - The weights ship without a Jinja chat template; prompts are built with `encoding.py`. This matters for self-hosting, and possibly for provider tool-call parsing.
- **GLM-5.3 Flash:** no reasoning toggle, temperature recommendation or tool-call quirks were documented in the sources found. BenchLM classifies it as a "Reasoning" model. — [Fireworks](https://fireworks.ai/models/fireworks/glm-5p3-flash); [BenchLM](https://benchlm.ai/md/models/glm-5-3-flash.md)
- **Structured outputs:** DeepSeek V4.1 Flash supports JSON-schema structured outputs via `response_format` (OpenRouter) and JSON / structured outputs on Fireworks (llmreference). — [OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash); [llmreference](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)

### Inferences
- **MiniMax latency:** because its default is `max` effort, explicitly set `reasoning_effort="low"` or `"medium"` for latency-sensitive roles such as claimers, routers and summarizers. Never try to disable thinking.
- **DeepSeek non-thinking mode** is the natural fit for cheap, fast summarizer or formatter roles, and thinking mode for workers or verifiers. How non-thinking is selected on Fireworks (`reasoning_effort` value, or `thinking` disabled) was not confirmed.
- **Deep Agents subagent loops:** the `reasoning_content` round-trip is the main integration risk. If LangChain does not re-send it on the next request, interleaved reasoning is lost. That may degrade tool-call quality for always-reasoning models like MiniMax.

### Gaps
- How to disable or limit thinking for GLM-5.3 Flash on Fireworks was not found.
- How to select DeepSeek non-thinking mode on Fireworks specifically was not found.
- Parallel tool-call support or reliability for any of the three was not documented in the sources found.
- No reported tool-call parsing bugs specific to these three on Fireworks were found.

## Q4. Calling via LangChain / Deep Agents, and prompt caching

### Takeaway
Use `langchain-fireworks` (ChatFireworks) with `FIREWORKS_API_KEY`. A recent LangChain fix stores Fireworks `reasoning_content` in `AIMessage.additional_kwargs` and makes `bind_tools(strict=...)` actually apply. Prompt caching on Fireworks is automatic and priced as cached input; all three list a cached-input rate.

### Cited Findings
- **LangChain fix:** langchain PR #34343 (commit 6d447f89, fixing issues #34341 and #34342) made two changes to the Fireworks integration. — [semanticdiff of langchain commit](https://app.semanticdiff.com/gh/langchain-ai/langchain/commit/6d447f89d9ccd6fc5d9e0bcf3acdf0844316df02)
  - It extracts `reasoning_content` from Fireworks responses into `AIMessage.additional_kwargs`.
  - It passes `strict` from `bind_tools` kwargs into `convert_to_openai_tool`.
- **Access methods:** Fireworks pages list the Fireworks Python client, the REST API and the OpenAI Python client (OpenAI-compatible). — [Fireworks GLM page](https://fireworks.ai/models/fireworks/glm-5p3-flash); [Fireworks MiniMax page](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
- **Cached input prices** (per 1M tokens):
  - GLM: $0.03 — [Fireworks](https://fireworks.ai/models/fireworks/glm-5p3-flash)
  - MiniMax: $0.015 — [Fireworks](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)
  - DeepSeek: $0.006 — [llmreference](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)
- **Passing reasoning back:** the Fireworks reasoning guide requires prior `reasoning_content` to be passed back for multi-turn tool use. — [Fireworks docs](https://docs.fireworks.ai/guides/reasoning.md)

### Inferences
Suggested configuration (not tested):
```python
from langchain.chat_models import init_chat_model
# FIREWORKS_API_KEY in env; requires langchain-fireworks
glm = init_chat_model("fireworks:accounts/fireworks/models/glm-5p3-flash", temperature=...)
ds  = init_chat_model("fireworks:accounts/fireworks/models/deepseek-v4p1-flash-1017",
                      temperature=1.0, top_p=1.0, max_tokens=...)  # DeepSeek-recommended sampling
mm  = init_chat_model("fireworks:accounts/fireworks/models/minimax-m3p1-flash",
                      model_kwargs={"reasoning_effort": "medium"})  # never try to disable thinking
# Alternative: ChatOpenAI(base_url="https://api.fireworks.ai/inference/v1", api_key=os.environ["FIREWORKS_API_KEY"], model="accounts/fireworks/models/...")
#   ChatOpenAI generally drops reasoning_content, so prefer ChatFireworks for reasoning models.
```

- **Caching:** keep the system prompt and tool schemas byte-stable and at the front of the prompt, so prefix caching hits on every Deep Agents step.
- **Tool-call quality check:** test whether ChatFireworks re-sends `additional_kwargs["reasoning_content"]` on subsequent requests. If it does not, consider a small message-conversion patch or middleware for MiniMax and DeepSeek-thinking workers.
- **Tentative role mapping** (to validate empirically):

  | Role | Model | Setting | Reason |
  |---|---|---|---|
  | Planner / claimer | MiniMax M3.1 Flash | effort low–medium | Highest AA general intelligence |
  | Planner / claimer (alternative) | GLM-5.3 Flash | — | Cheapest structured tool caller |
  | Coding / terminal worker | DeepSeek V4.1 Flash 1017 | thinking | Best DeepSWE / Terminal-Bench |
  | Tool-heavy worker | GLM-5.3 Flash | — | Toolathlon 78.4, lowest output price |
  | Verifier | DeepSeek (thinking) or MiniMax (high effort) | — | — |
  | Summarizer | DeepSeek V4.1 Flash | non-thinking | Long context: AA-LCR 84, cheapest cache reads, 384K output |

### Gaps
- The installed langchain-fireworks version containing PR #34343, and its release date, were not confirmed.
- Whether ChatFireworks serialises `reasoning_content` back into requests was not confirmed.
- No deepagents-specific issue reports for these three models were found.
- Fireworks' prompt-caching mechanics (automatic prefix caching, minimum length, `prompt_cache_key` / session affinity) were not re-verified in this pass.
