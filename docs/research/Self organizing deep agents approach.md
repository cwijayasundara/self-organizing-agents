# Build peer teams on a verified blackboard

Agensh does not show you how to build a supervisor-free team; it shows you how to make one live. Its "self-organization" is a prompt contract running on a thin shared log: typed 100-character gists, advisory claims that expire after an hour, direct messages that interrupt a peer mid-turn, and nudges to publish. There is **no task queue, no lock, no CI gate and no completion check** ([Repo](https://github.com/microsoft/Agensh)). The recommended approach for CK is therefore a hybrid. Keep Agensh's behavioural contract: identical peer prompts, typed capped gists, interrupt-priority DMs, a forced-publish nudge and idle and deadline watchdogs. Replace its weak parts with mechanisms from DeLM: atomic claims on a dependency-aware queue, gists verified when they are admitted, a test or rubric gate before anything merges, and an explicit termination predicate. DeLM is the only 2026 supervisor-free design that has beaten a centralized orchestrator on both quality and cost ([arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)). On deepagents 0.7.32 this becomes N independent `create_deep_agent` graphs with no `task` tool. They share a `StoreBackend` route, use custom claim, board and mail tools, and run under two custom middlewares and a small async runner. The three Fireworks models are mixed deliberately: DeepSeek V4.1 Flash for the heavy reasoning, GLM-5.3 Flash for cheap tool-calling breadth, and MiniMax M3.1 Flash at medium effort for cross-model verification. The showcase is a 10-peer due-diligence dossier, with DABstep as a negative control. Be clear-eyed about the payoff: Agensh's own gain from 1 to 8 agents was **+1.37 points** ([Paper](https://arxiv.org/abs/2609.26781)). At ≤10 agents the realistic wins are time-to-quality, breadth and cost per verified item, not a step change in final quality. The evaluation must be compute-matched or it will mislead.

## Agensh's mechanism is a prompt contract on a gist log

The README and paper describe workers that "self-organize sub-task discovery and allocation" and develop emergent roles such as reviewers and integrators ([Paper §2.1](https://arxiv.org/abs/2609.26781)). The code is much thinner. The so-called board-service is a single MySQL table of typed notes: `FACT`, `OBSERVED`, `FAIL`, `CLAIM` and `PATCH_SUMMARY`. Content is capped at **100 characters, or 300 for patch summaries**, and longer evidence goes into an optional `detail` field that peers can expand on demand with `board_unfold` ([shared_lessons.py](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)). A `CLAIM` is just a note with a one-hour TTL. The code has no uniqueness check, no owner check and no conflict rejection, so two agents can claim the same area. Collisions are settled socially, by prompting agents to DM each other, and git merge conflicts catch whatever slips through ([board-service/main.py](https://github.com/microsoft/Agensh/blob/main/board-service/main.py)). Decomposition belongs to no one. The launcher opens one Gitea issue "with no assignee; peers self-select." Each worker probes the reference binary for unbuilt behaviour, announces a claim, builds, checks against the reference, **merges to `main` itself**, and posts a patch summary ([pbench_run.sh](https://github.com/microsoft/Agensh/blob/main/scripts/pbench_run.sh), [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)).

Agensh's verifier is a regular expression. It rejects a patch summary whose `evidence=` starts with "tbd", "should work" or "looks right", and tags it `verified` when the text says "passed" or "now returns". The module says so itself: "Verification is a deterministic text check; it does not execute the claimed tests" ([verifier.py](https://github.com/microsoft/Agensh/blob/main/board-service/verifier.py)). Nothing protects branches and no CI runs. Only merged `main` is graded ([bootstrap.sh](https://github.com/microsoft/Agensh/blob/main/docker/bootstrap/bootstrap.sh)). Nothing detects completion either. Runs last a fixed **6 hours**, with deadline broadcasts at T−45m and T−5m. An idle watchdog DMs any worker that has been silent for 600 seconds with an empty inbox: "There is always new work" ([idle.txt](https://github.com/microsoft/Agensh/blob/main/prompts/idle.txt)). A 20-minute silence watchdog force-closes stuck sessions ([acp_socket_channel.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/acp_socket_channel.ts)).

Three pieces of plumbing do carry real weight. First, a **turn-start delta**: at the start of each turn, every agent receives only the gists it has not yet seen, tracked by a per-agent cursor, wrapped in "Read them BEFORE acting: do not re-derive a FACT… do not repeat a path recorded as FAIL" ([board_client.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/board_client.ts)). Second, a **mid-turn notice shim** appends pending DMs and new peer gists to the result of each infrastructure tool call, so a peer's `FAIL` reaches an agent deep in a long turn ([mcp-notice-shim.cjs](https://github.com/microsoft/Agensh/blob/main/mini-router/mcp-notice-shim.cjs)). Third, a **forced-publish nudge** fires whenever a turn produced no gist ([dispatcher.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/dispatcher.ts)). Every worker gets a byte-identical prompt, "N coders, all equal," and Copilot's subagent tool is disabled, so no worker can turn itself into a supervisor ([agent/entrypoint.sh](https://github.com/microsoft/Agensh/blob/main/agent/entrypoint.sh)). The mini-router is not a model gateway. It is a per-worker event queue that serializes Gitea and Mattermost events into turns.

The evidence matters most at CK's scale. The paper reports team sizes of 1, 8, 32 and 128 only. The mean pass rate rises from **19.31% to 20.68% at 8 agents**, then to 26.52% at 32 and 28.78% at 128 ([Paper §3.1](https://arxiv.org/abs/2609.26781)). The paper includes no ablations: nothing without the board, nothing without the DMs, and no orchestrator baseline. It reports no token or cost figures, one run per configuration, and one benchmark type that has a perfect oracle (a reference binary). The emergent reviewer and integrator roles appear only at 32 agents and above. At 8 agents the trajectories show interface agreements and renegotiated claims, nothing more. The one encouraging small-team signal is latency: on pandoc, 8 agents passed 30% at 90 minutes, while a single agent never reached that within two hours.

The table below converts this into keep, drop and add decisions. The reasons come from the evidence, not from taste.

| Decision | Mechanism | Reason |
|---|---|---|
| **Keep** | Identical peer prompt, no subagent tool | Removes the supervisor by construction; role diversity comes from models and claims, not prompts |
| **Keep** | Typed, capped gists with `FAIL` as first-class | Compression without LLM summarization. DeLM attributes its halved cost to sharing compact gists instead of raw traces ([arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)) |
| **Keep** | Turn-start delta plus mid-turn notices on tool results | The only way a long-running peer sees a refutation in time |
| **Keep** | Publish nudge, idle nudge, stuck-turn timeout, staggered start | Event-driven agents otherwise go quiet or spin |
| **Drop** | Gitea, Mattermost, MySQL, ACP router, secret-service | At ≤10 agents an in-process bus, one Postgres and LangGraph threads do the same job |
| **Drop** | TTL-only advisory claims as the sole allocation mechanism | MAST's most frequent failure is step repetition (15.7%) ([arXiv 2503.13657](https://arxiv.org/html/2503.13657v3)), and an atomic claim is cheap at this scale |
| **Drop** | Burn-the-budget termination | Business tasks have a finish line. "Unaware of stopping conditions" accounts for 12.4% of MAST failures |
| **Add** | DeLM atomic `reserve`/`claim`/`done`, one item per agent, dependency DAG | DeLM's queue rejects a second claim and lets only the holder complete ([DeLM shared_context.py](https://github.com/yuzhenmao/DeLM/blob/main/board/shared_context.py)) |
| **Add** | Gists verified at admission against evidence | Independent multi-agent systems amplify errors **17.2×** versus 4.4× when outputs are validated ([arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)) |
| **Add** | Test or rubric gate before merge, with cross-author and cross-model verify items | An objective-level verification step gave +15.6% in MAST's ChatDev intervention |
| **Add** | A "gap oracle" (acceptance checklist) and an explicit completion predicate | Agensh decomposes against a reference binary; business tasks need an equivalent objective list |
| **Add** | `DECISION` gist type for interface or constraint choices | Targets Cognition's "actions carry implicit decisions" failure ([Cognition](https://cognition.com/blog/dont-build-multi-agents)) |

The pattern across the prior art is that "decentralized" systems almost always keep a lightweight non-LLM arbiter. Examples are LbMAS's control unit, whose removal nearly tripled tokens from 4.72M to 13.9M ([arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)), and DeLM's "last finisher decides." The real design choice is **where state and verification live**, not whether any coordination code exists. The framework below keeps every LLM a peer and puts the arbitration in deterministic code.

## Ten deepagents graphs share one store, three custom services and two middlewares

Deep Agents ships supervisor/subagent and handoff patterns. It has no concurrent peer team with a shared task board, and `langgraph-swarm` has not shipped since 0.1.0 in December 2025 ([LangChain multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent), [PyPI langgraph-swarm](https://pypi.org/project/langgraph-swarm/)). The library does not stand in the way, though. `create_deep_agent` returns an ordinary compiled LangGraph graph. Each peer therefore gets its own model, its own `thread_id` on a checkpointer, and a shared `store` ([PyPI deepagents 0.7.32](https://pypi.org/project/deepagents/0.7.32/)). Pin **`deepagents==0.7.32`**: the 0.7 line shipped about 25 patches between August and October, and the pieces you will lean on (RubricMiddleware, async-subagent notifications) are marked beta.

The architecture has six components. The first is the **shared context log**: Agensh's gist store, with type caps, per-(author, `delegation_id`) replacement of patch summaries, exact and anchor-based dedup, a per-agent cursor, `grep` over full history, and lazy `unfold`. The second is the **task board**: a Postgres table of work items with a dependency list, a status machine (`blocked → ready → claimed → submitted → verified | rejected`), a holder, a lease, and a `kind` of either `work` or `verify`. The third is the **mailbox**, with two priorities. DMs are delivered mid-turn on the next tool result. Channel posts queue for the next turn start, capped at 32 inline, mirroring Agensh's listener ([group_messages.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/group_messages.ts)). The fourth is the **workspace**: private scratch on `StateBackend`, shared `/team/` on `StoreBackend`, and a protected `/team/main/` that only the gate can write. For code tasks, add a git worktree per peer on a shared sandbox. The fifth is the **verifier gate**. On `submit`, it runs an executable check (tests, schema validation, a citation resolver) and creates a `verify` item that the author cannot claim. A different model family should claim it where possible. Only a passing verify promotes the artifact into `/team/main/`. The sixth is **watchdogs and termination**: a staggered start, an idle nudge, a stuck-turn timeout, lease reclaim, deadline broadcasts, a quiescence detector, and a completion predicate evaluated by deterministic code after each turn.

Each component maps onto deepagents in a specific way:

| Concern | Deepagents primitive to use | What must be custom-built |
|---|---|---|
| Peer runtime | `create_deep_agent(model=..., name=..., checkpointer=..., store=...)` per peer | Runner loop: deepagents ends a run when the model stops calling tools, so peers need re-invocation on events |
| No supervisor | Harness profile with `GeneralPurposeSubagentProfile(enabled=False)` and no sync subagents, so the `task` tool is not exposed ([source](https://pypi.org/project/deepagents/0.7.32/)) | Nothing |
| Shared files | `CompositeBackend(default=StateBackend(), routes={"/team/": StoreBackend(store=shared, namespace=...)})` ([backends](https://docs.langchain.com/oss/python/deepagents/backends.md)) | Nothing for files; but writes are last-writer-wins |
| Protecting shared state | `FilesystemPermission(..., mode="deny")` on `/team/main/**` and `/team/board/**` | Gate tool that writes `main` |
| Atomic claims | None. `StoreBackend.awrite` is read-then-put with no version check ([source](https://pypi.org/project/deepagents/0.7.32/)) | Postgres `UPDATE … WHERE status='ready' … RETURNING` behind `task_claim` |
| Board and mail | `tools=` (additive) | `board_*`, `task_*`, `send_dm`, `post_channel`, `submit` tools and their services |
| Turn-start delta | `before_agent` hook returning a `messages` update | Cursor-advancing snapshot renderer |
| Mid-turn notices | `wrap_tool_call` / `awrap_tool_call` ([custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)) | Lease-protected pending-notice drain |
| Self-check before submit | `RubricMiddleware` (beta; grader sub-agent, `max_iterations=3`) | Rubric per task kind |
| Prompt caching | `FireworksPromptCachingMiddleware`, auto-added when `langchain-fireworks` is installed | Keeping the prefix byte-stable (see below) |
| Tracing | LangSmith via `RunnableConfig` tags and metadata | Team-level dashboard from board lifecycle data |

One implementation detail matters more than it looks. The deepagents research suggests injecting team context by rewriting the end of the system message in `wrap_model_call`. Do not do this with Fireworks models. The system message sits in front of the whole conversation, so changing it on every call breaks the cached prefix for every message after it. You would then pay full input price on a context that grows with every step. With cached input at **$0.006–$0.03 per million tokens** versus $0.15–$0.30 uncached, that is a 10–50× penalty on the dominant cost line ([Fireworks GLM](https://fireworks.ai/models/fireworks/glm-5p3-flash), [llmreference DeepSeek](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)). Instead, copy Agensh's two append-only paths. Put the delta in a new message at turn start (`before_agent`), and append notices to tool results (`wrap_tool_call`). Both only ever add to the end of the transcript. Do not inject a `HumanMessage` mid-turn through `before_model` either: Fireworks triggers interleaved thinking when the last message has role `tool` ([Fireworks reasoning](https://docs.fireworks.ai/guides/reasoning.md)), and a user message wedged between tool calls breaks that pattern.

The sketch below shows the shape of the framework. **It is an illustrative sketch, not tested code.** The deepagents calls follow the 0.7.32 signatures in the research notes, but import paths for backends and harness profiles, and everything in `peerteam.*`, are assumptions to verify in Phase 0.

```python
# SKETCH ONLY — untested; verify imports and HarnessProfile registration against deepagents==0.7.32
import asyncio
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from deepagents import (create_deep_agent, FilesystemPermission, HarnessProfile,
                        GeneralPurposeSubagentProfile, register_harness_profile)
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from peerteam.services import Team          # board + tasks + mail + gate, backed by Postgres
from peerteam.tools import team_tools       # board_write/read/grep/unfold, task_reserve/claim/release,
                                            # submit, send_dm, post_channel  (all call Team services)
from peerteam.models import fireworks_model # wraps init_chat_model("fireworks:...") + role kwargs
from peerteam.prompts import PEER_PROMPT, IDLE_PROMPT, PUBLISH_NUDGE

register_harness_profile("peer", HarnessProfile(          # exact signature: verify
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))

class TurnStartDelta(AgentMiddleware):
    """Agensh turn-start path: unread gists + queued channel posts, appended as one new message."""
    def __init__(self, team: Team, me: str): self.team, self.me = team, me
    async def abefore_agent(self, state, runtime):
        delta = await self.team.board.delta(self.me)        # advances this agent's cursor
        posts = await self.team.mail.drain(self.me, priority="channel", limit=32)
        mine  = await self.team.tasks.held_by(self.me)
        if not (delta or posts or mine):
            return None
        return {"messages": [HumanMessage(self.team.render_shared_context(delta, posts, mine))]}

class PeerNotices(AgentMiddleware):
    """Agensh notice-shim path: DMs and new FAIL/DECISION/colliding-CLAIM gists ride on every tool result."""
    def __init__(self, team: Team, me: str): self.team, self.me = team, me
    async def awrap_tool_call(self, request, handler):
        result = await handler(request)
        notes = await self.team.pending_urgent(self.me)      # lease-protected, delivered once
        if notes and isinstance(result, ToolMessage):
            result.content = f"{result.content}\n\n==== PEER NOTICES ====\n{notes}"
        return result

def make_peer(team: Team, name: str, model_key: str, cfg):
    shared = StoreBackend(store=team.store, namespace=lambda _rt: ("team", cfg.run_id))
    return create_deep_agent(
        model=fireworks_model(cfg.models[model_key]),
        name=name,
        system_prompt=PEER_PROMPT.format(n=cfg.team.size),   # byte-identical for every peer
        tools=team_tools(team, name),
        backend=CompositeBackend(default=StateBackend(), routes={"/team/": shared}),
        permissions=[FilesystemPermission(operations=["write", "edit", "delete"],
                                          paths=["/team/main/**", "/team/board/**"], mode="deny")],
        middleware=[TurnStartDelta(team, name), PeerNotices(team, name)],
        checkpointer=team.checkpointer, store=team.store,
    )

async def run_peer(team: Team, name: str, graph, cfg):
    conf = {"configurable": {"thread_id": f"{cfg.run_id}-{name}"},
            "tags": [cfg.run_id, name], "metadata": {"team_run": cfg.run_id}}
    await asyncio.sleep(team.stagger_delay(name))
    while not await team.is_complete():
        trigger = await team.mail.wait(name, timeout=cfg.team.idle_after_s)   # DM/channel event, or None
        before = await team.board.last_gist_id(name)
        try:
            await asyncio.wait_for(graph.ainvoke({"messages": [HumanMessage(trigger or IDLE_PROMPT)]},
                                                 config=conf), timeout=cfg.team.stuck_turn_s)
        except asyncio.TimeoutError:
            await team.tasks.release_expired(holder=name)
        if await team.board.last_gist_id(name) == before:                      # Agensh publish nudge
            await graph.ainvoke({"messages": [HumanMessage(PUBLISH_NUDGE)]}, config=conf)
        await team.evaluate_termination(last_actor=name)    # deterministic: DAG + gate + quiescence + budget

async def run_team(cfg):
    team = await Team.open(cfg)
    await team.seed_from_gap_oracle(cfg.team.goal_file)    # acceptance checklist -> ready work items
    peers = {p.name: make_peer(team, p.name, p.model, cfg) for p in cfg.peers}
    await asyncio.gather(*(run_peer(team, n, g, cfg) for n, g in peers.items()))
    return await team.export_main()
```

The claim primitive is the one piece where correctness matters. It is a single SQL statement that enforces "ready, unheld, and you hold nothing else," modelled on DeLM's `claim` returning `won=False` and its one-item-per-agent rule:

```sql
-- SKETCH: atomic claim with lease; returns 0 rows if lost
UPDATE tasks SET status='claimed', holder=:agent, lease_until=now() + make_interval(secs => :lease_s)
WHERE id=:task_id AND status='ready'
  AND (kind <> 'verify' OR author <> :agent)
  AND NOT EXISTS (SELECT 1 FROM tasks WHERE holder=:agent AND status='claimed')
RETURNING id;
```

Peers can still create work. `task_reserve(subject, depends_on)` normalizes the subject and inserts a row with `ON CONFLICT DO NOTHING`, so decomposition stays emergent while duplicates become impossible. That is DeLM's `reserve` semantics. Agensh's advisory `CLAIM` gist survives as a free-text "what angle I'm taking" signal on top of the hard claim.

The package layout keeps the coordination services independent of deepagents. That lets them sit behind CK's existing config-driven platform as a plugin, and also be exposed over MCP later.

```
peerteam/
  config/schema.py            # pydantic models for the YAML below
  services/
    board.py                  # gists: caps, types, dedup, cursor delta, grep, unfold, lifecycle JSONL
    tasks.py                  # DAG, reserve/claim/release/submit, leases, verify-item spawning
    mail.py                   # DM (interrupt) + channel (turn-start) queues, spill-to-file >32
    gate.py                   # executable checks + rubric grading + promote to /team/main
    termination.py            # completion predicate, quiescence, budgets, deadline broadcasts
    team.py                   # facade used by tools/middleware/runner
  agents/
    factory.py                # make_peer(): create_deep_agent + backend + permissions
    middleware/turn_delta.py  # before_agent delta
    middleware/notices.py     # wrap_tool_call notices
    middleware/reasoning.py   # reasoning_content round-trip guard (only if Phase 0 shows it is needed)
    middleware/budget.py      # per-peer token ledger, hard stop
    tools/                    # board_*, task_*, send_dm, post_channel, submit
    prompts/                  # peer.md (identical), idle.md, publish_nudge.md, deadline_*.md
  models/fireworks.py         # model registry + role kwargs
  runtime/runner.py           # run_peer / run_team, stagger, watchdogs
  eval/                       # arms (single, sc-ensemble, supervisor, self-org), judges, MAST labeller, metrics
  showcases/dd_dossier/  showcases/uw_triage/  showcases/dabstep_control/
```

The configuration schema below makes the coordination policy itself configurable. That matters because the evaluation should ablate exactly these switches.

```yaml
run_id: dd-acme-0001
team:
  size: 10
  goal_file: showcases/dd_dossier/brief.md       # human brief
  gap_oracle: showcases/dd_dossier/checklist.yaml # acceptance items -> seed tasks
  stagger_s: 20
  idle_after_s: 300
  stuck_turn_s: 900
  budget: {total_tokens: 30_000_000, per_peer_tokens: 4_000_000, wall_clock_min: 90}
  termination:
    predicate: all_items_verified_and_final_gate_pass
    quiescence_cycles: 3          # no admitted gist or state change across 3 full peer cycles
    deadline_broadcast_min: [15, 3]
coordination:
  claims: {mode: atomic, one_item_per_agent: true, lease_s: 1200, advisory_claim_gists: true}
  board:
    types: [FACT, OBSERVED, FAIL, CLAIM, PATCH_SUMMARY, DECISION]
    caps: {default: 100, PATCH_SUMMARY: 300, DECISION: 200}
    admission: {require_evidence: true, executable_check: citation_resolver}
    dedup: [exact, anchor]
    window: 2000
  messaging: {dm: interrupt, channel: turn_start, channel_inline_max: 32}
  verification:
    self_check: rubric_middleware            # max_iterations: 2
    verify_item: {required: true, forbid_author: true, prefer_other_model_family: true}
    merge_gate: [schema, citations_resolve, rubric>=0.8]
models:
  deepseek: {id: accounts/fireworks/models/deepseek-v4p1-flash-1017, kwargs: {temperature: 1.0, top_p: 1.0}}
  glm:      {id: accounts/fireworks/models/glm-5p3-flash, kwargs: {}}
  minimax:  {id: accounts/fireworks/models/minimax-m3p1-flash, kwargs: {reasoning_effort: medium}}
roster: {deepseek: 4, glm: 3, minimax: 3}     # expands to peers p01..p10
backend:
  store: postgres://...                        # InMemoryStore for unit tests
  shared_prefix: /team/
  protected: [/team/main/**, /team/board/**]
observability: {langsmith_project: peerteam, lifecycle_jsonl: true}
```

## Model diversity replaces role prompts as the source of specialization

Agensh gives every worker the same prompt and lets roles emerge, but that emergence only showed up at 32 agents and above. With ten identical prompts, the cheapest lever for avoiding herd behaviour is the model. The evidence points the same way. Heterogeneous debate is the one debate variant that helped in the large MAD re-evaluation ([arXiv 2502.08788](https://arxiv.org/html/2502.08788v2)). DeLM found that funnelling parallel workers through a main agent raised Avg@1 but **reduced Pass@k diversity** ([arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)), because a supervisor homogenizes exploration. A mixed roster gives a self-organized team its diversity without anyone assigning roles. Pair that with a claim filter that prefers a different model family for `verify` items, and verification is no longer a model grading its own reasoning.

The three models divide cleanly, with one caveat: most benchmark figures are vendor-reported, and no source evaluated all three on one harness.

| Model (Fireworks ID) | Price per 1M (in / cached / out) | Agent evidence | Recommended use in the team | Must-set configuration |
|---|---|---|---|---|
| DeepSeek V4.1 Flash 1017 (`deepseek-v4p1-flash-1017`) | $0.30 / $0.006 / $1.20 ([llmreference](https://www.llmreference.com/model/deepseek-v4.1-flash-1017/fireworks-ai)) | DeepSWE 77.0, Terminal-Bench 4.0 42.3, ProgramBench 29.1 (vendor); AA-LCR 84.0 independent; **AA-Omniscience hallucination rate 96.5%** ([braindetox](https://braindetox.kr/en/posts/deepseek_v4_1_flash_1017_update_2026.html), [BenchLM](https://benchlm.ai/md/models/deepseek-v4-1-flash.md)) | 4 peers: deep extraction, numerical reasoning, long-document reading, code and terminal work | temperature 1.0, top_p 1.0; thinking on; never accept its uncited facts at admission |
| GLM-5.3 Flash (`glm-5p3-flash`) | $0.15 / $0.03 / $0.50 ([Fireworks](https://fireworks.ai/models/fireworks/glm-5p3-flash)) | Toolathlon Verified 78.4 (vendor); AA Tau3 Banking 47.2, AutomationBench 60.4, Terminal-Bench 4.0 32.8 independent ([BenchLM](https://benchlm.ai/md/models/glm-5-3-flash.md)) | 3 peers: breadth retrieval, tool-heavy work items, board hygiene, first-pass verify on DeepSeek output | No documented reasoning toggle; test tool-call strictness |
| MiniMax M3.1 Flash (`minimax-m3p1-flash`) | $0.15 / $0.015 / $0.60 ([Fireworks](https://fireworks.ai/models/fireworks/minimax-m3p1-flash)) | AutomationBench-AA 62.8, DeepSWE 73.7; AA Intelligence Index 43; very verbose (180M vs 100M median tokens) ([Artificial Analysis](https://artificialanalysis.ai/de/models/minimax-m3-1-flash)) | 3 peers: judgment-heavy verify items, synthesis and memo sections, the rubric grader inside `RubricMiddleware` | `reasoning_effort` low/medium; **thinking cannot be disabled** (400 error) and defaults to `max` ([eesel](https://www.eesel.ai/blog/minimax-m3-1-flash)) |

The 4/3/3 split is a starting hypothesis to test, not an optimum. It puts the heaviest reasoner on the most items and keeps a verifier pool from each of the other two families. Because roles are not hard-wired, a GLM peer can still claim a hard extraction item if nothing else is ready. The model mix shapes behaviour without fixing it.

Four configuration caveats decide whether the team works at all. First, **reasoning round-tripping**. Fireworks returns reasoning in `reasoning_content` and requires the prior assistant message, including that field, to be sent back in multi-turn tool use. It also offers `reasoning_history="preserved"` ([Fireworks reasoning](https://docs.fireworks.ai/guides/reasoning.md)). LangChain PR #34343 now extracts `reasoning_content` into `AIMessage.additional_kwargs` ([semanticdiff](https://app.semanticdiff.com/gh/langchain-ai/langchain/commit/6d447f89d9ccd6fc5d9e0bcf3acdf0844316df02)). Whether `ChatFireworks` re-serializes it on the next request is **unconfirmed**. Write a five-minute test before anything else. If it fails, add a thin message-conversion middleware, and never fall back to `ChatOpenAI` against the Fireworks endpoint, which drops the field. Second, **MiniMax's always-on thinking at default `max` effort** combines with its verbosity to make it the hidden cost driver. Set effort explicitly per role, and give MiniMax peers a lower per-peer token ceiling. Third, **DeepSeek's 96.5% hallucination rate on unknown facts** means it answers rather than abstains. That is exactly why admission requires evidence: every `FACT` must carry a resolvable citation (document ID plus span) in `detail`, and the gate checks it mechanically before any rubric judgment. Fourth, **caching and context**. All three have roughly 1M-token windows. Deepagents falls back to a 170k summarization trigger when a model has no profile ([context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)), so set the trigger explicitly per model to control cost. Keep the system prompt and tool schemas byte-stable across peers so the prefix cache hits. DeepSeek's standard Fireworks endpoint measured 84 tokens/s against 225 on Spot ([OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash)), so latency-sensitive runs should use the faster tier or a dedicated deployment.

The economics favour experimentation. Assume each peer reads 2M input tokens per run at 80% cache hits and writes 200k output tokens. At the listed prices that is roughly $0.37 per DeepSeek peer and $0.21 per GLM peer. A MiniMax peer comes to about $0.20, or nearer $0.30 once its verbosity is priced in. A full 10-peer run lands at **about $3**, so a several-hundred-run evaluation factorial costs low thousands of dollars, not a budget conversation. These are illustrative assumptions, not measurements. Phase 0 should replace them with metered numbers.

## A 10-peer due-diligence dossier is the showcase, DABstep the control

The showcase has to suit self-organization, not just look good in a demo. Google's 180-configuration study found that multi-agent coordination improved parallelizable financial reasoning by about **81%**, and degraded sequential planning by **39–70%**. It also found negative returns once a single agent exceeds about 45% accuracy ([Google Research](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/), [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)). Two cautions apply to that 81%. It was measured for a centralized architecture; the decentralized figure on Finance-Agent was not retrieved. And it comes from a different study, not from Agensh. The recommended showcase is therefore an **autonomous due-diligence dossier**. For a target company, ten peers answer a bundle of 15–30 diligence questions drawn from the Finance Agent Benchmark's categories, optionally extended with CUAD or MAUD contract-clause checks, and assemble an investment-committee memo. The benchmark has expert-authored rubric items graded item by item with a contradiction check. The best model, o3, scored only **46.8%**, which leaves headroom and sits right at Google's saturation threshold ([arXiv 2508.00828](https://arxiv.org/pdf/2508.00828)). The work is breadth-first across multiple 10-Ks, 10-Qs, transcripts and contracts, and it maps directly onto financial-services, insurance and private-equity client work.

Self-organization would play out in four stages. The gap oracle is the question checklist plus a memo template, and it seeds roughly 25 ready `work` items. It also seeds blocked synthesis items (one per memo section) that depend on their questions, and a final `memo_assemble` item that depends on every section. Peers start 20 seconds apart. Each reads the board, claims one item atomically, and posts an advisory `CLAIM` gist naming its angle. A DeepSeek peer working on "adjusted EBITDA bridge" publishes `FACT`s with filing citations, and a `DECISION` gist ("use FY24 10-K segment definitions; restated FY23") that becomes a constraint everyone sees. A peer that finds a footnote contradicting a published fact posts a `FAIL` and DMs the author. The DM interrupts the author mid-turn, which is exactly the situation the notice middleware exists for. Peers that see an uncovered angle reserve new items, such as "covenant headroom under the 2025 credit agreement." `ON CONFLICT` silently merges duplicates.

Each submit spawns a `verify` item that a different family prefers to claim. A MiniMax peer, for instance, re-derives the number from the cited span and either passes it to `/team/main/` or rejects it with a `FAIL`. Section items unblock as their questions verify. Whoever finishes the last section claims `memo_assemble`. The completion predicate then checks, deterministically, that every checklist item is verified and that the final gate's rubric passes. That is DeLM's "last finisher decides" ([arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)), with the decision taken by code, not by an LLM declaring itself done.

Roles to watch for: a retrieval-heavy GLM cluster, a DeepSeek numerical-modelling cluster, MiniMax peers drifting toward verification and synthesis, and possibly one peer that takes over board hygiene. Measure the emergence instead of asserting it, using the entropy of each peer's tool and item-kind distribution. A single-author preprint covering ~25,000 tasks reported spontaneous specialization and a minimal-structure protocol beating centralized coordination by 14%. It also found that self-organization only works above a capability threshold ([arXiv 2603.28990](https://arxiv.org/abs/2603.28990)). Treat that as a hypothesis this showcase can test, not as established fact.

The **secondary case for insurance clients** is underwriting submission triage on Snorkel's public multi-turn dataset. It covers appetite, product recommendation, NAICS classification, limits and deductibles, scored against reference answers. Models hallucinated non-existent products in 15–45% of recommendation cases ([Snorkel](https://snorkel.ai/blog/evaluating-ai-agents-for-insurance-underwriting/)), which gives the admission-verification layer something real to catch. Its weakness is that a batch of small submissions mostly shards, so it shows throughput more than coordination. Mixing submission types that share a burden of interpreting the guidelines helps. The **negative control** is DABstep's hard tasks: 450+ payments questions with exact-match scoring, where the best hard-task score was 14.55% ([arXiv 2506.23719](https://arxiv.org/html/2506.23719v1)). These are deep sequential chains of the kind Google found multi-agent setups degrade. If the framework does not lose to a single agent there, either the benchmark is unrepresentative or the evaluation is broken. Either way, the team learns something it needs to know before telling clients when to use the framework.

## Compute-matched factorial evaluation separates coordination from spend

Anthropic found that token usage alone explains **80% of BrowseComp variance**, and that multi-agent systems burn about 15× the tokens of chat ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). Any comparison that does not fix the budget will show "more agents spent more." The design is a factorial over architecture and team size, run at a fixed total token budget per task, with a second, unconstrained pass reported as quality-versus-cost Pareto curves.

| Arm | Description | Sizes |
|---|---|---|
| A — single agent | One deep agent, same tools, same budget, stop-hook resume (Agensh needed one to keep its single-agent baseline working) | 1 |
| A′ — independent ensemble | N agents in parallel, majority vote or self-consistency; isolates "more samples" from "coordination" | 3, 5, 10 |
| B — supervisor | Native deepagents supervisor with N−1 `task` subagents, same model mix | 3, 5, 10 |
| C — self-organized | This framework | 3, 5, 10 |
| C-ablations | C without board; without mid-turn notices; advisory-only claims (pure Agensh); without verify items; homogeneous single model | 5, 10 |

The C-ablations are the scientific contribution. Agensh ran none of them ([Paper](https://arxiv.org/abs/2609.26781)), so even a small, clean result at 5 and 10 agents is new evidence. Hold the model mix constant across arms. A single-model run of each arm then tests whether diversity, rather than topology, drives any gain.

The primary metric is the **rubric-item pass rate**: the share of Finance Agent rubric items, Snorkel reference answers or DABstep exact matches passed per task. The secondary metrics are:

- Cost per passed item, in dollars and tokens.
- Time to 80% of the arm's final pass rate, the analogue of Agensh's pandoc latency result.
- Duplicate-work rate: overlapping document reads and claim collisions.
- Message volume per passed item.
- Error amplification, measured by injecting a known false fact into one peer and tracing whether it reaches the memo. This mirrors Google's 17.2× versus 4.4× metric.
- Idle and blocked time.
- Role-specialization entropy.
- MAST failure labels assigned by an LLM annotator. The annotator agreed with human experts at κ=0.77 ([arXiv 2503.13657](https://arxiv.org/html/2503.13657v3)).

Judges must come from a model family outside the three agent models. Calibrate them against about 50 expert-labelled items and report κ. For the memo itself, add GDPval-style blinded pairwise comparison against a human-written deliverable, keeping in mind that GDPval's automated grader agreed with experts only 66% of the time, against 71% between humans ([arXiv 2510.04374](https://arxiv.org/html/2510.04374v1)). Run at least three seeds per cell and use paired bootstrap confidence intervals across tasks.

Pre-register three hypotheses. H1: C matches or beats B on pass rate at equal budget at N=5 and 10. H2: C beats A′, which shows that coordination adds value beyond sampling. H3: C loses to A on DABstep-hard. The statistical constraint is real: Finance Agent's private sets are not public, so reproducible runs are limited to the 50-question public set regrouped by company, or a self-built extension. Expect wide intervals, and say so up front.

## Ship in five phases, with the thin evidence as the main risk

**Phase 0 (week 1): model spikes.** Verify the `reasoning_content` round-trip on all three models through `ChatFireworks`. Measure tool-call reliability on the claim and board tool schemas. Confirm how DeepSeek's non-thinking mode and GLM's reasoning controls are selected on Fireworks; neither is documented in the sources. Meter real cache-hit rates and per-step costs. Confirm the `HarnessProfile` registration that removes `task`.

**Phase 1 (weeks 2–3): core services on `InMemoryStore` with three peers.** Build the board, the atomic task DAG, the mailbox, both middlewares and the runner, and test them on a toy checklist task. Unit-test claim races with 50 concurrent `task_claim` calls.

**Phase 2 (weeks 4–5): hardening.** Move to Postgres. Add the gate with citation resolution and `RubricMiddleware`, the termination predicate, quiescence detection, leases and watchdogs, and lifecycle JSONL plus LangSmith tags.

**Phase 3 (week 6): the 10-peer dossier showcase,** with trace review against MAST categories.

**Phase 4 (weeks 7–8): the evaluation factorial and ablations,** followed by packaging as a plugin for the config-driven platform, with the coordination services optionally exposed over MCP.

The risks start with the evidence base itself. At ≤10 agents, Agensh's gain was +1.37 points. MorphAgent's accuracy was flat from 3 to 10 agents while rounds rose ([arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)). MultiAgentBench's overall KPI fell as agents went from 3 to 5 and 7 ([arXiv 2503.01935](https://arxiv.org/html/2503.01935v1)). And DeLM's advantage shrank to near parity with a stronger model ([arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)). The design is most likely to help on breadth-first, verifiable, multi-document work where the single agent is below about 45%, and in time-to-quality. It is likely to hurt on sequential, constraint-heavy chains, on tool-dense tasks (Google's tool-coordination coefficient is β=−0.330), and wherever verification is weak, since an unchecked decentralized team behaves like Google's "independent" architecture with its 17.2× error amplification.

The engineering risks are concrete. Several deepagents building blocks are beta. The docs and source disagree on `AsyncSubAgent` fields. No official example of concurrent top-level peers exists. And deepagents' built-in backends give no write atomicity, which is why claims and `main` writes must bypass them. On the model side, most benchmarks are vendor-reported: GLM's Terminal-Bench 2.1 is 84.3 by vendor versus 62.9 measured by Vals AI. MiniMax's release date and openness conflict across sources. Per-model Fireworks serverless rate limits are unknown, and ten concurrent peers could hit them.

Several questions remain open: whether model diversity or topology drives any gain; whether advisory claims plus DMs are good enough at 5 peers, which would make the atomic queue unnecessary overhead; whether verify items cost more tokens than the errors they catch; and whether any role specialization appears at 10 peers at all, or only the interface-agreement behaviour Agensh saw at 8.

## Conclusion

The useful reading of Agensh is that a supervisor's work does not vanish when the supervisor is removed. It is redistributed into infrastructure. Agensh redistributes allocation to social negotiation and verification to each author's conscience, and that is affordable at 128 agents with a perfect oracle. At ten agents on business work without one, it is too loose. The defensible design moves allocation into an atomic queue, verification into a cross-model gate, and termination into deterministic code, while keeping every LLM an equal peer. That gives an architecture CK can explain to a client risk committee. A peer team with a gate is auditable in a way an emergent swarm is not: every fact has an author, a citation, a verifier from another model family, and a promotion record.

The bigger opportunity is to fill the measurement gap. No published work sweeps 1/3/5/10 agents on business tasks at matched budget across single-agent, supervisor and self-organized designs, with ablations of the board, the claims and the verification layer. At about $3 per 10-peer run on these Fireworks models, that study is cheap enough to run properly. A clean null result at ten agents, showing that coordination adds nothing over a compute-matched ensemble except speed, would still be worth publishing and worth knowing before a client asks.
