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

### 1. Offline unit tests (free, no keys, ~35 s)

```
uv run python -m pytest -q
```

Expect about 544 passed and 1 deselected. The suite uses fake models (`tests/fakes.py`) to exercise the ledger (board, leased tasks, artifacts, mail), peers, cross-family review, validators, budgets, the runner's stop conditions, the data-room generator, the scorer and the evaluation harness. Tests marked `live` are skipped by default. Run one area with, for example, `uv run python -m pytest -q tests/test_runner.py`.

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

### 4. Live swarm on the evidence-review demo (4 peers, a few minutes, needs the Fireworks key)

The quickest realistic run, sized for demos: a small research question ("should a 600-person firm adopt a four-day week?") over nine short files in `examples/evidence_review/sources/`, with a retracted study, an inflated vendor claim, a subgroup hidden by an overall average and a total that does not add up. Four peers take the four starting tasks (productivity, wellbeing, cost, source credibility) in parallel, review each other across families, and one of them writes the synthesis. The answer key is `examples/evidence_review/gold.json`, outside the evidence room. No data generation step is needed:

```
uv run --env-file .env agora run --roster examples/evidence_review/roster.yaml --template examples/evidence_review/template.yaml --brief examples/evidence_review/brief.md --domain evidence_review --watch
```

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

`agora run` prints a progress log to stderr while it works (the final JSON result still goes to stdout). Each line is one thing the swarm did: an episode starting, a board note, a direct message, a task being claimed, submitted, sent back or approved, a refused tool call, a runner nudge or budget warning, and the spend every $0.10. Add `-v` to also log every tool call, or `-q` to show warnings only.

Add `--watch` to open a live view of the swarm in your browser:

```
uv run --env-file .env agora run --roster examples/eu_market_entry/roster.yaml --template examples/eu_market_entry/template.yaml --brief examples/eu_market_entry/brief.md --domain eu_market_entry --watch
```

The page (http://127.0.0.1:8765 by default; `--port` changes it, `--no-browser` skips opening it) shows:

- **Swarm graph**: the peers around the shared ledger, colored by model family. A dashed spinning ring means the agent is in an episode. Animated dots show notes going to the board, tasks being claimed, reviews (green for approve, red for reject) and direct messages between peers.
- **Task board**: open, claimed, in-review and done tasks, with each task's owner and the tasks it is waiting on. Click a card to read its latest artifact.
- **Agents**: each peer's state, held task, episode count, spend and last action. Click a row (or a node) to filter the activity feed to that agent.
- **Activity feed**: notes, messages, coordination tool calls, episodes and runner actions, newest first, with category filters. Other tool calls, such as file reads, are hidden until you turn them on.

When the run finishes, the page stays up until you press Ctrl-C. To watch a run that is going in another terminal, or to replay a finished one, point `agora watch` at its ledger:

```
uv run agora watch runs/<run-id>.sqlite
```

Both read the SQLite ledger through a separate read-only connection, so watching never affects the agents. Runner and tool activity is recorded in an `events` table of the ledger that peers never read. Ledgers written before that table existed still show tasks, notes and messages, but no episodes or tool calls.

### 6. Evaluation harness (compares arms at equal budget)

See [EU market-entry example and evaluation](#eu-market-entry-example-and-evaluation) below. Always start with `--dry-run`, which is free.

## Default models

GLM 5.3 Flash and DeepSeek V4.1 Flash are the default pair: cheap, and two model families so cross-family review holds. The full 10-peer roster is `roster.glm-deepseek.yaml`. `roster.example.yaml` is the five-model reference roster (adds MiniMax, Haiku 5.5, GPT-6 Luna) used by the tests.

## Design

The design report is in `reports/Supervisorless self organizing agents.md`. The record of the first live run is in `docs/phase3-toy-run.md`.

## EU market-entry example and evaluation

`examples/eu_market_entry/` holds a 10-agent dossier task (brief, 12-task template, roster) over a synthetic data room with planted facts. Generate the data room for each variant you evaluate (see step 4 of [Testing the framework](#testing-the-framework)); `eval.yaml` reads rooms from `data/eu/v<N>` and keys from `data/eu_gold/v<N>.json`:

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
