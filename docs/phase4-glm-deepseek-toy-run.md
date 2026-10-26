# Phase 4 toy run with GLM 5.3 Flash and DeepSeek V4.1 Flash

## Setup

Roster `examples/toy_dossier/roster.glm-deepseek.yaml`: T01 deepseek, T02 glm (family `zhipu`), T03 deepseek. Two families. Budget swarm_usd 2, peer_usd 0.8, wall_clock_s 1200. Template and brief as in the earlier toy runs. Keys were loaded from `.env` into the process environment and are not recorded.

```
.venv/bin/python -m agora.cli run --roster examples/toy_dossier/roster.glm-deepseek.yaml \
  --template examples/toy_dossier/template.yaml --brief examples/toy_dossier/brief.md --run-id glmds1
```

## Outcome

Exit code 0. Ledger `runs/glmds1.sqlite` (git-ignored, not committed).

```json
{"db": "runs/glmds1.sqlite", "done": {"done": true, "missing": []}, "elapsed_s": 112.16,
 "episodes": {"T01": 3, "T02": 1, "T03": 1}, "exhausted": [], "retired": [],
 "run_id": "glmds1", "spent_usd": 0.089648718, "status": "done"}
```

Spend by peer: T01 deepseek $0.0429 (26 calls), T02 glm $0.0116 (18), T03 deepseek $0.0351 (17). Total $0.090 of $2, in 112 s of 1200 s. No peer retired or exhausted.

## Tasks

| Task | Kind | Status | Author (family) | Reviewer (family) |
|---|---|---|---|---|
| competitors | work | done | T02 (zhipu) | T01 (deepseek) |
| pricing | work | done | T01 (deepseek) | T02 (zhipu) |
| summary | integration | done | T02 (zhipu) | T01 (deepseek) |
| sub:T03:1 (peer-created, not required) | work | in_review | T03 (deepseek) | none (review task `review:sub:T03:1:1` still open) |

## Reviews

Three REVIEW notes, all APPROVE: note 6 T01 on competitors, note 7 T02 on pricing, note 10 T01 on summary. Every approval is cross-family (zhipu authored, deepseek reviewed, and the reverse); the `author_family` and `owner_family` columns on the review tasks confirm it. No rejections. Reviewers re-derived the numbers (floor 4.00 / (1 - 0.60 - 0.03) = 10.81, so 10.82).

## Final recommendation

12.00 EUR per seat per month: 63.7% gross margin, above the 10.82 floor, inside the competitor centre band 11.50-12.50 (ladder 8.00 / 12.50 / 15.00). Risk named: Notiva's 8.00 entry price. It cites `competitors@v1` and `pricing@v1`.

## Observations

- Notes: 2 CLAIM, 2 FACT, 1 OBSERVED, 4 PATCH_SUMMARY, 3 REVIEW.
- Unexpected: T03 (deepseek) created an optional task `sub:T03:1` that duplicated the summary. It ended `in_review` with an open review task and no reviewer, the known shutdown-grace limitation from Plan 2. It is not required, so the run is `done`. T03 then wrote a FACT noting both summaries pick 12.00.
- T01 ran 3 episodes (earlier toy run: 2); T03 did no required work, with all three required tasks taken by T01 and T02.
- With only two families, every review is forced to the other family, so one family is always the reviewer; fine here, but a 10-peer run will depend on the deepseek/glm split staying balanced.
- Cost is comparable to the three-family Fireworks run ($0.077).
