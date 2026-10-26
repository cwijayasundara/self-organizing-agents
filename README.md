# agora

agora is a supervisor-free multi-agent framework. Peer agents coordinate only through a shared SQLite ledger (a typed board, leased tasks, versioned artifacts and mail), with no coordinator assigning work. A task counts as done only after a reviewer from a different model family approves its artifact and the deterministic validators pass. A runner starts the peers, bounds their episodes and budgets, and stops the run.

## Running locally

Prerequisites: Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/). The tests need no keys; live runs need API keys for the providers your roster uses.

1. Install dependencies (creates `.venv` and installs the `agora` and `agora-eval` commands):

   ```
   uv sync
   ```

2. Add API keys (`.env` is git-ignored; never commit it):

   ```
   cp .env.example .env
   ```

   Fill in `FIREWORKS_API_KEY` (DeepSeek, GLM, MiniMax). `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are only needed for rosters that use Haiku 5.5 or GPT-6 Luna. The default GLM + DeepSeek rosters need only the Fireworks key.

3. Run the offline tests (no network or keys):

   ```
   .venv/bin/python -m pytest -q
   ```

4. Optionally check that your keys and models work (tool calling, tool loop, usage reporting):

   ```
   uv run --env-file .env python scripts/smoke_models.py --roster roster.glm-deepseek.yaml
   ```

   A provider whose key is missing is skipped.

5. Do a live run of the toy example (below). Each run writes its ledger to `runs/<run-id>.sqlite`; pass `--db` or `--run-id` to change that.

## Default models

GLM 5.3 Flash and DeepSeek V4.1 Flash are the default pair: cheap, and two model families so cross-family review holds. The full 10-peer roster is `roster.glm-deepseek.yaml`. `roster.example.yaml` is the five-model reference roster (adds MiniMax, Haiku 5.5, GPT-6 Luna) used by the tests.

## Live run (the toy dossier example)

```
uv run --env-file .env agora run --roster examples/toy_dossier/roster.glm-deepseek.yaml --template examples/toy_dossier/template.yaml --brief examples/toy_dossier/brief.md
```

Exit codes: 0 = done (all required tasks approved), 1 = configuration or usage error, 2 = swarm budget exhausted, 3 = wall-clock timeout, 4 = stalled (no progress).

## Design

The design report is in `reports/Supervisorless self organizing agents.md`. The record of the first live run is in `docs/phase3-toy-run.md`.

## EU market-entry example and evaluation

`examples/eu_market_entry/` holds a 10-agent dossier task (brief, 12-task template, roster) over a synthetic data room with planted facts. Generate a data room and its hidden answer key (the key stays outside the room):

```
python scripts/make_dataroom.py --variant 0 --out data/eu/v0 --gold data/eu_gold/v0.json
```

`agora run ... --domain eu_market_entry` adds the citation and summary-block checks. The evaluation harness compares seven arms at equal budget (single DeepSeek or GLM agent, supervisor-led team, swarms of 10, 5 and 3, and a same-family-review ablation):

```
# free preview: lists the runs and the worst-case cost, needs no keys, creates no files
python -m agora.eval.cli --config examples/eu_market_entry/eval.yaml --dry-run

# live run: keys must be exported in the environment; --max-total-usd is required
set -a; . ./.env; set +a
python -m agora.eval.cli --config examples/eu_market_entry/eval.yaml --arms c0-deepseek,c1-10 --max-total-usd 10
```

Results go to `eval_runs/<name>/` (`results.jsonl`, `texts/`, `ledgers/`, `report.md`). Finished runs are skipped on resume; failed runs are retried; interrupted runs record their spend. Exit codes: 0 finished, 1 usage or config error, 5 stopped by the spend cap, 130 interrupted. The first live pilot is written up in `docs/phase5-eu-pilot.md` ($1.64 for 3 arms; a pipeline check, not a result).

## Known limitations

- The scorer's keyword recall undercounts honest phrasings; `summary_accuracy` and the judge score are the stronger signals. Treat recall as auxiliary.
- The swarm enforces citation and summary-block validators that the baselines only receive as instructions; baselines stop at 90% of budget or 20 episodes; the supervisor's subagent call limit is per delegation. See the report caveats.
- One judge model is used per run (rotation by variant and seed); the pre-registered decision rule needs at least 3 rows per side.
- Optional tasks that peers create during shutdown are refused; any that were already in flight are listed under `unreviewed` in the run result.
- Luna (GPT-6) is configured as a judge and verified in a one-call check, but no full evaluation arm has used it. The `agora-eval` shortcut is only installed after reinstalling the package (`uv sync`); until then use `python -m agora.eval.cli`.
