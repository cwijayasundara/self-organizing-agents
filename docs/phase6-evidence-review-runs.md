# Phase 6: evidence-review demo (4 live runs)

A demo-sized example to replace the EU market-entry run for live showings. The EU swarm took 759 s in the Phase 5 pilot, mostly because its task graph is four levels deep and each level waits for a review. This example has one level of four parallel tasks plus one integration task, so peers spend their time working and reviewing rather than waiting for dependencies.

## Setup

- Example: `examples/evidence_review/` (brief, 5-task template, 4-peer roster, answer key `gold.json` outside the evidence room).
- Evidence room: `examples/evidence_review/sources/`, nine short static files (three studies, a retraction notice, a vendor white paper, a news article, a staff survey and a cost sheet). No generation step.
- Planted findings: a retracted study (`studies/okafor_lind_2024.md`) still cited by the news article, a vendor headline (+40%) that its own table contradicts (+4.1%), a subgroup (customer-support shift staff, -8.7%) hidden by an overall +0.0%, and a cost total that is 72,000 EUR short of its line items.
- Peers: R1 and R3 DeepSeek V4.1 Flash, R2 and R4 GLM 5.3 Flash. The roster now calls the same four seats `figures`, `sources`, `costs`, and `people`. Budget $0.60, 480 s wall clock, `stagger_s` 3, `idle_poll_s` 6, `stall_after_s` 150. The table below keeps the ids those runs actually used.
- Command:
  `uv run --env-file .env agora run --roster examples/evidence_review/roster.yaml --template examples/evidence_review/template.yaml --brief examples/evidence_review/brief.md --domain evidence_review --run-id evr<N>`

## Results

| Run | Status | Time | Spend | Episodes (R1/R2/R3/R4) | Rejections | FACT notes | Summary answers correct | Memo words |
|---|---|---|---|---|---|---|---|---|
| `evr1` | done | 140 s | $0.182 | 2/1/3/2 | 0 | 8 | 5 of 5 | 409 |
| `evr2` | done | 266 s | $0.226 | 4/2/4/5 | 2 (`productivity`, `synthesis`) | 11 | 5 of 5 | 429 |
| `watch` (before fixes, run from the README command) | done | 272 s | $0.210 | 4/4/5/2 | 2 (`synthesis` v1 and v2: both auto-rejected by the validator; v1 also for a real 364,000 vs 404,000 EUR error) | 15 | 5 of 5 | n/a |
| `evr3` (after fixes 1 and 2) | done | 182 s | $0.219 | 2/2/4/2 | 0 | 12 | 5 of 5 | 360 |
| `evr4` (after all fixes) | done | 109 s | $0.118 | 1/3/2/3 | 0 | 9 | 5 of 5 | 415 |

The `watch` run was started with `--watch` and its ledger is `runs/20261027T062955458761Z.sqlite`. All ledgers are in `runs/` (git-ignored). `evr1`/`evr2` scores come from the saved final artifact. Every approval was cross-family. No peer retired or ran out of budget.

## What the runs show

- **Shared findings on the board:** in both runs the source-credibility peer posted the retraction, the inflated vendor claim, the subgroup and the cost gap as FACT notes before the synthesis started, and the synthesis used all four.
- **Peers correcting each other:** in `evr2` the cost peer's artifact put shift-department staffing at 352,000 EUR. Two other peers posted FACT corrections (364,000 EUR, or 404,000 EUR with overtime), and the cost peer then posted its own correction.
- **Review with consequences:** in `evr2` two reviews rejected work for unmet acceptance criteria (for example, the synthesis did not cite every section by task id), and the authors revised and resubmitted.
- **Bad data caught:** in `evr1` a peer found an unplanted inconsistency in the first version of `studies/nordvik_2025.md` (a 20% cut in hours cannot give both +6.1% per hour and -0.4% per employee). The file was corrected before `evr2` by adding the hours actually worked (38.6 to 36.3) and changing the per-hour figure to +5.9%.

## Fixes made after the `watch` run

The `watch` run (the README command) needed three synthesis versions, with about two dozen of its log lines being refused writes (length limits and missing citations). Causes and fixes:

1. **Quoted number in the brief.** The brief's template showed `"cost_mismatch_eur": "<number>"`, so the author wrote the string `"72000"`, which the validator rejects. Fixed in this brief and in the EU brief (`arith_mismatch_eur` had the same trap); the validator message now names the field (`cost_mismatch_eur must be a JSON number without quotes, got "72000"`).
2. **Unstated write limits.** The peer protocol now lists the note and DM length limits and says a FACT's citation belongs in `detail`; a test keeps those numbers equal to the real constants.
3. **Smaller follow-ups.** The citation refusal now says the citation must be in square brackets; `board_grep`'s description now gives its query syntax (the "grep before you post a FACT" line in the protocol had caused three malformed queries in `evr3`).

Effect: synthesis passed on its first version in `evr3` and `evr4`; refused length-limit writes went from about two dozen in the `watch` run to 0 in `evr3` and 3 in `evr4` (two PATCH_SUMMARY, 5 and 88 characters over, and one CLAIM, 2 over). `evr3` was run before fix 3, `evr4` after it. Time and cost vary run to run (109 to 272 s here), so these four runs show the direction, not a measured saving.

## Remaining friction

- Peers still try to claim tasks whose dependencies are not done (3-5 per run), and some post the same FACT twice. Neither blocks the run.
- Run time depends mostly on how many review rounds the synthesis needs.
