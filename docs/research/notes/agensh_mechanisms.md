# Agensh (Microsoft Research, 2026): how supervisor-free self-organization works, at implementation level

Scope and method: I shallow-cloned `github.com/microsoft/agensh` (HEAD `0468a3e`, committed 2026-10-23) and read every component: prompts/, board-service/, mini-router/, agent/, secret-service/, scripts/, docker/bootstrap. I also read the full technical report (`agensh.pdf` in the repo, 13 pages, identical to arXiv 2609.26781v1, submitted 2026-09-22) and the current DeLM repo (`yuzhenmao/DeLM`, HEAD `6661761`, 2026-10-08).
Labels used below: "Verified (code)" = read in source; "Verified (paper)" = stated in the report; "Inference" = my reading.
Short source keys:
- [Paper] = https://arxiv.org/abs/2609.26781 (the PDF is also at https://github.com/microsoft/Agensh/blob/main/agensh.pdf)
- [Repo] = https://github.com/microsoft/Agensh. File links use `https://github.com/microsoft/Agensh/blob/main/<path>`.

**Headline correction to the brief:** the "board-service" is **not** a task board or ticket queue. It is the **DeLM-style shared-context service**: an append-only log of typed short notes ("gists"). There is **no task queue, no lock, and no lease on work** anywhere in Agensh. Sub-tasks are represented only by **advisory, TTL'd `CLAIM` notes**, and optionally by Gitea issues the agents open themselves. Exclusion is social: agents settle overlaps by DM, and git merge conflicts catch the rest.

---

## 1. Sub-task representation, discovery and claiming (board-service, Gitea issues, and who decomposes)

### Takeaway
Agensh has no task data model. The task root is Gitea issue #1, which the launcher opens with **no assignee**. Each agent decomposes the work itself: it runs the reference binary to find unexplored areas, then announces its scope as a `CLAIM` gist (max 100 chars, hidden after a 1h TTL). It may also open its own Gitea issue. Duplicate work is reduced in four ways: claims are rendered under "pick a different angle", colliding claims are pushed to agents mid-turn, the prompt tells agents to DM each other on a collision, and startup is staggered. Nothing enforces exclusivity.

### Cited Findings
- The launcher opens one task issue with the brief as its body. The code comment reads "opening task issue (no assignee; peers self-select)". It creates the issue via the Gitea API as admin, titled `[pbench] <TASK>`. — [scripts/pbench_run.sh](https://github.com/microsoft/Agensh/blob/main/scripts/pbench_run.sh)
- Worker prompt (verbatim): "**gitea** — issue #1 is the task. You open your own issues for the areas you take, and PRs carry the work." and "${PBENCH_WORKERS} coders, all equal. You claim what to build, you build it, you merge it, and you choose the next thing." — [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)
- The prescribed work cycle (verbatim): "1. Run `/opt/pbench/executable` to observe the unexplored areas to build. 2. Announce the area you are taking as a `CLAIM` on the shared context board. 3. Run `/opt/pbench/executable` on that area ... and write code that reproduces what you observe, based on current `main`. You do not need to sync code with others during implementation. 4. Check your work by running the reference and your build on the same inputs and comparing. 5. Push, open a PR, and merge to `main`. If the merge is refused, merge the latest `main` into your branch, re-check your work against the reference, and push again. 6. Say what you finished as a `PATCH_SUMMARY` (`files= | idea= | evidence=`) on the board, then go back to 1." — [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)
- The paper describes the claim step as: "The worker proposes a sub-task to do and announces its scope as a CLAIM appended to the shared context. When two workers' claims overlap or conflict, they are encouraged to resolve the issue through direct messages." It also says: "By proposing and claiming their own sub-tasks, workers self-organize sub-task discovery and allocation." — [Paper §2.1](https://arxiv.org/abs/2609.26781)
- **Data model (verified, code).** There is one MySQL table, `board_gists(id BIGINT AUTO_INCREMENT, board_id, thread_id /*agent name*/, type, content TEXT, ts_epoch, expires_at, delegation_id VARCHAR(128), detail LONGTEXT)`, indexed on (board_id, ts) and (board_id, type). Types are `FACT, OBSERVED, FAIL, CLAIM, PATCH_SUMMARY`. Gist IDs are rendered as labels `G<id>`. — [mini-router/sql/03-board-schema.sql](https://github.com/microsoft/Agensh/blob/main/mini-router/sql/03-board-schema.sql), [board-service/shared_lessons.py](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- **Claim semantics (verified, code).** `CLAIM` gets `expires_at = now + ttl`, with `BOARD_CLAIM_TTL_SECONDS` defaulting to 3600. Expired claims are hidden from reads and snapshots but stay in MySQL. The code has no uniqueness check, no owner check and no conflict rejection, so two agents can both CLAIM the same area. Each claim renders as `[t<agent>/CLAIM +<min>m, +<left>m left] <content>`. — [board-service/main.py](https://github.com/microsoft/Agensh/blob/main/board-service/main.py), [shared_lessons.py](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- In the prompt view, claims appear under the header "[Active claims — peer threads' current targets; pick a different angle if your plan duplicates theirs]". — [shared_lessons.py `format_for_prompt`](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- Rule for a mid-turn CLAIM (verbatim from the prompt): "`CLAIM` on what you are building — a collision; settle it by direct message. any other `CLAIM` — keep building what you are on." Also: "Send a direct message when two of you are about to edit the same thing; use the channel for everything else." — [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)
- **`delegation_id`.** This is an agent-chosen label for "the unit of work this note belongs to", for example "python-parser". The tool description says: "Reuse the SAME id for every note about that sub-task: a refined PATCH_SUMMARY then REPLACES your earlier one ... and a FAIL strikes your own patch summary. A fresh id per note silently disables both." — [board-service/mcp.cjs](https://github.com/microsoft/Agensh/blob/main/board-service/mcp.cjs)
- Refreshing a claim is driven by the router's "forced-write nudge" after any turn that published no gist: "...if you are still mid-task, refresh your `CLAIM` so peers and your lead can see the work is live." The text mentions "your lead" even though no lead exists; it reads like a leftover from an earlier design. — [mini-router/src/board_client.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/board_client.ts)
- **Startup ramp reduces contention.** The paper says: "To reduce scope contention, we stagger agent activation in all experiments, launching one agent every 30 seconds during the first hour and one every 3 seconds thereafter." The code uses `PBENCH_WAKE_STAGGER_S=30`, `PBENCH_WAKE_FAST_STAGGER_S=3` and `PBENCH_WAKE_RAMP_SUBJ_S=3600`. The switch happens by worker index (the first 120 workers get 30s spacing). Wake-up time counts against the shared budget. — [Paper App. C](https://arxiv.org/abs/2609.26781), [scripts/pbench_run.sh](https://github.com/microsoft/Agensh/blob/main/scripts/pbench_run.sh)
- Each worker is woken by a Mattermost DM containing the kickoff ("New task. ${TASK_BRIEF}"), and the kickoff is also posted to the task channel. — [prompts/kickoff.txt](https://github.com/microsoft/Agensh/blob/main/prompts/kickoff.txt), [pbench_run.sh](https://github.com/microsoft/Agensh/blob/main/scripts/pbench_run.sh)
- **Contrast with DeLM's current code.** DeLM does have a real task queue with atomic claims. Its `claim(actor, item_id)` returns `won=False` if the item is not `open`, and errors with "you already hold an unfinished item" (one item per agent). `reserve(subject)` creates or claims a scope atomically, keyed on the normalized subject. `done()` is allowed only by the holder: "only the agent holding this item may complete it". Agensh dropped this hard queue and kept only advisory CLAIM gists. — [DeLM board/shared_context.py](https://github.com/yuzhenmao/DeLM/blob/main/board/shared_context.py)

### Inferences
- Decomposition is fully emergent and environment-driven. Each agent probes the reference binary, reads the board's claims and patch summaries, and picks a gap. There is no planner. This works because ProgramBench has a cheap, always-available oracle (the reference binary) that shows what is still unbuilt. For a Deep Agents port to non-reproduction tasks, you need an equivalent "gap oracle", such as a failing-test list, a spec checklist, or a diff against acceptance criteria. Otherwise the agents have nothing objective to decompose against.
- Agensh trades correctness of allocation (locks) for liveness (nothing can deadlock or go stale; an expired claim just vanishes). At ≤10 agents, DeLM's atomic `reserve`/`claim`/`done` with one item per agent is cheap and probably strictly better. You can keep Agensh's advisory CLAIM text as a soft signal on top. This is a design choice, not something either paper ablates.
- Gitea issues per area are prompt-optional. The code never reads them, so their use is emergent.

### Gaps
- The paper does not measure how often duplicate or overlapping claims happen, how much work is wasted, or how many claim collisions get resolved by DM.
- There is no ablation of the TTL (1h) or of the ramp schedule.

---

## 2. Shared context mechanism (DeLM-derived): storage, compression, delivery to each agent

### Takeaway
Shared context is a typed, append-only gist log, deliberately very short (100 chars, or 300 for PATCH_SUMMARY). Any long content goes into an optional `detail` field that is not shown by default and can be expanded on demand with `board_unfold G<id>`. "Compression" is mostly a hard character cap enforced at write time, plus the following:
- exact and "semantic" deduplication at render time;
- each author's PATCH_SUMMARY is replaced in place per `delegation_id`;
- claims expire;
- a recent window of 2,000 entries, with full-history `board_grep`.

There are two delivery paths:
1. At turn start, the router prepends unread gists (cursor-based delta) under `==== SHARED CONTEXT ====`.
2. Mid-turn, an MCP proxy shim appends new peer gists and DMs to the result of any infrastructure tool call (gitea/mattermost/board).

### Cited Findings
- DeLM is "Decentralized Multi-Agent Systems with Shared Context" by Yuzhen Mao, Jerry Gu, Aadi Chauhan, Qizheng Zhang, Hangoo Kang and Azalia Mirhoseini, arXiv 2606.10662, submitted 2026-06-09, v3 on 2026-10-04. It replaces the orchestrator with "a shared context and a task queue". Agents claim tasks asynchronously and publish findings. It targets "bubbles", meaning time spent waiting on or redoing peers' work. Reported results: up to +17.5 points accuracy over the strongest baseline, up to 2.49× faster than the base harness on Terminal-Bench 4.0, DeepSWE v1.1 and SWE-bench Verified, and on ProgramBench a pass rate up to 19.9 points higher than Claude Code within a 120-minute budget. — [arXiv 2606.10662](https://arxiv.org/abs/2606.10662)
- The DeLM README says the two-agent version averages "+12.5 percentage points and 1.78× speedup" over base harnesses on a 10-task Terminal-Bench 4.0 subset. The repo supports n=2 or n=4 agents with Codex or Claude Code, and there is a Claude Code/Codex plugin (`Decentralized-LM/delm-agent-plugin`). — [DeLM repo](https://github.com/yuzhenmao/DeLM)
- DeLM's original shared memory, "SharedLessons", stores "compact cross-thread facts, failed attempts, observations, claims, and patch summaries". Agensh keeps the class name `SharedLessons` and the same five types. — [DeLM repo README (earlier SWE-bench branch)](https://github.com/yuzhenmao/DeLM); [shared_lessons.py](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- The paper credits DeLM: "The shared context follows the core idea of DeLM [14], but we adapt its tool formats and worker instructions." It also says: "To support longer task horizons, we introduce a context grep tool that lets workers search the full recorded history beyond recent memory." — [Paper §2.2–2.3](https://arxiv.org/abs/2609.26781)
- **Type semantics, from the prompt (verbatim):** "`OBSERVED` for noticeable reference behaviour, `FACT` for what you confirmed, `FAIL` for a hypothesis you falsified (the highest-value entry: it stops peers spending budget on it), `PATCH_SUMMARY` as `files= | idea= | evidence=` when you fix something, and `CLAIM` while you are working so peers pick a different angle. ... Do not re-derive a peer's `FACT`, and do not retry something recorded as `FAIL`." — [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)
- **Write-time "verifier" (deterministic text check only).** It uppercases the type, truncates content to its cap, and rejects a PATCH_SUMMARY whose `evidence=` field is missing or starts with any of: "tbd", "pending", "not verified", "unverified", "should work", "should pass", "looks right", "looks correct", "seems to work", "to be verified", "will verify", "n/a". In the module's own words: "Verification is a deterministic text check; it does not execute the claimed tests." — [board-service/verifier.py](https://github.com/microsoft/Agensh/blob/main/board-service/verifier.py)
- **Patch status tagging.** A PATCH_SUMMARY gets `[status=verified]` if its evidence matches `\b(pass(ed|es)?|verified|confirmed|no longer|now returns|now produces)\b` and contains no weak words ("should", "looks", "seems", ...). A later `FAIL` from the **same author with the same delegation_id** marks that author's latest patch `invalidated` and increments `local_failures=N`. A new PATCH_SUMMARY from the same (author, delegation_id) replaces the old one in place. — [shared_lessons.py `_admit`](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- **Deduplication at render time.** First, non-claim and non-patch entries are merged when their whitespace-normalized text matches exactly, and rendered with `(xN)` and the contributing authors. Second, a "semantic key" pass merges entries that share strong code anchors: file plus symbol, file plus line, file plus test, error plus anchor, or a test name. The code comment says: "Require strong code/test anchors before treating distinct prose as duplicate." Claims and patches are never merged. — [shared_lessons.py `_dedupe_entries`, `_semantic_key`](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- **Rendering order.** The view has three sections. First, "[Patch summaries — candidate fixes proposed by peer threads; review BEFORE deciding to submit or to propose your own]". Then "[Active claims ...]". Then "[Shared lessons]" (FACT, OBSERVED and FAIL). Each line is `[t<agent>/<TYPE> +<minutes since board start>m] content`. — [shared_lessons.py `format_for_prompt`](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)
- **Unfold (lazy detail).** Gists that have a `detail` are listed in an index, "[Unfoldable — ... Call board_unfold with up to 100 labels to expand them for one step.]", with a 90-char excerpt each. The unfold output is headed "Expanded for THIS step only. It is not added to the shared board, and peers still see only the gist layer — if something here matters to them, publish it as a gist yourself." — [board-service/unfold.py](https://github.com/microsoft/Agensh/blob/main/board-service/unfold.py)
- **Windows.** The in-memory recent view holds at most 2,000 entries (`MAX_BOARD_ENTRIES`). `board_read` returns that window. `board_grep` searches MySQL history with boolean `&`, `|` (or `,` for OR in the MCP tool) and parentheses, at most 50 terms and at most 500 matches (newest first, rendered chronologically), and reports `total` and `truncated`. — [main.py](https://github.com/microsoft/Agensh/blob/main/board-service/main.py), [board-service/README.md](https://github.com/microsoft/Agensh/blob/main/board-service/README.md)
- **Turn-start delivery is a delta.** `GET /snapshot?viewer=&boards=` returns only gists with `id > board_cursor[agent]`, then advances that cursor (monotonically, via `GREATEST`). An explicit `board_read` returns the full live view. The router wraps the delta with guidance. When there is content, the guidance says: "The entries above are verified notes published by your peers. Read them BEFORE acting: do not re-derive a FACT someone already established, do not repeat a path recorded as FAIL, and check PATCH_SUMMARY entries before proposing your own fix." When the board was unreachable, it says the view is "UNKNOWN, not empty". — [main.py `get_snapshot`](https://github.com/microsoft/Agensh/blob/main/board-service/main.py), [board_client.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/board_client.ts)
- **Mid-turn delivery (the "notice shim").** Every MCP server (gitea-mcp, mcp-server-mattermost, the board server) is launched behind `mcp-notice-shim.cjs`. After each `tools/call` response, the shim calls `GET /pending/<agent>`. That call takes a 30s per-agent lease (`pending_leases` table), so concurrent wrappers do not double-drain. The returned new DM posts and peer gists (excluding the agent's own) are appended as text to the tool result, followed by `POST /shown/<agent>` to advance cursors and record the delivered events. — [mini-router/mcp-notice-shim.cjs](https://github.com/microsoft/Agensh/blob/main/mini-router/mcp-notice-shim.cjs), [main.py `get_pending`/`post_shown`](https://github.com/microsoft/Agensh/blob/main/board-service/main.py)
- The paper's description: "During an active turn, a wrapper around any infrastructure tool call appends pending direct messages and new shared context entries to the tool results returned. This path operates on MCP tool returns; it does not interrupt an arbitrary running process." — [Paper App. B.2](https://arxiv.org/abs/2609.26781)
- **Publication pressure.** After each turn, the dispatcher compares the agent's latest own gist ID before and after. If nothing new was published, it sends a second prompt: "==== SHARED CONTEXT: ANYTHING TO PUBLISH? ==== This turn produced no board entry. If you established something your peers can build on, publish it now; ... Do NOT publish a placeholder. Publish only evidence — let peers draw their own conclusions." — [dispatcher.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/dispatcher.ts), [board_client.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/board_client.ts)
- **Diagnostics.** `POST /board/{id}/lifecycle` writes JSONL with `written_count`, `render_count`, verified/invalidated status and first/last timestamps for each unique entry. Use it to measure whether shared context is actually being read. — [shared_lessons.py `write_lifecycle_summary`](https://github.com/microsoft/Agensh/blob/main/board-service/shared_lessons.py)

### Inferences
- There is no LLM summarization anywhere in the shared context. Compression is done entirely by forcing authors to write short gists, deterministic dedup, and lazy `detail` expansion. This is cheap and easy to port. In Deep Agents it maps naturally to a tool pair (`board_write`, `board_read`/`grep`/`unfold`), plus a middleware or pre-model hook that injects the unread delta at the start of each turn.
- The mid-turn "interrupt" path is the most distinctive piece. Without it, an agent deep in a long turn would not see a peer's `FAIL` until the turn ended. In LangChain/LangGraph, the equivalent is a tool-wrapping middleware (`wrap_tool_call`) that appends pending notices to each `ToolMessage`. It should be applied to all tools, not just infrastructure ones. Agensh restricts it to MCP tools only because Copilot's native shell tool cannot be wrapped.
- The FAIL→invalidate link applies only to the author's own patch. A peer's FAIL does not mark someone else's patch. Cross-agent refutation therefore happens through PR review and messaging. The paper's PHP-src anecdote about a counterexample withdrawing an approval was conversational, not a board mechanism.

### Gaps
- There is no ablation of shared context (for example, Agensh with vs. without the board, or without the mid-turn shim). The paper does not quantify its contribution.
- The full DeLM paper's gist/verifier specification was not reviewed in depth. Only the abstract and the repo were read.

---

## 3. Verification and merging: who integrates?

### Takeaway
Each author verifies its own work by differential testing against the reference binary: it runs both on the same inputs and compares. It then pushes a branch, opens a Gitea PR and **merges it to `main` itself**. On a refused merge, it merges `main` into its branch, re-checks and re-pushes. The code shows no CI, no required reviewers and no branch protection. Peer review and dedicated "integrators" are **emergent** behaviors reported at 32+ agents, not mechanisms. The board's "verified" tag is a regex on the evidence text, not an executed check.

### Cited Findings
- Prompt: "Each step is finished by the person doing it." Step 4 says "Check your work by running the reference and your build on the same inputs and comparing." Step 5 says "Push, open a PR, and merge to `main`..." The team section adds: "sync your codebase with the latest `main` branch before merging your own code to `main`". — [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)
- The paper's verify step: "The worker matches its local progress against the sub-task's acceptance criteria. If it does not satisfy those criteria, the worker revises its approach until the criteria are met." Merge step: "If the merge is blocked by a conflict, the worker incorporates the latest peer progress, resolves the conflict, and merges again." — [Paper §2.1](https://arxiv.org/abs/2609.26781)
- The shared workspace is described as "a Git platform... Workers modify private checkouts and branches and integrate their contributions into a main branch. Git records the provenance of changes and detects textual merge conflicts, while hosting issues and pull requests for all." — [Paper §2.2](https://arxiv.org/abs/2609.26781)
- **Permissions.** Bootstrap creates a Gitea org team `coders` with `write` permission on all repos, and keeps its membership strictly equal to the agent list. Grepping bootstrap.sh found no branch-protection or required-approval calls; I did not inspect Gitea's own default settings. — [docker/bootstrap/bootstrap.sh](https://github.com/microsoft/Agensh/blob/main/docker/bootstrap/bootstrap.sh)
- **Tool shaping for Gitea MCP.** Denied and hidden tools include `create_branch`, `delete_branch`, `create_or_update_file`, `delete_file`, `get_file_contents`, `get_dir_contents`, `get_repository_tree`, `list_commits`, `wiki_*`, `label_*`, `milestone_*`, `actions_*`, release and tag tools, and `create_repo`/`fork_repo`. Issue and PR tools remain available. This forces code reading and writing to go through a local `git clone` and shell, while Gitea MCP stays the coordination surface (issues and PRs). On the Mattermost side, channel creation, joining and leaving, membership, bookmarks, pins, files, and message edits and deletes are denied. — [agent/config/copilot-deny-tools.json](https://github.com/microsoft/Agensh/blob/main/agent/config/copilot-deny-tools.json)
- Copilot's native subagent tools are disabled: `--excluded-tools=task --excluded-tools=list_agents`. Each worker is a single agent loop, so recursive orchestration is not possible. — [agent/entrypoint.sh](https://github.com/microsoft/Agensh/blob/main/agent/entrypoint.sh)
- **Grading contract.** The grader tars the repo HEAD, deletes any committed `./executable`, and runs the root `compile.sh`. Only merged `main` counts. The 45-minute reminder says: "Land the open PRs; work that is not merged does not count." — [prompts/pbench-brief.txt](https://github.com/microsoft/Agensh/blob/main/prompts/pbench-brief.txt), [prompts/deadline-45m.txt](https://github.com/microsoft/Agensh/blob/main/prompts/deadline-45m.txt)
- **Emergent integration (paper, observational).**
  - At 32 agents (PHP-src): "several peers initially approved a contribution. Another worker found a concrete counterexample, so the earlier approval was withdrawn, and the author fixed the problem. Peers then reviewed the contribution again, and a peer merged it."
  - At 128 agents: "Workers are choosing reviewers based on relevant prior experience and reuse these review relationships... transfer responsibility for integrating a contribution to a peer who resolves conflicts, validates the combined work, and merges it." In pandoc, there was a "standardized integration protocol: the author updated and tested a branch, then sent its commit hash for peer validation and merge", later revised so the peer performs "the entire update, test, check, and merge cycle."
  - At 1,024 agents: "multiple workers served as integrators. A worker could contact several candidate integrators, select the first valid responder, cancel the other requests, and hand over the code".
  - [Paper §3.2](https://arxiv.org/abs/2609.26781)
- Gitea activity reaches agents as events. An SSE `/user/events` wakeup triggers a REST fetch of notifications, and each becomes a summary such as `"<repo> <kind><ref>: <title>"` (kind is the notification subject type, e.g. pull or issue). Agents therefore see PR and issue activity on repos they watch or participate in. — [mini-router/src/listeners/gitea/](https://github.com/microsoft/Agensh/blob/main/mini-router/src/listeners/gitea/README.md)

### Inferences
- Integration is "everyone merges to main, latest-wins, git catches textual conflicts". Semantic regressions are caught only when a later agent's differential check fails. At ≤10 agents, with no CI gate, regressions on `main` are plausibly the main risk. A cheap mandatory gate in your port (run the test suite before merge, in a merge tool) would be a deliberate departure from Agensh. The paper did not test it.
- The "verified" tag on the board is a self-attestation filter. It blocks lazy placeholders but cannot catch false claims.

### Gaps
- There are no statistics on merge conflict rates, reverted merges, broken-`main` incidents, or PR review rates per team size.
- The 8-agent anecdotes describe only interface agreement and claim renegotiation. Peer review and integrator roles were reported at 32 and 128+ agents, so they may not appear at ≤10 agents.

---

## 4. What `mini-router` and `secret-service` are

### Takeaway
`mini-router` is **not a model gateway**. It is a per-worker TypeScript sidecar that turns Gitea and Mattermost activity into a durable per-agent event queue (MySQL). It serializes those events into prompts on the worker's persistent Copilot session over ACP (Agent Client Protocol, via a Unix socket), adds the shared-context delta, nudges publication, and retries. `secret-service` is a tiny internal HTTP service that hands bootstrap-issued Gitea and Mattermost tokens to the routers. Model access goes through a separate egress proxy (`strip_metadata_proxy.py`), so workers only ever see a local proxy credential.

### Cited Findings
- mini-router README: "One TypeScript sidecar per worker connects Gitea/Mattermost activity to a native Copilot ACP session. Routing and retry are infrastructure behavior; agents choose and coordinate their work through the shared services and prompts." — [mini-router/README.md](https://github.com/microsoft/Agensh/blob/main/mini-router/README.md)
- **Event queue.** Table `events(dedup_key, source, agent, payload JSON, state ENUM('pending','sending','sent','failed','retrying'), attempts, batch_id, next_retry_at, UNIQUE(dedup_key, agent))`. Delivery follows "pending → sending → sent". Retry backoff is `[1s, 5s, 30s, 120s]` with `MAX_ATTEMPTS = 5`. A restart returns `sending` rows to `pending`. — [sql/01-events-schema.sql](https://github.com/microsoft/Agensh/blob/main/mini-router/sql/01-events-schema.sql), [src/state.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/state.ts), [src/README.md](https://github.com/microsoft/Agensh/blob/main/mini-router/src/README.md)
- **Dispatcher.** It takes up to 32 pending events per batch. It retires DMs already delivered mid-turn by the shim (via the `shown` ledger). It sets the prompt prefix to the board snapshot and sends the batch as one prompt. It marks the batch sent when the turn completes, then runs the forced-write nudge check. Normal dispatch and retries share one serialization chain ("must never prompt the session at once"). When idle, it waits on a wake signal or a 30s timeout. — [src/dispatcher.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/dispatcher.ts)
- **Event envelope seen by the agent:** `[event] event_id=... source=... kind=... observed_at=+<min>m summary: ...`. Multiple events become `[event-batch] N events` with `--- event i/N ---` blocks. Timestamps are relative to a shared `PBENCH_RUN_START_MS`. — [src/uem_render.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/uem_render.ts)
- The ACP session ID is persisted in `agent_kv`, and the router "reconnects to the saved native session when possible" after restarts. — [mini-router/README.md](https://github.com/microsoft/Agensh/blob/main/mini-router/README.md)
- secret-service README: "serves bootstrap-issued worker tokens to mini-routers on the private Compose network. `GET /tokens/<agent>` requires `X-Internal-Auth`... Routers request their Gitea token and, when chat is enabled, the corresponding `<agent>-mm` token." — [secret-service/README.md](https://github.com/microsoft/Agensh/blob/main/secret-service/README.md)
- On model credentials, REPRODUCE.md says: "The egress proxy injects the real credential; workers receive only a local proxy credential." `strip_metadata_proxy.py` "Relays model HTTP traffic, removes unsupported fields, injects auth and retries selected failures". — [REPRODUCE.md](https://github.com/microsoft/Agensh/blob/main/REPRODUCE.md), [scripts/README.md](https://github.com/microsoft/Agensh/blob/main/scripts/README.md)
- The paper describes Agensh as "an organization harness layered above a single-agent harness rather than a replacement for it... Agens[h] can connect to different underlying harnesses, such as Claude Code and Copilot, through lightweight harness-specific adapters." — [Paper §2.3](https://arxiv.org/abs/2609.26781)
- Defaults are 8 workers, 6h per task, `gpt-5.6-sol` at high effort, the Responses API, and a 272,000-token prompt window. The paper adds a 128,000-token output limit. — [REPRODUCE.md](https://github.com/microsoft/Agensh/blob/main/REPRODUCE.md), [Paper App. C](https://arxiv.org/abs/2609.26781)

### Inferences
- The architecture is event-driven agents with a durable inbox per agent. Each agent's "turn" is triggered by external events (a DM, a channel post, PR or issue activity, an idle nudge), not by a polling loop the agent runs itself. In LangGraph this is a per-agent thread (`thread_id`) with a checkpointer, plus a small dispatcher that drains a per-agent queue into `graph.invoke(..., config={"thread_id": agent})`. Turns must be serialized per agent.

### Gaps
- None material.

---

## 5. Prompts and roles: pre-assigned or emergent?

### Takeaway
All roles are emergent. Every worker gets the identical prompt (only `AGENT_NAME`, peer count and handles differ): "N coders, all equal." There are no role slots, no lead, and no subagent tool. The paper reports that specialization emerges with scale: interface agreement at 8, multi-worker review and integration at 32, reviewer selection and standardized integration protocols at 128, and multiple integrators with first-responder selection at 1,024.

### Cited Findings
- "The complete worker prompt is presented in Appendix A, which is exactly the same for each worker except for the worker ID." — [Paper §2.3](https://arxiv.org/abs/2609.26781). The full prompt is reproduced in Appendix A and matches [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt) with [pbench-brief.txt](https://github.com/microsoft/Agensh/blob/main/prompts/pbench-brief.txt) spliced in. The entrypoint renders it to `/work/AGENTS.md`. — [prompts/README.md](https://github.com/microsoft/Agensh/blob/main/prompts/README.md)
- Key prompt lines (verbatim):
  - "Always focus on reproducing the reference; reach for the coordination tools only when your information can greatly impact others' work."
  - "**Anything else.** MCP, git CLI, shell, curl, writing files — whatever is at hand is fine. If the tool you have is not enough, look for one; if there is none, build one."
  - Iron rule 1: "**Fully autonomous**: the whole team defines requirements itself, breaks down work itself, decides itself, and finishes itself. There is no external input; do not wait for instructions, do not ask on mattermost 'what to do next' — the answer is always: **push the rebuild forward**."
  - [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt), [prompts/pbench-brief.txt](https://github.com/microsoft/Agensh/blob/main/prompts/pbench-brief.txt)
- Task brief (the kickoff DM) passes concrete Mattermost team and channel IDs: "Pass those ids straight to the mattermost tools — do not guess them and do not go looking them up. If a mattermost call returns 403 or 404 you have used a wrong id, not lost access". — [prompts/task-brief.txt](https://github.com/microsoft/Agensh/blob/main/prompts/task-brief.txt)
- prompts/README: "Cooperation is defined by these prompts; the router transports service events and context between native Copilot turns." The paper: "Agensh realizes the cooperation loop through workflow instructions in each worker's prompt rather than hard-coding the loop into the runtime infrastructure." — [prompts/README.md](https://github.com/microsoft/Agensh/blob/main/prompts/README.md), [Paper §2.3](https://arxiv.org/abs/2609.26781)
- Emergence by scale is reported as qualitative trajectory observations, with titles "8 agents: coordinating implementation with peers", "32 agents: managing integration across multiple workers", "128 agents: self-organized specialization and workflow standardization", and "1,024 agents: role specialization at organization scale". Concretely at 8 agents: in gromacs, workers "announced a module interface and independently implemented command modules that followed it"; in FFmpeg, "one worker changed its scope and took on complementary work after discussing the overlap issue with a peer." — [Paper §3.2](https://arxiv.org/abs/2609.26781)
- Single-agent baseline prompt files exist separately (brief, rules, resume) and use a stop hook. — [prompts/single-agent/](https://github.com/microsoft/Agensh/blob/main/prompts/single-agent/README.md)

### Inferences
- At ≤10 agents, expect only the 8-agent behaviours: interface agreements and claim renegotiation. Reviewer and integrator specialization appeared only at 32+ in their runs. If you want review or integration at small scale, you probably need to prescribe it (for example, a rotating integrator, or "merge requires one peer's LGTM"). That departs from Agensh's "all equal" design, and they did not evaluate it.
- The emergent behaviours are reported anecdotally. There is no frequency table or annotation methodology.

### Gaps
- No quantitative role analysis, no annotation protocol, and no released trajectory dataset was found in the repo. The README links an interactive replay at agens-harness.github.io, which I did not inspect.

---

## 6. Messaging protocol on Mattermost: channels, DMs, priority and noise control

### Takeaway
There is one shared channel (`pbench-task`) for announcements and "everything else", plus DMs for urgent collisions. The two have different priorities:
- **DMs** are delivered **mid-turn**: appended to the next infrastructure tool result, and they interrupt the agent.
- **Channel posts** queue until the turn ends. They are summarized to 200 chars each in the event, only the newest 32 are kept inline, and larger backlogs are spilled to a JSONL file with an exact @mention count.

Noise is controlled mostly by the prompt ("Be brief and concrete"; "reach for the coordination tools only when your information can greatly impact others' work"), by denying channel-management tools, and by the board taking over the role of findings broadcast.

### Cited Findings
- Prompt: "**mattermost** — channel `pbench-task`, where the team talks. Be brief and concrete. Handles are `${GITEA_ORG}-worker1..N`; `@worker1` matches no account, so use the full one. A **direct message** on the same server reaches a peer **inside their current turn**, so it is the fast way to settle a collision — and it interrupts what they are doing." — [prompts/agents.txt](https://github.com/microsoft/Agensh/blob/main/prompts/agents.txt)
- Paper: "Lower-priority shared-task-channel messages are delivered at the beginning of each loop iteration, while higher-priority direct messages are delivered at the end of each infrastructure tool call." — [Paper §2.2](https://arxiv.org/abs/2609.26781)
- Listener behaviour: "New direct posts have kind `dm`; their summary bodies are untruncated ... for mid-turn delivery. Channel/group message bodies in summaries are capped at 200 characters ... full post text kept in the raw event. Edits and deletions retain their own kinds, so even DM edits/deletions wait for a queued turn. Self-authored and system posts are filtered". — [listeners/mattermost/README.md](https://github.com/microsoft/Agensh/blob/main/mini-router/src/listeners/mattermost/README.md)
- **Backlog spill.** If a batch has more than 32 group messages, the older ones go to `/opt/data/home/group-messages/group-messages-<hash>.jsonl`, and a system notice says: "Showing the latest 32 group-chat messages. N earlier messages are saved in <path> ... You are mentioned K times in the earlier messages. Search the file for "@handle" to find your mentions." The mention regex matches the complete handle "so worker1 does not count mentions of worker10". — [src/group_messages.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/group_messages.ts)
- The deny list blocks `create_channel`, `join_channel`, `leave_channel`, `add_user_to_channel`, `list_public_channels`, `get_channel_members`, `pin/unpin`, `update_message`, `delete_message`, bookmarks and file uploads. Agents can only post, read, DM and react. — [copilot-deny-tools.json](https://github.com/microsoft/Agensh/blob/main/agent/config/copilot-deny-tools.json)
- Mattermost catch-up after reconnect starts with a 10-minute lookback. — [listeners/README.md](https://github.com/microsoft/Agensh/blob/main/mini-router/src/listeners/README.md)

### Inferences
- The design splits information into three channels by type. Durable findings go to the board, which is structured, capped, dedup'd and greppable. Negotiation goes to DMs, which interrupt. Announcements go to the channel, which is batched. For ≤10 agents in Deep Agents you can collapse Mattermost into a simple in-process message bus with the same two priorities. The interrupt vs. batched distinction is the part worth keeping.

### Gaps
- No message-volume statistics (posts per agent-hour, DM share) are reported for any team size.

---

## 7. Termination, watchdogs and liveness

### Takeaway
Nothing detects that the goal is done. Runs are wall-clock bounded at 6h:
- channel reminders at T−45m ("Stop dispatching new features... Land the open PRs") and T−5m;
- the export of Gitea `main` HEAD at T;
- graceful shutdown with workspace archives.

Liveness is maintained by three things:
- an **idle watchdog**: if a worker's turn logs haven't changed for ≥600s **and** its event queue is empty, it gets the idle prompt by DM, with an @mention in the channel as fallback, repeated at most every 600s;
- an **ACP silence watchdog**: no bytes from the agent for 20 min force-closes the connection and the prompt fails into retry;
- the publication nudge after every turn.

### Cited Findings
- Idle prompt (verbatim): "There is always new work — do not be bounded by the previous CLAIMs' scope: pick up /opt/pbench/executable, run it against untried inputs, and close the gap between reference and the team's implementation." — [prompts/idle.txt](https://github.com/microsoft/Agensh/blob/main/prompts/idle.txt), [Paper App. C](https://arxiv.org/abs/2609.26781)
- Watchdog code: `WORKER_IDLE_THRESHOLD=600`, `WORKER_IDLE_REPEAT=600`, `WORKER_CHECK_INTERVAL=60`. Idle time is measured from the newest `*.jsonl` turn-log mtime. If there are pending UEM rows, it logs "letting the queue wake it" and does not nudge. It sends a DM first and falls back to `@worker <idle msg>` in the channel. The watchdog starts before the ramp. — [scripts/pbench_run.sh](https://github.com/microsoft/Agensh/blob/main/scripts/pbench_run.sh)
- Silence watchdog: `MINI_ROUTER_STUCK_MS` defaults to 1,200,000 (20 min). The code logs "acp silence ... force-closing connection" and rejects with "acp prompt stuck: no RX". — [src/acp_socket_channel.ts](https://github.com/microsoft/Agensh/blob/main/mini-router/src/acp_socket_channel.ts), [tools/gen-compose-prod.py](https://github.com/microsoft/Agensh/blob/main/tools/gen-compose-prod.py)
- Deadline prompts (verbatim): "@all **45 minutes left.** Stop dispatching new features. From here the only goal is that root `compile.sh` builds `./executable` and that everything already written is merged to the default branch. Land the open PRs; work that is not merged does not count. If a PR cannot be merged, say so and move on." and "@all **5 minutes left.** Merge anything that is ready right now, then stop. Confirm root `bash compile.sh && ./executable` still works on the default branch and post the final state." — [prompts/deadline-45m.txt](https://github.com/microsoft/Agensh/blob/main/prompts/deadline-45m.txt), [deadline-5m.txt](https://github.com/microsoft/Agensh/blob/main/prompts/deadline-5m.txt)
- "At T = t + 6 h, all agents are terminated and the submission is exported." — [Paper App. C](https://arxiv.org/abs/2609.26781)
- The single-agent baseline needed a stop hook because "a single-agent run can rarely sustain the full 6-hour runtime". Its prompt: "There is always new work -- do not be bounded by the previous plan's scope ... Let's make the 6h fulfilled." The standalone driver "immediately resumes completed turns while more than 60 seconds remain". — [Paper App. C](https://arxiv.org/abs/2609.26781), [scripts/README.md](https://github.com/microsoft/Agensh/blob/main/scripts/README.md)

### Inferences
- Agensh is designed to use a fixed budget, not to stop when done. For tasks with a definite finish line, your port needs an explicit completion condition, such as all acceptance tests passing on `main`, or a quorum `DONE` gist. Agensh offers no template for this.
- The idle nudge is effectively how work keeps being generated after the obvious gaps are claimed. Without it, event-driven agents simply go quiet when no events arrive.

### Gaps
- No data on how often idle nudges or silence force-closes fired.

---

## 8. Results, scaling, small teams (≤10 agents), ablations and failure modes

### Takeaway
Only team sizes 1, 8, 32 and 128 (plus 1,024 on pandoc) are reported. **At 8 agents the gain is small: mean 19.31% → 20.68% (+1.37 pp)**, against 26.52% at 32 and 28.78% at 128. Pandoc alone: 33.89% (1) → 50.94% (128) → 55.06% (1,024). With GPT-6.1-sol, pandoc goes 56.19% (1) → 79.59% (32). There are **no ablations** (no runs without the board, without DMs, without the ramp, or with an orchestrator baseline), **no 2/4/16-agent points**, **no cost or token accounting**, and no systematic failure-mode analysis.

### Cited Findings
- "the mean final test-pass rate across the five tasks increases from 19.31% with 1 agent to 20.68%, 26.52%, and 28.78% with 8, 32, and 128 agents, respectively. Scaling from 1 to 128 agents yields a gain of 9.47 percentage points, or an approximately 49% relative improvement" — [Paper §3.1](https://arxiv.org/abs/2609.26781)
- Latency: "on pandoc, 128 agents exceed a 30% test-pass rate at the 30-minute checkpoint, while 32 and 8 agents first exceed that threshold at the 60- and 90-minute checkpoints, respectively. The single-agent run remains below this threshold throughout the first two hours." — [Paper §3.1](https://arxiv.org/abs/2609.26781)
- Pandoc results: "33.89% with 1 agent to 50.94% with 128 agents and 55.06% with 1,024 agents" (+4.12 pp from 128 to 1,024). — [Paper §3.1](https://arxiv.org/abs/2609.26781)
- README addendum (not in the paper): "With the latest GPT-6.1-sol at high reasoning effort, the six-hour Pandoc test-pass rate rises from 56.19% with 1 agent to 79.59% with 32 agents, a relative improvement of 41.64%." — [Repo README](https://github.com/microsoft/Agensh)
- Tasks were FFmpeg, gromacs, pandoc, PHP-src and ctags, the five hardest of ProgramBench's 200 tasks by SOTA mean pass rate. Reference sizes range from 104k LOC (pandoc) to 2.8M LOC (PHP-src). — [Paper §3, Table 1](https://arxiv.org/abs/2609.26781)
- Experimental conditions: the model was GPT-5.6-sol (high) under Copilot CLI. For 1,024 agents, "we distribute workers across 16 nodes, with 64 agents per node." The canonical-kept pass rate is reported. — [Paper App. C](https://arxiv.org/abs/2609.26781)
- Failure modes mentioned only in passing:
  - a PHP-src approval withdrawn after a counterexample;
  - at 128 agents in pandoc, "After some failures, workers further revised the cooperation protocol";
  - at 1,024 agents, workers "recover and take over the work after another worker's attempt fails".
  - [Paper §3.2](https://arxiv.org/abs/2609.26781)
- The paper's own related work cites Carlini's 16-Claude C-compiler experiment (git repo plus task-lock files, no orchestrator) and STORM (a shared workspace that detects stale or conflicting edits at write time) as closely related designs. — [Paper §4](https://arxiv.org/abs/2609.26781)

### Inferences
- **For ≤10 agents:** the gain from 1→8 is about 7% relative on average. Most of Agensh's benefit appears at 32+ agents on multi-million-LOC targets, at roughly 8–128× the compute of a single agent. Since no cost is reported, the compute-normalized benefit is unknown. A single agent run with best-of-8 or longer budgets was not compared. For a small Deep Agents team, DeLM's own evidence is more relevant: it reports gains at n=2 and n=4 on Terminal-Bench, SWE-bench Verified and ProgramBench, using a hard task queue.
- The 8-agent latency result (30% on pandoc reached at 90 min vs. never in 2h for one agent) suggests small teams help time-to-quality more than final quality.
- The cooperation infrastructure is heavy: Gitea, Mattermost, MySQL, and a router plus shim per agent. At ≤10 agents, most of it can be collapsed: one SQLite board, an in-process message bus, local git with worktrees, and LangGraph threads. The behavioural contract (typed capped gists, advisory or atomic claims, interrupt-priority DMs, the forced-publish nudge, idle nudges, deadline reminders, self-merge after differential verification) is what carries over.

### Gaps
- Per-task numbers for 8/32/128 appear only as figure bars (Figs 5–6). The text extracted from the PDF does not include them.
- No ablations, cost or token figures, variance or seeds, or multiple runs per configuration are reported.

---

## 9. Criticism, follow-up discussion, community reimplementations

### Takeaway
As of 2026-10-26, community discussion is thin and mostly positive amplification. I found no independent reproduction or reimplementation of Agensh. One critical-sounding Towards AI article ("More Agents, Smaller Gains") exists but could not be retrieved. The closest "reimplementations" are the upstream DeLM codebase and its Claude Code/Codex plugin.

### Cited Findings
- Digg aggregation: Elvis (@omarsar0) called it a "Banger paper from Microsoft Research". John Yang (@jyangballin, a ProgramBench author) praised that coordination is "self-determined". Ofir Press (also a ProgramBench author) reposted. The page says "Not enough discussion yet". — [Digg](https://digg.com/ai/ynngx373)
- Hermes-AI news repeats the headline claim ("raising test-pass rates by up to 21 points") from an AlphaSignal summary, with no methodology or criticism. — [hermes-ai.net](https://hermes-ai.net/news/microsoft-s-agensh-runs-1-024-coding-agents-without-a-central-controller/)
- A Towards AI piece titled "More Agents, Smaller Gains: What Agensh, MAST and the Google Study Say About Your Orchestrator" exists in search results. The fetch failed (client error), so its content is unverified. — [Towards AI](https://pub.towardsai.net/more-agents-smaller-gains-what-agensh-mast-and-the-google-study-say-about-your-orchestrator-411be9c77062)
- The paper itself cites "Towards a science of scaling agent systems" (Kim et al., arXiv 2512.08296) as motivation. This is presumably the "Google study" in the Towards AI title. — [Paper refs](https://arxiv.org/abs/2609.26781)
- DeLM offers a plugin to run its collaborating agents inside Claude Code and Codex. — [DeLM repo](https://github.com/yuzhenmao/DeLM)

### Inferences
- The obvious critiques visible from the data are: diminishing returns (+1.37 pp at 8 agents, +2.26 pp from 32→128, +4.12 pp from 128→1,024 on pandoc); no compute normalization or cost reporting; one model family; one benchmark type with a perfect behavioural oracle; single runs; and qualitative-only emergence claims.

### Gaps
- No HN thread, Microsoft Research blog post, or LinkedIn discussion was found. The project page is aka.ms/Agensh, but I fetched neither it nor the replay site.

---

## Appendix-style quick reference for a Deep Agents re-implementation (Inference, derived from the verified mechanisms above)
- **Board tools:** `board_write(type∈{FACT,OBSERVED,FAIL,CLAIM,PATCH_SUMMARY}, content≤100/300, delegation_id, detail?)`, `board_read`, `board_grep(bool expr)`, `board_unfold(labels)`.
  - Server rules: claim TTL of 1h; patch replace per (author, delegation_id); FAIL invalidates the author's own patch; reject placeholder evidence; exact plus anchor-based dedup.
  - Per-agent read cursor for turn-start deltas.
- **Turn-start middleware:** prepend `==== SHARED CONTEXT ====` with the unread delta and the "Read them BEFORE acting..." guidance.
- **Tool-result middleware:** append pending DMs and new peer gists to every tool result. Use a lease or cursor so each notice is delivered once.
- **After-turn hook:** if the agent wrote no gist this turn, send the forced-write nudge.
- **Supervisor process:** startup stagger (30s); idle check (600s, skipped if the inbox is non-empty); stuck-turn timeout (20 min); deadline broadcasts at T−45m and T−5m; export `main` at T.
- **Prompt:** identical for all agents; "N coders, all equal"; the 6-step observe/claim/build/verify/merge/publish cycle; DM only for collisions; no subagent tool.
- **For ≤10 agents, consider** (not evaluated by Agensh): DeLM-style atomic `reserve`/`claim`/`done` with one item per agent; a pre-merge test gate; and a completion condition.
