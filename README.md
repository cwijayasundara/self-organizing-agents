# agora

agora is a supervisor-free multi-agent framework. Peer agents coordinate only through a shared SQLite ledger (a typed board, leased tasks, versioned artifacts and mail), with no coordinator assigning work. A task counts as done only after a reviewer from a different model family approves its artifact and the deterministic validators pass. A runner starts the peers, bounds their episodes and budgets, and stops the run.

## Setup

```
uv sync
cp .env.example .env   # then fill in your API keys; never commit .env
```

## Tests (offline, no network or keys)

```
.venv/bin/python -m pytest -q
```

## Default models

GLM 5.3 Flash and DeepSeek V4.1 Flash are the default pair: cheap, and two model families so cross-family review holds. The full 10-peer roster is `roster.glm-deepseek.yaml`. `roster.example.yaml` is the five-model reference roster (adds MiniMax, Haiku 5.5, GPT-6 Luna) used by the tests.

## Live run (the toy dossier example)

```
uv run --env-file .env agora run --roster examples/toy_dossier/roster.glm-deepseek.yaml --template examples/toy_dossier/template.yaml --brief examples/toy_dossier/brief.md
```

Exit codes: 0 = done (all required tasks approved), 1 = configuration or usage error, 2 = swarm budget exhausted, 3 = wall-clock timeout, 4 = stalled (no progress).

## Design

The design report is in `reports/Supervisorless self organizing agents.md`. The record of the first live run is in `docs/phase3-toy-run.md`.

## Known limitations / Plan 2

Optional tasks that peers create and submit during the shutdown grace window can end `in_review` with no reviewer. The Haiku and Luna roster (`examples/toy_dossier/roster.yaml`) has not been verified in a live run. Other review findings are triaged to Plan 2.
