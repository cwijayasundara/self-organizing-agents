# Phase 3 toy dossier live run

## Setup

Roster `examples/toy_dossier/roster.fireworks.yaml` (Fireworks only; the `.env` keys for Anthropic and OpenAI were not usable, so the planned haiku/luna roster `roster.yaml` was not run live). Peers: T01 deepseek, T02 minimax, T03 glm (family `zhipu`), so three families. Budget: swarm_usd 2, peer_usd 0.8, wall_clock_s 1200. Template: `competitors` and `pricing` (parallel) and `summary` (integration, depends on both).

Command (the Fireworks key came from the shell environment and is not recorded anywhere):

```
.venv/bin/python -m agora.cli run --roster examples/toy_dossier/roster.fireworks.yaml \
  --template examples/toy_dossier/template.yaml --brief examples/toy_dossier/brief.md --run-id toy1
```

## Outcome

Exit code 0, status `done`. Ledger: `runs/toy1.sqlite` (git-ignored, not committed).

```json
{"status": "done", "spent_usd": 0.076934228, "elapsed_s": 138.2,
 "episodes": {"T01": 2, "T02": 1, "T03": 1}, "retired": [], "done": {"done": true, "missing": []}}
```

Spend by peer (spend table): T01 deepseek $0.0392 (23 model calls), T02 minimax $0.0213 (24), T03 glm $0.0164 (19). Total $0.077 of $2, in 138 s of 1200 s.

## Tasks

| Task | Kind | Status | Author (family) | Reviewer (family) |
|---|---|---|---|---|
| competitors | work | done | T02 (minimax) | T03 (zhipu) |
| pricing | work | done | T01 (deepseek) | T03 (zhipu) |
| summary | integration | done | T03 (zhipu) | T01 (deepseek) |
| sub:T02:1 (peer-created: price ladder) | work, not required | in_review | T02 (minimax) | none yet (review task open) |

## Reviews

Every approval was by a different family than the author: 3 `REVIEW` APPROVE notes (note 5 T03 on pricing, note 9 T03 on competitors, note 12 T01 on summary), and the `author_family` and reviewer `owner_family` columns on the review tasks confirm it. No reviews were rejected. The reviewers re-derived the numbers (price floor 4.00 / (1 - 0.60 - 0.03) = 10.81, so 10.82; competitor margins 47 / 65 / 70.3%). The final recommendation is 12.50 EUR per seat per month (65.0% gross margin, above the floor, median of the competitors), citing `pricing@v1` and `competitors@v1`, with a Notiva-undercut risk.

## Episodes and retirements

T01 2, T02 1, T03 1 episodes; no peer retired. Notes: 2 CLAIM, 3 FACT, 7 PATCH_SUMMARY, 3 REVIEW.

## Observations

- Right: no coordinator, yet the three peers split the work with no duplicate claims, reviewed each other across families and finished in under 2.5 minutes at under 4% of budget. The task was easy and the checks were deterministic arithmetic, so this shows the plumbing works, not that the swarm is better than a single agent.
- Right: no errors, retries, nudges or retirements were visible in the trace.
- Peers can create tasks: T02 added a non-required task `sub:T02:1` (price ladder and discount guardrails, recommending 11.99) after finishing `competitors`. It was committed and submitted for review only after the run had already reached done, about 3 s after the summary approval, during the shutdown grace window, so no peer could review it. It therefore ended `in_review` with an open review task; `done` only needs required tasks. This is harmless for done, but the summary's 12.50 and the unreviewed sub-task's 11.99 recommendation disagree, and the unreviewed one is not part of the final artifact. Worth considering in Plan 2: whether unreviewed optional work should block or be flagged at done.
- The offline-style timing defaults (stagger 12 s, idle poll 15 s) were not an issue here.
- The haiku/luna roster (`roster.yaml`) is covered only by the offline load test; it was not exercised live.
