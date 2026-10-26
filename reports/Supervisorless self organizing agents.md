# Replace the supervisor with a shared ledger

Build the framework as **identical peer agents running one prompt-defined cooperation loop over deterministic shared infrastructure**: a typed, append-only board (Agensh's FACT / OBSERVED / FAIL / CLAIM / PATCH_SUMMARY), atomic leased task claims, peer messages pushed into tool results, a cross-model review gate, and a code-level ledger that owns budget and termination. No LLM decides who does what or when the job is finished. Agensh shows that this design works. Removing the orchestrator and letting equal peers claim, verify, merge and publish raised mean ProgramBench pass rate from **19.31% with 1 agent to 28.78% with 128** ([Agensh paper](https://github.com/microsoft/Agensh/blob/main/agensh.pdf)). Agensh also shows the limits: gains were non-monotonic per task, every configuration was a single run, there were no ablations, and termination was purely an external wall clock. The broader literature adds two warnings that shape this design. Decentralized teams cost about **3.6× the turns of a single agent** and amplify errors **7.8×** without a verification step ([Kim et al.](https://arxiv.org/html/2512.08296v2)). And a 10-agent team only pays off on genuinely parallel work. LangChain Deep Agents 0.7.x has no peer primitive, but its `create_deep_agent` graph, `BaseStore`, `CompositeBackend`, custom tools and `wrap_tool_call` / `wrap_model_call` middleware are enough to build one ([deepagents 0.7.32](https://pypi.org/project/deepagents/0.7.32/)). The recommended model mapping is DeepSeek V4.1 Flash for hard reasoning and review, MiniMax M3.1 Flash for high-volume tool work, and GLM 5.3 Flash for long-context reading and integration. The recommended example is a 10-peer EU market-entry due-diligence dossier, evaluated against a single agent with the same budget before any claim of benefit is made.

## Agensh puts coordination in the prompt and the plumbing, not in a boss

Agensh's thesis is that orchestrator-worker harnesses such as Claude Code agent teams, Codex sub-agents and Copilot fleet are capped by "a central orchestrator's capacity to allocate tasks and coordinate workers" ([Agensh paper](https://github.com/microsoft/Agensh/blob/main/agensh.pdf)). It replaces the orchestrator with a five-step loop that every worker runs asynchronously: gather context, claim a sub-task as a `CLAIM` on the shared board, act, verify against acceptance criteria, merge and publish. The key design choice is that **the loop lives in the prompt, and the prompt is "exactly the same for each worker except for the worker ID"**. The runtime only transports events and context between turns ([Agensh paper](https://github.com/microsoft/Agensh/blob/main/agensh.pdf); [prompts/README](https://github.com/microsoft/Agensh/blob/main/prompts/README.md)). There are no persona templates. The paper reports that reviewer and integrator roles emerged at 32–1,024 agents, but it only gives trajectory anecdotes and never measures them.

Three infrastructure services carry the coordination. A Git workspace (Gitea) surfaces textual merge conflicts, and PRs merge with zero required approvals ([REPRODUCE.md](https://github.com/microsoft/Agensh/blob/main/REPRODUCE.md)). A chat interface (Mattermost) delivers low-priority channel messages at the start of each loop iteration and high-priority direct messages at the end of every infrastructure tool call. A DeLM-style board stores typed notes capped at **100 characters (300 for PATCH_SUMMARY)**, with a 2,000-entry recent window and a **1-hour claim TTL** ([shared_lessons.py](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)). The board also behaves in ways that matter for a port. A PATCH_SUMMARY with the same `delegation_id` replaces the author's earlier one. A matching FAIL invalidates it. A "verifier" marks entries `verified` only if the evidence text avoids weak words such as "should work" or "looks right". That check is purely textual and "does not execute the claimed tests" ([board-service/verifier.py](https://github.com/microsoft/Agensh/blob/main/board-service/verifier.py)). The interrupt mechanism is worth copying exactly: an `mcp-notice-shim` appends pending DMs and new peer notes to every tool result, so agents learn about collisions mid-turn without any process interruption ([mini-router README](https://github.com/microsoft/Agensh/blob/main/mini-router/README.md)).

Agensh also relies on several unglamorous liveness mechanisms that the cooperation loop alone does not provide. The task-handling rule is blunt: on `FAIL`, "stop if you are doing that thing"; on `FACT` / `OBSERVED`, "use it"; on a colliding `CLAIM`, "settle it by direct message" ([agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)). Sub-agent spawning is removed (`--excluded-tools=task --excluded-tools=list_agents`) so no worker can become a de facto supervisor ([entrypoint.sh](https://github.com/microsoft/Agensh/blob/main/agent/entrypoint.sh)). An idle watchdog nudges an agent after 600 s of inactivity. A post-turn check sends "ANYTHING TO PUBLISH?" when a turn wrote nothing to the board ([dispatcher.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/dispatcher.ts)). Activation is staggered (one agent every 30 s in the first hour) to reduce scope contention. **Termination is purely external**: at T−45 min the channel says "Stop dispatching new features… Land the open PRs", at T−5 min "Merge anything that is ready right now, then stop", and at 6 h every agent is killed and `main` is exported ([REPRODUCE.md](https://github.com/microsoft/Agensh/blob/main/REPRODUCE.md); [Agensh paper](https://github.com/microsoft/Agensh/blob/main/agensh.pdf)).

Read the evidence with care before carrying it over to a 10-agent business system. Per-task scaling is erratic: ctags fell from **25.82% to 18.47%** going from 1 to 8 agents, and gromacs stayed flat until 128 agents ([Agensh paper, Fig. 5](https://github.com/microsoft/Agensh/blob/main/agensh.pdf)). At 8 agents, which is closest to your scale, the mean gain was only **+1.37 pp** (19.31 → 20.68). The paper has no ablation of the board, DM priority or claim TTL, no orchestrator baseline at equal agent count, no seeds or error bars, and no token or dollar cost. It ran on GPT-5.6-sol at high effort with a 272k window, not on flash-tier open models ([REPRODUCE.md](https://github.com/microsoft/Agensh/blob/main/REPRODUCE.md)). The parts worth taking are the mechanisms (typed board, TTL claims, push-on-tool-return, publish nudges, external deadlines). The scaling curve should not be taken as a forecast.

## The literature says sparse boards and hard gates beat chatty meshes at ten agents

The most controlled topology study so far, 180 configurations across five architectures, three model families and four benchmarks, finds **no universally best topology** ([Kim et al.](https://arxiv.org/abs/2512.08296v1)). Centralized coordination gained **+80.8%** on parallelizable Finance-Agent. Decentralized peer debate gained **+9.2%** (against centralized +0.2%) on dynamic web navigation. On sequential PlanCraft, **every multi-agent variant lost 39–70%**. Coordination returns turn negative once the single-agent baseline exceeds about **45%**. Coordination turns grow as **T = 2.72 × (n + 0.5)^1.724**, and per-agent capacity becomes "prohibitively thin beyond 3–4 agents" under fixed budgets ([Kim et al. v2](https://arxiv.org/html/2512.08296v2)). Decentralized was not cheaper than centralized: overhead was **263% vs 285%**, and success per 1K tokens was **23.9 vs 21.5** against 67.7 for a single agent. The practical conclusion is that removing the supervisor saves nothing by itself. Savings come from **sparse communication**: a board plus targeted messages rather than all-to-all chat. Anthropic's experience points the same way. Token usage explained ~80% of BrowseComp variance, multi-agent systems burn about 15× chat tokens, and early versions failed by over-spawning and sending "too many updates" ([Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)).

Claude Code agent teams is the most production-tested set of supervisor-free execution primitives. It uses a shared task list with pending / in-progress / completed states, **dependency-gated claiming protected by file locking**, automatic unblocking of dependents, per-agent mailboxes, `TaskCompleted` hooks that can block completion, and `TeammateIdle` hooks that keep agents working ([Claude Code docs](https://code.claude.com/docs/en/agent-teams)). Its documented failures are the ones a peer system must prevent structurally. Agents sometimes "fail to mark tasks as completed, which blocks dependent tasks". Two agents editing one file overwrite each other. The suggested sizing is **3–5 teammates with 5–6 tasks each**. Blackboard research adds positive evidence for volunteer self-selection: agents that decide for themselves whether to answer a posted request gave up to **57% relative improvement** in end-to-end success over master-slave baselines ([Salemi et al.](https://arxiv.org/abs/2510.01285v2)). Contract-net bidding is poorly validated for LLMs because "LLM skills are qualitative and probabilistic", which makes bids hard to evaluate ([COALESCE](https://arxiv.org/pdf/2506.01900)). The framework should therefore use first-atomic-claim-wins, not auctions.

Verification is where peer systems win or lose. MAST's taxonomy of 1,600+ traces ranks **step repetition (15.7%)**, **reasoning-action mismatch (13.2%)**, **unawareness of termination conditions (12.4%)** and **disobeying the task spec (11.8%)** as the largest failure modes. Adding a high-level objective verification step to ChatDev raised success by **+15.6%**, the largest single intervention measured ([MAST](https://arxiv.org/html/2503.13657v3)). Kim et al. measure error amplification relative to a single agent at **17.2× for independent agents, 7.8× for decentralized and 4.4× for centralized**, and attribute the difference to the validation step in the centralized design ([Kim et al. v2](https://arxiv.org/html/2512.08296v2)). A supervisor-free framework therefore needs a **review gate at the board's commit point** to get centralized-level error containment without a central agent.

Model diversity helps in exactly the place where this design uses it. In decentralized runs, mixed-capability teams matched or beat homogeneous strong teams (Anthropic family 0.47 vs 0.37 on BrowseComp-Plus), and strong *workers* mattered more than a strong orchestrator ([Kim et al. v2](https://arxiv.org/html/2512.08296v2)). A diverse trio of mid-tier models reached **91% on GSM8K vs 82%** for three copies of one model ([Diversity of Thought](https://arxiv.org/html/2410.12853v1)). ReConcile found cross-family diversity "critical" to its gains of up to 11.4% ([ReConcile](https://arxiv.org/html/2309.13007v3)). There is a real counter-case. Debate can harm accuracy "particularly with heterogeneous LLM agents", because models abandon correct answers under peer pressure ([Wynn et al.](https://arxiv.org/html/2509.05396v1)), and vanilla debate often fails to beat majority vote ([Demystifying MAD](https://www.arxiv.org/pdf/2601.19921)). So diversity belongs in **independent review and independent first drafts**, not in open-ended debate.

## The framework is seven components, and only one of them is an LLM

The architecture keeps Agensh's split: the peer is a single-agent harness (Deep Agents), and everything organizational is deterministic infrastructure around it. The table maps each component to its Agensh origin and its Deep Agents 0.7.x realization. Pin `deepagents==0.7.32`, because the project ships breaking changes inside 0.x minors and releases several times a week ([PyPI history](https://pypi.org/project/deepagents/#history)).

| Component | Agensh origin | Literature adjustment | Deep Agents 0.7.x realization |
|---|---|---|---|
| **Peer** (×N, identical protocol) | Copilot CLI worker, same `agents.txt` per worker | Keep identical protocol; add an optional one-line "home lens" as a testable ablation | `create_deep_agent(model=ChatFireworks(...), system_prompt=PROTOCOL.format(agent_id=…), tools=[…], middleware=[…], backend=…, store=…, checkpointer=…, name=agent_id, context_schema=PeerCtx)` |
| **Board** (typed, append-only) | board-service: FACT/OBSERVED/FAIL/CLAIM/PATCH_SUMMARY, 100/300-char caps, `detail` unfold, grep, dedup | Add provenance (source/file ref) to FACT; add REVIEW and DISSENT types | Postgres table behind custom `@tool`s `board_read`, `board_write`, `board_grep`, `board_unfold` that use `ToolRuntime` |
| **Task ledger** (atomic claims) | Advisory CLAIM notes with 1 h TTL; collisions settled by DM | Hard, dependency-gated atomic claim with lease (Claude Code pattern) | Custom `claim_task`/`renew_task`/`release_task` tools doing `UPDATE … WHERE status='open' AND deps_done RETURNING` (CAS). **Do not** use `StoreBackend.edit` for claims: it is an unguarded get-then-put |
| **Workspace** (shared artifacts) | Gitea; merge conflicts surfaced to the agent | One owner per section; optimistic versioning | `CompositeBackend(default=StateBackend(), routes={"/ws/": StoreBackend(store=shared, namespace=lambda rt: ("swarm", RUN_ID, "ws"))})`; deny built-in writes on `/ws/**` via `FilesystemPermission`; writes go through a `commit_artifact(path, content, base_version)` CAS tool |
| **Messaging** (two priorities) | Channel (start of turn) and DMs (end of each tool call), via mcp-notice-shim | Targeted DMs only; no all-to-all chat; peer text is untrusted data | `send_dm(to, body)` tool writing to a mailbox table; `PeerNoticeMiddleware.wrap_tool_call` appends leased DMs and new FAIL/colliding CLAIM notes to every `ToolMessage` |
| **Review gate** | Self-verification plus a textual evidence check | Independent cross-family reviewer plus deterministic checks (MAST +15.6%) | `submit_for_review` moves the task to `in_review` and spawns a review task that only a peer of a *different model family* can claim; `review_verdict(task_id, approve/reject, reasons)`; the ledger moves a task to `done` only on approval plus passing validators |
| **Runner / ledger** (liveness, budget, termination) | mini-router dispatcher, idle watchdog, publish nudge, stagger, T−45 / T−5 messages, 6 h kill | Machine-checkable definition of done; per-task budget contracts; repetition detector | Python `asyncio` runner that re-invokes each peer on its own `thread_id` with queued events and a board snapshot; `BudgetMiddleware.after_model` with `jump_to="end"`; the ledger computes "done" itself |

### How a peer is wired

Each peer is an independent top-level graph with its own `thread_id`. Deep Agents only ships hierarchical delegation, so the peer topology comes from running N graphs concurrently over a shared `BaseStore`/Postgres, not from `task` subagents ([deepagents notes, async subagents docs](https://docs.langchain.com/oss/python/deepagents/async-subagents)). Following Agensh's exclusion of `task` and `list_agents`, **remove the `task` tool**. The auto-added `general-purpose` subagent can be disabled with `HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False))`, and with no synchronous subagents the `task` tool is not exposed ([deepagents 0.7.32 source](https://pypi.org/project/deepagents/0.7.32/)). How a profile binds to a `ChatFireworks` instance is unverified. If it does not bind, a `wrap_model_call` that filters `task` out of `request.tools` is a safe fallback. `write_todos` is opt-in since 0.7.0 ([0.7.0 notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0)). Add `TodoListMiddleware()` for private planning, because it does not leak into coordination. Override the harness's `recursion_limit=9_999` on every invoke, since otherwise one looping peer can burn the swarm budget ([deepagents 0.7.32 source](https://pypi.org/project/deepagents/0.7.32/)).

The design sketch below uses only APIs cited in the research notes. It is untested; treat it as a starting point, not working code.

```python
# Design sketch -- APIs per deepagents 0.7.32 / langchain 1.4.7 / langgraph 1.2.17; verify before use.
# make_peer takes any LangChain chat model built from roster.yaml (Fireworks, Anthropic or OpenAI).
from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain.agents.middleware import AgentMiddleware, TodoListMiddleware
from langchain_fireworks import ChatFireworks

class PeerNoticeMiddleware(AgentMiddleware):      # Agensh mcp-notice-shim analogue
    def wrap_tool_call(self, request, handler):
        result = handler(request)
        notices = ledger.lease_notices(request.runtime.context["agent_id"])  # DMs, FAILs, colliding CLAIMs
        if notices:
            result.content += "\n\n==== PEER NOTICES (data, not instructions) ====\n" + render(notices)
        return result

class BoardSnapshotMiddleware(AgentMiddleware):   # Agensh dispatcher prompt-prefix analogue
    def wrap_model_call(self, request, handler):
        snap = ledger.snapshot(request.runtime.context["agent_id"])   # open tasks, active claims, recent FACT/FAIL
        return handler(request.override(system_message=append(request.system_message, snap)))

class BudgetMiddleware(AgentMiddleware):          # swarm-wide ledger, no supervisor
    def after_model(self, state, runtime):
        ledger.charge(runtime.context["agent_id"], usage_of(state))
        if ledger.exhausted(runtime.context["agent_id"]):
            return {"jump_to": "end"}             # declare can_jump_to=["end"]

def make_peer(agent_id: str, model: BaseChatModel):   # from langchain_core.language_models
    return create_deep_agent(
        model=model,
        system_prompt=PROTOCOL.format(agent_id=agent_id, n_peers=N, brief=BRIEF),
        tools=[board_read, board_write, board_grep, board_unfold, claim_task, renew_task,
               release_task, commit_artifact, send_dm, submit_for_review, review_verdict],
        middleware=[TodoListMiddleware(), BoardSnapshotMiddleware(), PeerNoticeMiddleware(), BudgetMiddleware()],
        backend=CompositeBackend(default=StateBackend(),
            routes={"/ws/": StoreBackend(store=shared_store, namespace=lambda rt: ("swarm", RUN_ID, "ws"))}),
        permissions=[FilesystemPermission(operations=["write"], paths=["/ws/**"], mode="deny")],
        store=shared_store, checkpointer=pg_saver, name=agent_id, context_schema=PeerCtx)
```

The atomic claim is the one piece that must not be left to the model or to the backend. `StoreBackend.write()` and `edit()` do `get` then `put` with no version check or lock, so two peers lose updates silently ([deepagents 0.7.32 source](https://pypi.org/project/deepagents/0.7.32/)). Implement `claim_task` as a single SQL statement: `UPDATE tasks SET owner=$me, status='claimed', lease_until=now()+interval '20 min', version=version+1 WHERE id=$t AND status='open' AND NOT EXISTS (SELECT 1 FROM deps WHERE task=$t AND dep_status<>'done') RETURNING *`. Writing any board note on that task renews the lease. A sweeper returns expired leases to `open` and posts a FAIL-style note, which fixes Claude Code's "stuck task status" deadlock structurally. Keep Agensh's advisory CLAIM notes as well: they announce the *angle* a peer is pursuing inside a task (for example "testing the Germany-first scenario") and cost nothing. `ContextHubBackend` is the only built-in backend with optimistic-commit semantics and could replace the custom CAS tool for the workspace, at the price of a LangSmith dependency ([backends docs](https://docs.langchain.com/oss/python/deepagents/backends)).

Three more API traps. Namespace components must avoid `.`, because LangGraph's `BaseStore` rejects them even though deepagents' regex allows them, so never put model IDs or emails in namespaces ([langgraph-checkpoint](https://pypi.org/project/langgraph-checkpoint/)). `FilesystemPermission` applies only to built-in tools, and custom tools bypass it ([deepagents 0.7.32 source](https://pypi.org/project/deepagents/0.7.32/)). That is what lets `commit_artifact` be the only write path into `/ws/`. Finally, summarization thresholds come from the model profile's `max_input_tokens`, so confirm that profiles exist for these October-2026 Fireworks models or pass your own `SummarizationMiddleware` by name.

### The runner replaces the router, not the supervisor

The runner is Agensh's mini-router rewritten in Python. It starts peers staggered (one every 10–15 s is enough at N=10). It invokes each peer for a bounded episode (`recursion_limit` ≈ 60–120 steps) on a persistent `thread_id`. When an episode ends, it builds the next turn's input from queued events: review requests, DMs, "your lease expired", and the deadline messages. The runner never chooses tasks or reassigns work. It enforces the timer, the budget and the protocol. The "ANYTHING TO PUBLISH?" nudge carries over directly: compare the peer's latest board-note ID before and after the episode, and send the nudge when nothing was written ([dispatcher.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/dispatcher.ts)). Give each peer a stable Fireworks session-affinity key and a byte-identical protocol prefix, so the automatic `FireworksPromptCachingMiddleware` and Fireworks' prefix cache actually hit ([Fireworks prompt caching](https://docs.fireworks.ai/guides/prompt-caching); [0.7.0 notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0)). Keep timestamps out of the system prompt and put the volatile board snapshot last.

## Assign models by failure cost, and make every review cross-family

The three Fireworks models are close enough in capability and different enough in price and behavior to support a heterogeneous team. **All three requested IDs are confirmed on Fireworks**: `glm-5p3-flash`, `minimax-m3p1-flash` and `deepseek-v4p1-flash-1017`. The DeepSeek 1017 model is listed as Ready and serverless, with 1M context and function calling. Standard pricing is $0.30 / $0.006 cached / $1.20 per 1M tokens, and priority pricing is $0.375 / $0.0075 / $1.50 ([Fireworks DeepSeek 1017 page](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash-1017)). Pin the `-1017` ID explicitly. The version-tracking alias `deepseek-flash-latest` points to the base `deepseek-v4p1-flash`, not necessarily to the 1017 build ([Fireworks open models](https://docs.fireworks.ai/nexus/open-models.md)). Log the served `model` field on every call anyway, so traces record exactly which weights produced each result.

| | DeepSeek V4.1 Flash 1017 | MiniMax M3.1 Flash | GLM 5.3 Flash |
|---|---|---|---|
| Price in / cached / out per 1M | $0.30 / $0.006 / $1.20 (priority $0.375 / $0.0075 / $1.50) | $0.15 / $0.015 / $0.60 | $0.15 / $0.03 / $0.50 |
| Agentic signal | DeepSWE 77.0, AutomationBench 60.5 (vendor) | DeepSWE 73.7, AutomationBench-AA 62.8 (Fireworks) | DeepSWE 63.4, AutomationBench 48.8 (vendor) |
| Reasoning | thinking / non-thinking modes | always on, effort low→max | unconfirmed toggle |
| Best team role | analytical owner of hard sections, primary reviewer, recommendation drafter | high-volume tool worker: data-room queries, calculations, structured tables | long-document reader, integrator, consistency checker, editor |

Sources: [Fireworks GLM](https://fireworks.ai/models/fireworks/glm-5p3-flash), [Fireworks MiniMax](https://fireworks.ai/models/fireworks/minimax-m3p1-flash), [Fireworks DeepSeek 1017](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash-1017), [Pillitteri on 1017](https://pasqualepillitteri.it/en/news/24844/deepseek-releases-41-flash-1017-mit-weights-shorter-outputs), [BenchLM GLM](https://benchlm.ai/md/models/glm-5-3-flash.md). None of the three has published BFCL or tau2-bench numbers. The agentic scores are mostly vendor-reported on shifting harnesses. The independent Vals Index places DeepSeek 1017 at **56.58%** and MiniMax at **53.78%**, and MiniMax took **43 minutes per run** on Vals ([Vals DeepSeek](https://www.vals.ai/models/deepseek_deepseek-v4.1-flash-1017); [Vals MiniMax](https://www.vals.ai/models/minimax_MiniMax-M3.1-flash)). That latency is a real concern for an always-on reasoner in a timed swarm.

The mapping follows failure cost. DeepSeek goes where a wrong answer is expensive: financial modeling, regulatory analysis, the go/no-go recommendation, and most reviews. It has the strongest agentic numbers and the most output headroom, and its cached input at $0.006 makes re-reading the board cheap. MiniMax goes where volume dominates: near-DeepSeek agentic scores at half the price, run at `reasoning_effort="low"` and temperature ~0.2 with JSON-argument validation, following Fireworks' 0.0–0.3 tool-calling advice ([Fireworks function calling](https://docs.fireworks.ai/guides/function-calling)). GLM goes where context length and price dominate. Its 18B active parameters and hybrid long-context architecture make it the natural reader of interview transcripts and the integrator that loads the whole dossier at once.

Two rules come from the diversity literature. First, **a reviewer must never share the author's model family**, which places diversity at the commit point where it measurably contains errors. Second, **judgment calls use independent drafts from three families before any exchange**, capped at one exchange round with confidence-weighted voting and a retained DISSENT note. That captures the diversity gains while limiting the conformity drift Wynn et al. document. Heterogeneity also helps throughput: Fireworks rate limits apply per account *and per model*, so spreading peers over three models roughly triples serverless TPM headroom under the 6,000 RPM account cap ([Fireworks serverless rate limits](https://docs.fireworks.ai/serverless/rate-limits.md); [Fireworks quotas](https://docs.fireworks.ai/guides/quotas_usage/rate-limits)).

Three integration details decide whether reasoning survives the agent loop. Use `ChatFireworks` (`langchain-fireworks>=1.5.2` for `reasoning_effort`), not `ChatOpenAI` pointed at Fireworks, because Fireworks returns thinking in `reasoning_content` and requires it to be sent back on tool turns for interleaved reasoning ([LangChain ChatFireworks](https://docs.langchain.com/oss/python/integrations/chat/fireworks); [Fireworks reasoning](https://docs.fireworks.ai/guides/reasoning.md)). Verify empirically that `reasoning_content` round-trips through `AIMessage` in a Deep Agents tool loop, because nothing in the sources confirms it. Never use `response_format: json_schema` on reasoning roles, since it disables reasoning output ([Fireworks structured output](https://docs.fireworks.ai/structured-responses/structured-response-formatting)). Typed outputs should go through tool calls, which keep reasoning on. Finally, DeepSeek's card recommends temperature 1.0, which conflicts with Fireworks' low-temperature tool advice. Test both settings.

### Fireworks Nexus / Nexus Auto routing as an alternative to fixed models

Fireworks Nexus Auto offers one model ID, `auto`, at the OpenAI-compatible base `https://api.fireworks.ai/inference/v1`, and it also works on the Anthropic Messages and Responses APIs. It **chooses a model for each new user turn**, and that model serves the whole turn, tool calls included. The response's `model` field shows which model served it. Fireworks manages the set of models behind `auto`, and you cannot pick a custom set. The only restriction is `--providers fireworks`, which limits it to open models. Closed models need Anthropic or OpenAI provider keys. Nexus Auto is positioned for coding harnesses, and its earlier name, FireRouter, is retired ([Nexus Auto docs](https://docs.fireworks.ai/nexus/auto.md)). Nexus also provides version-tracking aliases: `glm-flash-latest` → `glm-5p3-flash`, `deepseek-flash-latest` → `deepseek-v4p1-flash`, and `minimax-latest` → `minimax-m3`. **`minimax-latest` is not `minimax-m3p1-flash`**, so do not use it as a stand-in ([Nexus open models](https://docs.fireworks.ai/nexus/open-models.md)).

The recommendation is to **pin the three exact model IDs per role** and not route through `auto` by default. Three reasons follow. Role diversity is a design requirement: the cross-family review rule needs a known family for both author and reviewer, and `auto` hides that choice. Reproducibility depends on knowing which weights ran. And the evaluation against the equal-budget single agent is only clean when the model is held fixed, since otherwise model variance and team effect are confounded. Routing granularity is a second problem. In a Deep Agents loop each episode invocation is one user turn, so Nexus Auto would pick one model per peer episode, and that pick would be opaque and nondeterministic. It is not the per-step, role-aware routing this design wants. Make the model provider **pluggable per role** in the roster config (`model: accounts/fireworks/models/… | auto | alias`) so that `auto` can run as an optional evaluation arm, or as the default for low-stakes worker roles where diversity and reproducibility matter less. If it is used, log the served `model` field into the ledger, so the reviewer-family rule can still be enforced after the fact.

### Decision: models are set per role in config, across five families

*Added after the initial report, on the user's decision.* The framework sets the model **per role in a roster config file**, using exact model IDs. `auto` is allowed only as an explicit value for an experiment. The pool grows from three Fireworks models to five models from five vendors, adding **OpenAI GPT-6 Luna** and **Anthropic Claude Haiku 5.5**. That gives the cross-family review rule five families to choose from instead of three.

| | GPT-6 Luna | Claude Haiku 5.5 |
|---|---|---|
| Model ID | `gpt-6-luna` (only snapshot) | `claude-haiku-5-5` |
| Positioning | "most efficient model for focused, high-volume tasks" | high-volume, latency-sensitive work; built to run as a sub-agent |
| Price in / cached / out per 1M | $0.10 / $0.01 / $0.50; prompts **>272K** cost 2× input and 1.5× output for the whole request | $0.10 / $0.01 / $0.50 for prompts **≤100K**; $0.50 / $0.05 / $2.50 above 100K |
| Context / max output | 1.05M (922K input) / 128K | 1M / 128K |
| Reasoning control | `reasoning_effort`: none, low, medium (default), high, xhigh, max | adaptive thinking, on by default; `effort` low–max (default medium) |
| Agentic signal (from Anthropic's launch page, so vendor-reported) | OSWorld 2.1 48.9%, Terminal-Bench 4.0 16.4%, GDPval-AA 1437 | OSWorld 2.1 72.4%, Terminal-Bench 4.0 39.2%, GDPval-AA 1620 |
| Default rate limits | Build tier 5,000 RPM / 2M TPM | per Anthropic org tier |

Sources: [OpenAI GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna), [OpenAI launch post](https://openai.com/index/introducing-gpt-6-sol-and-luna/), [Claude Haiku 5.5 page](https://www.anthropic.com/claude-haiku-5-5).

**Integration gotchas that decide whether these two work in a Deep Agents loop:**
- **GPT-6 Luna must use the Responses API.** OpenAI states that Chat Completions supports function calling only with `reasoning_effort` set to `none`. Use `ChatOpenAI(model="gpt-6-luna", use_responses_api=True, reasoning={"effort": "low"})`, or accept no reasoning on Chat Completions.
- **Haiku 5.5 has a price cliff at 100K tokens per request.** A peer's prompt includes its whole history plus the board snapshot, so it must stay under 100K or that request costs 5×. Trim aggressively for Haiku peers: a smaller board window and earlier summarization (set `SummarizationMiddleware` to trigger well below 100K).
- **Haiku 5.5 rejects sampling parameters and prefill.** Never pass `temperature`, `top_p` or `top_k`; any non-default value returns a 400. Don't pass a shared `temperature` from the roster defaults.
- **Haiku 5.5 thinking blocks must be passed back unchanged** with tool results. A forced `tool_choice` skips thinking, so use `auto`.
- **Haiku 5.5 safety classifiers can decline** with `stop_reason: "refusal"`, and there is no server-side fallback for Haiku. The runner should treat a refusal as a released lease plus a FAIL note, so a peer of another family can claim the task.
- **Check model profiles.** Confirm that LangChain profiles report `max_input_tokens` for both models; Deep Agents uses it to set summarization thresholds.
- `langchain-anthropic` is already a hard dependency of `deepagents` 0.7.32, so Haiku needs no extra package.

**Role mapping across the five models.** Haiku 5.5 posts the strongest agentic and knowledge-work numbers of the low-cost tier, at the lowest price. It becomes the **second analytical family and the main cross-family reviewer** for the open-model sections. Luna takes high-volume structured tool work beside MiniMax. Having two vendors per role tier means a lease freed by a refusal or rate limit can always go to another family.

| Tier | Models | Roles |
|---|---|---|
| Hard judgment | DeepSeek V4.1 Flash 1017, Claude Haiku 5.5 | financial model, regulatory analysis, go/no-go drafts, primary reviews |
| High-volume tool work | MiniMax M3.1 Flash, GPT-6 Luna | data-room queries, sizing tables, competitor pricing, GTM calculations |
| Long context and integration | GLM 5.3 Flash | interview transcripts, ops cost, integration and consistency editor |

**Roster config.** One YAML file defines providers, models and roles. A factory turns each entry into a LangChain chat model, so adding a sixth model is a config change, not a code change:

```yaml
# roster.yaml -- model per role; exact IDs only (auto allowed only as an experiment arm)
models:
  deepseek: {provider: fireworks, id: accounts/fireworks/models/deepseek-v4p1-flash-1017, family: deepseek, reasoning_effort: high}
  minimax:  {provider: fireworks, id: accounts/fireworks/models/minimax-m3p1-flash,       family: minimax,  reasoning_effort: low, temperature: 0.2}
  glm:      {provider: fireworks, id: accounts/fireworks/models/glm-5p3-flash,            family: zhipu}
  haiku:    {provider: anthropic, id: claude-haiku-5-5, family: anthropic, effort: medium, max_prompt_tokens: 90000}
  luna:     {provider: openai,    id: gpt-6-luna,       family: openai,    reasoning_effort: low, api: responses}
peers:
  - {id: P01, model: deepseek, lens: financial model and unit economics}
  - {id: P02, model: deepseek, lens: go/no-go recommendation and scenario logic}
  - {id: P03, model: haiku,    lens: regulatory and data-protection risk}
  - {id: P04, model: haiku,    lens: cross-section validation and review}
  - {id: P05, model: minimax,  lens: market sizing}
  - {id: P06, model: minimax,  lens: pricing and packaging}
  - {id: P07, model: luna,     lens: competitor landscape and price benchmarking}
  - {id: P08, model: luna,     lens: go-to-market and sales capacity}
  - {id: P09, model: glm,      lens: customer-interview evidence}
  - {id: P10, model: glm,      lens: operations cost and integration editing}
review_policy: {reviewer_family_must_differ: true}
judge: {provider: anthropic, id: claude-opus-5-5}   # must not be a team model; see evaluation
```

```python
# Design sketch -- the factory maps a roster entry to a chat model; verify parameter names in Phase 0.
from langchain_fireworks import ChatFireworks
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

def build_model(m: dict):
    if m["provider"] == "fireworks":
        return ChatFireworks(model=m["id"], **pick(m, "reasoning_effort", "temperature"))
    if m["provider"] == "anthropic":   # never pass temperature/top_p/top_k to Haiku 5.5
        return ChatAnthropic(model=m["id"], max_tokens=16000, thinking={"type": "adaptive"},
                             effort=m.get("effort", "medium"))
    if m["provider"] == "openai":      # Responses API: Chat Completions tools need reasoning_effort=none
        return ChatOpenAI(model=m["id"], use_responses_api=True,
                          reasoning={"effort": m.get("reasoning_effort", "low")})
    raise ValueError(f"unknown provider {m['provider']}")
```

The `effort` argument on `ChatAnthropic` and the `reasoning` argument on `ChatOpenAI` are unverified for these package versions. If either is rejected, pass the raw API field (`output_config.effort` for Anthropic) through the client's extra-body or model-kwargs option. The ledger stores `family` for every model, and the review gate checks it.

### Pinned stack: latest releases as of 2026-10-26

On the user's instruction, the framework targets the latest releases. PyPI lists these as current, and their declared constraints are compatible: deepagents 0.7.32 requires `langchain>=1.4.7`, `langchain-core>=1.7.0` and `langchain-anthropic>=1.7.6`, and langchain 1.4.7 requires `langgraph>=1.2.12,<1.3`.

```text
# requirements.txt -- exact pins; Python >=3.10,<4
deepagents==0.7.32              # 2026-10-23
langchain==1.4.7                # 2026-10-21
langchain-core==1.7.0           # 2026-10-22
langgraph==1.2.17               # 2026-10-24
langgraph-checkpoint-postgres==3.2.0
langchain-fireworks==1.7.1
langchain-anthropic==1.7.6
langchain-openai==1.7.2
```

Deep Agents ships 2–3 releases a week. Pin exact versions and upgrade on purpose, rerunning the Phase 1–3 tests each time, not by floating `>=`.

## Budgets, leases and a computed definition of done stop the known failure modes

Agensh's only termination rule is the clock, which suits a benchmark with hidden tests and fails a business user who needs a result once it is ready. The framework should keep Agensh's clock as the outer bound and add a **ledger-computed definition of done**. The run ends early when every required deliverable task is `done` (approved by a cross-family reviewer and passing deterministic validators) and the integration task's consistency check passes. No agent can declare the team finished, which removes MAST's premature-termination mode and the "lead stops early" failure Claude Code documents ([MAST](https://arxiv.org/html/2503.13657v3); [Claude Code docs](https://code.claude.com/docs/en/agent-teams)). Agents can still shut down individually. The run as a whole is a function of ledger state.

Budget control borrows the "Agent Contracts" idea: every task carries resource budgets, time limits and success criteria, not just an owner ([Agent Contracts](https://arxiv.org/html/2601.08815v2)). Use three layers. The swarm has a hard dollar ceiling and a wall clock. Each peer has a token allowance, enforced by `BudgetMiddleware` jumping to `end`. Each task has a step budget, after which the lease is released with a mandatory FAIL or partial PATCH_SUMMARY note. At 85% of either swarm budget, the runner broadcasts the equivalent of Agensh's T−45 message ("no new tasks; land and review what exists"). At 97% it sends the T−5 message ("commit ready artifacts, then stop"). For an illustrative run where each of 10 peers consumes 2M input and 200k output tokens at list prices, the arithmetic gives roughly **$5.40 before caching** for the original three-model roster (3 DeepSeek ≈ $2.52, 4 MiniMax ≈ $1.68, 3 GLM ≈ $1.20). The five-model roster comes to roughly **$4.50**: 2 DeepSeek ≈ $1.68, 2 MiniMax ≈ $0.84, 2 GLM ≈ $0.80, 2 Haiku ≈ $0.60 and 2 Luna ≈ $0.60. The Haiku figure assumes every request stays under 100K tokens. Cached-input discounts of 80–98% pull it lower. The point is that **model cost is small next to engineering time**, so the evaluation, not the API bill, should limit the number of runs.

| Failure mode (MAST share / source) | Structural control |
|---|---|
| Step repetition 15.7% | Per-peer repetition detector (embedding similarity of consecutive actions) that triggers release-and-nudge; Agensh rule "do not retry something recorded as FAIL" enforced by surfacing matching FAILs in tool results |
| Unaware of termination 12.4%, premature termination 6.2% | Ledger-computed definition of done; agents cannot end the run; deadline broadcasts at 85% / 97% |
| Disobey task spec 11.8% | Task schema with objective, output format, boundaries and acceptance criteria (Anthropic's delegation fields) and validators at the review gate |
| Incomplete / incorrect verification 8.2% / 9.1% | Cross-family reviewer plus deterministic checks (evidence present, citations resolve to data-room files, numbers reconcile across sections); Agensh's weak-word evidence filter as a cheap first pass |
| Duplicate work / scope contention | Atomic dependency-gated claim; advisory angle CLAIMs; staggered start; redundancy metric tracked (R > 0.50 correlates with failure) |
| Stuck claims / deadlock | Lease TTL with renewal on activity; sweeper reopens expired tasks; idle nudge after N idle minutes |
| Silent peers | Agensh "ANYTHING TO PUBLISH?" post-episode nudge |
| Conformity in judgment calls | Independent first drafts, one exchange round max, confidence-weighted vote, retained DISSENT |
| Prompt injection between peers | Peer text wrapped and labeled as data; no peer can grant permissions; tool allow-list per peer (Claude Code treats relayed approvals as untrusted) |
| Runaway cost | `recursion_limit` per episode, per-peer token allowance, swarm dollar ceiling, per-task step budget |

Sources for the table: [MAST](https://arxiv.org/html/2503.13657v3), [Kim et al. v2](https://arxiv.org/html/2512.08296v2), [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system), [Claude Code docs](https://code.claude.com/docs/en/agent-teams), [agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt), [verifier.py](https://github.com/microsoft/Agensh/blob/main/board-service/verifier.py). MAST also warns that prompt and role tweaks alone give "inconsistent" gains. That is why every control in the table lives in code or in the ledger, and the prompt only states the rules.

## Ten peers build an EU market-entry dossier from a sealed data room

The example should be one where multi-agent work has a fair chance. The task should be breadth-first and decomposable into parallel workstreams, not a sequential plan, since every MAS variant lost 39–70% on PlanCraft ([Kim et al. v2](https://arxiv.org/html/2512.08296v2)). It should also be gradable without guessing. The proposed problem: **"A mid-market B2B SaaS company must decide whether to enter the EU in the next 18 months, in which country order, at what price, and with what 3-year P&L and risk register."** The team works offline against a **sealed synthetic data room**: CRM pipeline exports, cost structure, competitor price sheets, 20 customer-interview transcripts, a regulatory memo pack and hiring-cost tables. This mirrors Agensh's offline, black-box setting. Each data-room variant has **planted facts** that serve as hidden tests, in the way ProgramBench tests serve Agensh: a regulatory blocker in one country, a churn anomaly in one segment, a competitor that undercuts on price, an arithmetic inconsistency between two source tables, and a misleading interview quote.

The runner seeds the board from a template, not from an LLM planner: the brief, the definition of done, and 12 required deliverable tasks with dependencies. Market sizing, competitors, pricing, GTM, customer evidence, regulatory, operations cost and financial model can run in parallel. The country sequence depends on sizing, regulatory and cost. The P&L depends on pricing, GTM and cost. The recommendation depends on all of them. Integration and the consistency check come last. Peers may add sub-tasks with `board_write`/`create_task` when they find gaps, as Agensh agents "open your own issues for the areas you take" ([agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)). This deterministic seeding keeps the system supervisor-free while avoiding the vague-delegation gaps Anthropic observed.

The roster below is the five-model version from the roster config: two peers per model family.

| Peer | Model | Home lens (soft first-claim affinity only) | Typical emergent duties |
|---|---|---|---|
| P01 | DeepSeek V4.1 Flash 1017 | Financial model and unit economics | Reviews pricing and GTM numbers |
| P02 | DeepSeek V4.1 Flash 1017 | Go/no-go recommendation and scenario logic | Reviews country sequence |
| P03 | Claude Haiku 5.5 | Regulatory and data-protection risk | Primary reviewer for MiniMax and Luna sections |
| P04 | Claude Haiku 5.5 | Cross-section validation and review | Reviews the P&L (cross-family vs P01) |
| P05 | MiniMax M3.1 Flash | Market sizing (TAM/SAM/SOM) from CRM and market tables | Computes tables for others |
| P06 | MiniMax M3.1 Flash | Pricing and packaging | Reviews GTM assumptions |
| P07 | GPT-6 Luna | Competitor landscape and price benchmarking | Flags undercut risk to P06 by DM |
| P08 | GPT-6 Luna | Go-to-market, channel and sales capacity | Reviews operations cost |
| P09 | GLM 5.3 Flash | Customer-interview evidence (long transcripts) | Supplies cited FACTs to every section |
| P10 | GLM 5.3 Flash | Operations cost and integration editing | Claims the integration task when it unblocks |

All ten get the same protocol prompt. The home lens is a single line that only biases the *first* claim. After that, any peer claims any unblocked task, which preserves Agensh's identical-peer property while giving a 10-peer team an initial spread without stagger tricks. Whether the lens helps is an open question, and it is a planned ablation. The go/no-go recommendation runs as a three-family judgment call (for example DeepSeek, Haiku and Luna, or whichever peers claim the three draft tasks), not as a single author's view. Long-context work stays on GLM and DeepSeek peers. Haiku peers should not claim tasks whose inputs exceed about 90K tokens, because of the 100K price cliff; the claim tool can enforce this from the roster's `max_prompt_tokens`. Note the tension with the guidance that recommends 3–5 agents ([Claude Code docs](https://code.claude.com/docs/en/agent-teams); [Kim et al. v2](https://arxiv.org/html/2512.08296v2)). Ten peers with 12+ seeded tasks sits near the recommended 5–6 tasks per agent only once sub-tasks appear. The evaluation must therefore test 3 and 5 peers, not assume 10 is better.

## A budget-matched single agent is the bar the swarm must clear

Agensh compares only against a single agent and never against an orchestrator at equal agent count. Kim et al. show that much multi-agent gain is simply more tokens spent, and Anthropic reports that token usage explains ~80% of performance variance ([Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)). The evaluation therefore has to hold budget fixed. Use **20 data-room variants**, following Anthropic's advice that about 20 realistic cases reveal the early large effects. Run **at least three seeds per condition** and report variance, which Agensh does not.

| Condition | Purpose |
|---|---|
| C0: single DeepSeek agent, same total $ and wall clock as C1, with an Agensh-style continuation hook ("there is always new work…") | Primary baseline; the swarm must beat this |
| C0-M, C0-G, C0-H, C0-L: single MiniMax / GLM / Haiku / Luna agents at equal budget | Separates the model effect from the team effect; a single Haiku agent is a strong cheap baseline |
| C1: 10 heterogeneous peers (target design) | Main treatment |
| C2: 10 homogeneous peers per model | Tests the diversity claim |
| C3: 3 and 5 heterogeneous peers at equal total budget | Tests Kim et al.'s 3–4-agent thinning claim |
| C4: orchestrator-worker with deepagents `task` subagents, same models and budget | The comparison Agensh omitted |
| Ablations on C1: no push notices, no review gate, same-family review, no home lens, claim TTL 5 vs 20 vs 60 min | Ablations Agensh never ran |

Scoring combines deterministic and judged measures. Deterministic: **planted-fact recall**, numeric consistency errors across sections, citations that resolve to data-room files, and whether the definition of done was met. Judged: a single rubric covering factual accuracy, citation accuracy, completeness, decision quality and clarity ([Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)). The judge must be a model **not on the team**, with human grading on at least a 25% sample. With Haiku 5.5 and Luna on the team, a larger model from the same vendor (for example Claude Opus 5.5 or GPT-6.1 Sol) may favour its smaller sibling. Rotate between two judges from different vendors and report how far they agree. Efficiency metrics follow Kim et al.: dollars, tokens, wall clock, turns, overhead vs C0, success per 1K tokens, error amplification, redundancy and message density. Coordination diagnostics follow MAST: failure modes per trace via its LLM-judge annotator, duplicate-claim rate, review reject rate, lease expiries and termination correctness ([MAST](https://arxiv.org/html/2503.13657v3); [Kim et al. v2](https://arxiv.org/html/2512.08296v2)). The decision rule is fixed in advance. Adopt the swarm only if C1 beats C0 on rubric score and planted-fact recall at equal budget beyond seed variance, or matches C0 at materially lower wall clock when latency is the business driver. If C0 already scores above ~45%, expect the swarm to lose ([Kim et al.](https://arxiv.org/abs/2512.08296v1)).

### Phased build plan

| Phase | Scope | Exit criterion |
|---|---|---|
| 0. Model verification (week 1) | Install the pinned stack; smoke-test all five pinned IDs from `roster.yaml` and log the served `model` field; confirm Luna tool calls on the Responses API and that Haiku thinking blocks round-trip; 100-task tool-call reliability test per model (malformed args, parallel calls); confirm `reasoning_content` round-trip in a Deep Agents loop; check model profiles' `max_input_tokens`; read rate-limit headers | Pass/fail table per model; final role mapping |
| 1. Substrate (weeks 1–2) | Postgres board, task ledger with CAS claims and leases, mailbox, artifact store with versions; race tests with 20 concurrent claimers | Zero double-claims or lost writes under stress |
| 2. Peer harness (weeks 2–3) | `make_peer` factory, four middlewares, `task` tool removed, recursion and budget limits, LangSmith tracing per `name`/`thread_id` | One peer completes a seeded task end to end |
| 3. Swarm runtime (weeks 3–4) | Async runner, stagger, episode loop, idle / publish nudges, deadline broadcasts, review gate, definition-of-done evaluator; 3 peers on a toy dossier | Run terminates on done or budget with no manual intervention |
| 4. Business example (weeks 4–6) | Data-room generator with planted facts (20 variants); 12-task template; 10-peer roster config | C1 completes all 20 variants within budget |
| 5. Evaluation (weeks 6–8) | Conditions C0–C4 and ablations, 3 seeds each; MAST tagging; human grading sample | Go/no-go decision on the swarm vs single agent |
| 6. Packaging (weeks 8–9) | YAML config for roster, models, budgets, task templates, validators, board types; plug-in validator and tool interfaces; pinned versions | Second domain (for example a supplier-risk review) runs from config alone |

### Risks and unverified items

The largest risk is that the swarm does not beat the single agent. Kim et al.'s overhead numbers, Agensh's +1.37 pp at 8 agents and MAST's long list of coordination failures all point that way for tightly coupled work. Phase 5 exists to find out cheaply. Second is substrate churn: Deep Agents ships several patches a week, with breaking 0.x minors. There is no official peer or blackboard pattern, and the docs give no guidance on concurrent writers ([deepagents notes](https://docs.langchain.com/oss/python/deepagents/backends)). Pin versions and keep coordination in your own tables, not in deepagents internals. Third is model behavior: no independent tool-call reliability data exists for any of the three models, MiniMax's always-on reasoning may make it the latency bottleneck, and silently dropped `reasoning_content` would degrade quality without any error. Fourth, peer messages are an injection surface with no central filter.

The `deepseek-v4p1-flash-1017` ID is now confirmed on Fireworks, and pinning it removes the question of which weights the base ID or the `deepseek-flash-latest` alias serves. Items flagged as **unverified** in the sources: Fireworks-published max output for all three models. Parallel tool-call support per model. Whether GLM 5.3 Flash exposes a thinking toggle. DeepSeek's parameter count (552B vs 763B) and a conflicting third-party price ($0.22/$0.66 vs Fireworks' $0.30/$1.20). How a `HarnessProfile` binds to a `ChatFireworks` instance. Whether `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware` exist in langchain 1.4.7, which is why the custom `BudgetMiddleware` is used. The helper for appending to `ModelRequest.system_message`, since deepagents' own helper is private. Whether `init_chat_model("fireworks:…")` resolves cleanly. How to pass the Fireworks session-affinity `user`/header through `ChatFireworks`. `langgraph-swarm` 0.1.0 compatibility with deep-agent graphs. The `effort` argument on `ChatAnthropic` 1.7.6 and the `reasoning` argument on `ChatOpenAI` 1.7.2. Parallel tool calls for GPT-6 Luna, which its model page does not mention. The Haiku-vs-Luna benchmark figures come from Anthropic's own launch page and have not been checked independently. The secondary claim that 0.7 cut base prompt tokens by ~65%. Agensh's emergent-role claims are qualitative anecdotes, and the README's GPT-6.1-sol result (56.19% → 79.59% on pandoc) is not in the paper ([Agensh README](https://github.com/microsoft/Agensh/blob/main/README.md)).

## Conclusion

The research changes what "supervisorless" should mean in practice. Agensh's real lesson is that organization can be moved out of any agent and into infrastructure: a typed board, claims that expire, notices pushed into tool results, nudges, and a clock. A 10-agent business system needs more of that infrastructure than Agensh's coding benchmark did, not less. ProgramBench supplied hidden tests and a fixed deadline. A business dossier needs a computed definition of done and a cross-family review gate to provide the same error containment that the literature credits to centralized validators. The resulting system has no boss, but its ledger is strict, and that strictness is what lets identical peers on cheap flash models self-organize safely.

The second implication concerns where the value is. The three Fireworks models cost a few dollars per 10-agent run, so the constraint is not inference spend but evidence. Agensh's headline gain appeared at scales of 32 to 1,024 agents and was nearly flat at 8. The most valuable thing this project can produce is therefore a properly controlled comparison: 1 vs 3 vs 5 vs 10 peers, heterogeneous vs homogeneous, peer vs orchestrator, all at equal budget. If the swarm wins there, the YAML-configured framework is reusable across domains. If it loses, the same substrate still yields a strong single-agent harness with a board-backed review loop, which is a useful result either way.
