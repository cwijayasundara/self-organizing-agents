# agora

agora is a supervisor-free multi-agent framework. Peer agents coordinate only through a shared SQLite ledger (a typed board, leased tasks, versioned artifacts and mail), with no coordinator assigning work. A task counts as done only after a reviewer from a different model family approves its artifact and the deterministic validators pass. A runner starts the peers, bounds their episodes and budgets, and stops the run.

## Running locally

Prerequisites: Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/). The tests need no keys; live runs need API keys for the providers your roster uses.

1. Install dependencies (creates `.venv` and installs the `agora` package and the `agora` / `agora-eval` commands into it):

   ```
   uv sync
   ```

2. Add API keys (`.env` is git-ignored; never commit it):

   ```
   cp .env.example .env
   ```

   Fill in `FIREWORKS_API_KEY` (DeepSeek, GLM, MiniMax). `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are only needed for rosters that use Haiku 5.5 or GPT-6 Luna. The default GLM + DeepSeek rosters need only the Fireworks key.

> **Always run through the project environment.** `agora` is installed only inside `.venv`, so a bare `python` (often the system Python, e.g. 3.14) fails with `ModuleNotFoundError: No module named 'agora'`. Prefix commands with `uv run` (as below), or activate the venv first with `source .venv/bin/activate`.

## Testing the framework

Work through these levels in order; each one costs more than the last.

### 1. Offline unit tests (free, no keys, about a minute)

```
uv run python -m pytest -q
```

Verified on 2026-10-27: **584 passed, 1 deselected**. The suite uses fake models (`tests/fakes.py`) to exercise the ledger (board, leased tasks, artifacts, mail), peers, cross-family review, validators, budgets, the runner's stop conditions, agent-profile capture and replay, viewer endpoints, final-result selection, the data-room generator, the scorer and the evaluation harness. Tests marked `live` are skipped by default. Run one area with, for example, `uv run python -m pytest -q tests/test_runner.py`.

### 2. Model smoke check (a few cents, needs keys)

Checks that each model in a roster can call tools, run a tool loop and report token usage:

```
uv run --env-file .env python scripts/smoke_models.py --roster roster.glm-deepseek.yaml
```

A provider whose key is missing is skipped. The same check runs as a pytest test against the five-model reference roster with `uv run --env-file .env python -m pytest -m live -s`.

### 3. Live swarm on the toy dossier (cheap, needs the Fireworks key)

```
uv run --env-file .env agora run --roster examples/toy_dossier/roster.glm-deepseek.yaml --template examples/toy_dossier/template.yaml --brief examples/toy_dossier/brief.md
```

Add `--watch` to follow it in the browser (see [Watching a run](#watching-a-run-progress-log-and-live-view)). Exit codes: 0 = done (all required tasks approved), 1 = configuration or usage error, 2 = swarm budget exhausted, 3 = wall-clock timeout, 4 = stalled (no progress). Each run writes its ledger to `runs/<run-id>.sqlite` (change it with `--db` or `--run-id`); open it with `sqlite3` to inspect tasks, artifacts, reviews and mail. `docs/phase3-toy-run.md` records what a good run looks like.

### 4. Live swarm on the evidence-review sample (4 peers, a few minutes, needs the Fireworks key)

This is the short sample. Corvane Systems, a 600-person firm, must choose `adopt_company_wide`, `pilot_knowledge_teams`, or `do_not_adopt` for a four-day week. Nine files in `examples/evidence_review/sources/` hold the evidence, including a retracted study, an inflated vendor claim, a subgroup hidden by an overall average, and a cost total that does not add up. No data-generation step is needed.

Four peers claim the four starting tasks in parallel. `figures` and `costs` run on DeepSeek; `sources` and `people` run on GLM. The tasks are productivity, source credibility, cost and operations, and wellbeing and retention. A peer from the other model family reviews each artifact. When those four are approved, one peer writes the synthesis memo. Budget is $0.60 and 480 seconds. A finished sample is usually a few minutes and under $0.30.

From the repo root, with `FIREWORKS_API_KEY` set in `.env`:

```
uv run --env-file .env agora run \
  --roster examples/evidence_review/roster.yaml \
  --template examples/evidence_review/template.yaml \
  --brief examples/evidence_review/brief.md \
  --domain evidence_review \
  --watch
```

`--domain evidence_review` checks citations and the `RESEARCH_SUMMARY` block. `--watch` opens the live view. Leave it off for a terminal-only run. `--no-browser` serves the page without opening it. `--port` changes the port (default 8765).

While it runs, stderr is the progress log: episodes, claims, board notes, reviews, and spend. Stdout stays the final status JSON. Exit codes: 0 done, 1 configuration or usage error, 2 budget exhausted, 3 wall-clock timeout, 4 stalled.

When the status is `done`, stderr then prints two blocks:

- `======== problem ========` is the brief the peers were given.
- `======== final output: synthesis@vN (...) ========` is the research memo, including the `RESEARCH_SUMMARY` JSON. `N` is the version that passed review.

The live view shows the same pair in a **Result** panel at the top. Click a task card to read a section artifact. The page stays up until you press Ctrl-C. The ledger is `runs/<run-id>.sqlite`. Reopen it with:

```
uv run agora watch runs/<run-id>.sqlite
```

The answer key is `examples/evidence_review/gold.json`, outside the evidence room. Compare its five fields with the memo's `RESEARCH_SUMMARY` block. `docs/phase6-evidence-review-runs.md` records earlier runs. A ledger written before the Result panel existed still shows the memo; the problem side says the brief was not stored.

### 5. Live swarm on the EU market-entry example (10 peers, needs the Fireworks key)

Generate the synthetic data room and its hidden answer key first (the key stays outside the room). `data/eu/v0` is what `examples/eu_market_entry/roster.yaml` points at via `data_dir`:

```
uv run python scripts/make_dataroom.py --variant 0 --out data/eu/v0 --gold data/eu_gold/v0.json
```

Then run the swarm with the domain validators (citations and summary block):

```
uv run --env-file .env agora run --roster examples/eu_market_entry/roster.yaml --template examples/eu_market_entry/template.yaml --brief examples/eu_market_entry/brief.md --domain eu_market_entry
```

### Watching a run: progress log and live view

`agora run` prints a progress log to stderr while it works (the final JSON result still goes to stdout). Each line is one thing the swarm did: an episode starting, a board note, a direct message, a task being claimed, submitted, sent back or approved, a refused tool call, a runner nudge or budget warning, and the spend every $0.10. Add `-v` to also log every tool call, or `-q` to show warnings only. `-q` still prints the problem and the final artifact once the status is `done`.

Add `--watch` to open a live view of the swarm in your browser:

```
uv run --env-file .env agora run --roster examples/eu_market_entry/roster.yaml --template examples/eu_market_entry/template.yaml --brief examples/eu_market_entry/brief.md --domain eu_market_entry --watch
```

The page (http://127.0.0.1:8765 by default; `--port` changes it, `--no-browser` skips opening it) shows:

- **Swarm graph**: the peers around the shared ledger, colored by model family. A dashed spinning ring means the agent is in an episode. Animated dots show notes going to the board, tasks being claimed, reviews (green for approve, red for reject) and direct messages between peers.
- **Result**: once the run is `done`, the brief and the final artifact. That is the integration task when the template has one (the evidence-review memo, or the toy dossier's `summary`), and otherwise the latest artifact of each required task. The same text is printed to stderr after the status JSON.
- **Task board**: open, claimed, in-review and done tasks, with each task's owner and the tasks it is waiting on. Click a card to read its latest artifact.
- **Agents**: each peer's state, held task, episode count, spend and last action. Click a row (or a graph node) to open its details: model, lens, budget, token usage, system prompt, tool descriptions and input schemas, skills, memory and data access. Use **Filter activity** in the dialog to scope the feed; **Clear filter** restores all agents.
- **Activity feed**: notes, messages, coordination tool calls, episodes and runner actions, newest first, with category filters. Other tool calls, such as file reads, are hidden until you turn them on.

When the run finishes, the page stays up until you press Ctrl-C. To watch a run that is going in another terminal, or to replay a finished one, point `agora watch` at its ledger:

```
uv run agora watch runs/<run-id>.sqlite
```

Both read the SQLite ledger through a separate read-only connection, so watching never affects the agents. Runner and tool activity is recorded in an `events` table of the ledger that peers never read. Ledgers written before that table existed still show tasks, notes and messages, but no episodes or tool calls.

#### Inspecting an agent

Click an agent's graph node or table row to open its details. Graph nodes and rows also support Enter and Space; Escape closes the dialog.

| Section | What it shows |
|---|---|
| Overview | Model, provider and family, lens, status, owned tasks, episode count, spend and peer budget, input/output token totals and prompt token limit. Live values update while the dialog is open. |
| System prompt | The effective system prompt captured at the first model call, with the configured protocol available separately. Before that call, only the configured protocol is shown. |
| Tools | Tool names, descriptions and JSON input schemas. Before the first model call, this lists configured ledger tools; afterward it includes the built-in tools available to the model. The hidden `task` delegation tool is excluded. |
| Skills | **None configured** for agents built by the current peer builder. |
| Memory and data access | How private state is stored, whether it is recorded, and the optional read-only `/data/` mount. |
| Shared memory | All shared board notes, plus messages sent by or addressed to this agent and broadcasts. Each list shows the latest 100 entries; the Ledger dialog provides the full loaded history. |

Use **Filter activity** inside the dialog to scope the feed. Use **Clear activity filter** there or **Clear filter** beside the feed heading to restore all agents.

New runs save agent configuration in `agent_profiles`, then capture the effective prompt and tool list at the first model call. Reopen the dialog to refresh that snapshot. This is a first-call snapshot, not a transcript or a view of the agent's current context. Private conversation checkpoints and scratch files remain in process memory and are not recorded for replay.

The viewer reads these details through `GET /api/agent?id=<agent-id>`. It polls `GET /api/state` for activity, tasks, spend, the stored brief and selected final artifacts; task cards use `GET /api/artifact?task=<task-id>`. These endpoints use read-only ledger connections.

#### Replaying runs and older ledgers

New runs also store the original brief in `run_meta`; the Result panel combines it with artifacts already stored in the ledger. Integration tasks are selected as the final deliverables when present; otherwise required non-review tasks are selected. The panel appears after a `done` run. It does not generate a new answer or call a model.

Older ledgers still show their available tasks, artifacts, notes and messages. Missing agent configuration is labeled **Not recorded**, and a missing stored brief is labeled explicitly in the Result panel. Opening an old ledger does not reconstruct missing metadata. Restart an already-running viewer after upgrading the code, then reload the page; start a new run to capture the new metadata.

### 6. Evaluation harness (compares arms at equal budget)

See [EU market-entry example and evaluation](#eu-market-entry-example-and-evaluation) below. Always start with `--dry-run`, which is free.

## Default models

GLM 5.3 Flash and DeepSeek V4.1 Flash are the default pair: cheap, and two model families so cross-family review holds. The full 10-peer roster is `roster.glm-deepseek.yaml`. `roster.example.yaml` is the five-model reference roster (adds MiniMax, Haiku 5.5, GPT-6 Luna) used by the tests.

## Design

The current implementation and evidence are described in [architecture.md](architecture.md). The original design report is in `reports/Supervisorless self organizing agents.md`. The record of the first live run is in `docs/phase3-toy-run.md`.

## EU market-entry example and evaluation

`examples/eu_market_entry/` holds a 10-agent dossier task (brief, 12-task template, roster) over a synthetic data room with planted facts. Generate the data room for each variant you evaluate (see step 5 of [Testing the framework](#testing-the-framework)); `eval.yaml` reads rooms from `data/eu/v<N>` and keys from `data/eu_gold/v<N>.json`:

```
uv run python scripts/make_dataroom.py --variant 0 --out data/eu/v0 --gold data/eu_gold/v0.json
```

`agora run ... --domain eu_market_entry` adds the citation and summary-block checks. The evaluation harness compares seven arms at equal budget (single DeepSeek or GLM agent, supervisor-led team, swarms of 10, 5 and 3, and a same-family-review ablation):

```
# free preview: lists the runs and the worst-case cost, needs no keys, creates no files
uv run python -m agora.eval.cli --config examples/eu_market_entry/eval.yaml --dry-run

# live run: needs the keys in .env (Fireworks, plus Anthropic/OpenAI for the judges); --max-total-usd is required
uv run --env-file .env python -m agora.eval.cli --config examples/eu_market_entry/eval.yaml --arms c0-deepseek,c1-10 --max-total-usd 10
```

Results go to `eval_runs/<name>/` (`results.jsonl`, `texts/`, `ledgers/`, `report.md`). Finished runs are skipped on resume; failed runs are retried; interrupted runs record their spend. Exit codes: 0 finished, 1 usage or config error, 5 stopped by the spend cap, 130 interrupted. The first live pilot is written up in `docs/phase5-eu-pilot.md` ($1.64 for 3 arms; a pipeline check, not a result).

## Known limitations

- The scorer's keyword recall undercounts honest phrasings; `summary_accuracy` and the judge score are the stronger signals. Treat recall as auxiliary.
- The swarm enforces citation and summary-block validators that the baselines only receive as instructions; baselines stop at 90% of budget or 20 episodes; the supervisor's subagent call limit is per delegation. See the report caveats.
- One judge model is used per run (rotation by variant and seed); the pre-registered decision rule needs at least 3 rows per side.
- Optional tasks that peers create during shutdown are refused; any that were already in flight are listed under `unreviewed` in the run result.
- Luna (GPT-6) is configured as a judge and verified in a one-call check, but no full evaluation arm has used it. The `agora-eval` shortcut is only installed after reinstalling the package (`uv sync`); until then use `uv run python -m agora.eval.cli`.
