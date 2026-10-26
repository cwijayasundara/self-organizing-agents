# Phase 5: EU market-entry pilot (3 arms, 1 data room, 1 run each)

This is a **pipeline check, not a result**. With n = 1 per arm the pre-registered decision rule returns "inconclusive" by design, and the keyword recall metric is known to undercount (see the hand check below). What the pilot shows is that the whole stack runs end to end on real models, what each arm costs, and what to look at in a larger study.

## Setup

- Command (keys exported from `.env` into the process environment; never printed):
  `python -m agora.eval.cli --config examples/eu_market_entry/eval.yaml --arms c0-deepseek,c1-10,c3-supervisor --max-total-usd 10`
- Data room: variant 0 (synthetic, generated deterministically; the answer key is stored outside the data room). Gold for this variant: blocker country Germany, anomalous segment SMB, undercutting competitor Notiva, hiring-table mismatch 70,494 EUR, misleading interview `interview_01`, country order Spain, France, Netherlands, Poland, Germany.
- Every arm: same brief and data room (read-only), budget $3 per run, 1500 s wall clock, per-episode step limit 100. Team models: DeepSeek V4.1 Flash 1017 and GLM 5.3 Flash. Judge for this pilot: Claude Haiku 5.5 (a single judge; the rotation picks it for variant 0, seed 0).
- Hard cap for the whole pilot: $10. Actual total including judge calls: **$1.64**.

## Results

| Arm | Status | Spend | Time | Planted facts found (keyword) | Summary answers correct | Citations that resolve | Judge (1-5) |
|---|---|---|---|---|---|---|---|
| `c0-deepseek` (single agent) | finished (said FINAL after 2 episodes) | $0.205 | 519 s | 5 of 5 | 5 of 5 | 33 of 33 | 4.0 |
| `c1-10` (10-agent swarm) | done (dossier task accepted, all 12 tasks done) | $1.053 | 759 s | 4 of 5 (missed: churn anomaly) | 5 of 5 | 25 of 25 | 4.4 |
| `c3-supervisor` (supervisor + 4 specialists + general-purpose helper) | finished (2 episodes) | $0.379 | 865 s | 4 of 5 (missed: misleading quote) | 5 of 5 | 23 of 23 | 3.0 |

Decision rule output: **inconclusive** (needs at least 3 ok rows per side). Judge spend was about $0.0006 per run.

## Hand check of the two "missed" facts

Reading the saved dossiers (`eval_runs/pilot/texts/`, git-ignored) shows both misses are false negatives of the per-line keyword matcher, not missed findings:

- **Swarm, `churn_anomaly`:** the dossier lists "SMB churn concentration" as a risk and names SMB as the anomalous segment in its summary block. It does not put a marker such as "higher" or "4x" on the same line as "SMB" and "churn".
- **Supervisor, `misleading_quote`:** the dossier flags the lone "+40%" willingness-to-pay statement as coming from a churned account (the planted contradiction), but cites other interview files and never names `interview_01`.

So the keyword recall understates every arm. `summary_accuracy` (exact comparison of the five answers in the summary block) and the judge score are the stronger signals; all three arms scored 5 of 5 on the summary block.

## Observations

- **Cost of coordination:** the swarm cost about 5 times the single agent ($1.05 vs $0.21) and about 2.8 times the supervisor arm for dossiers of similar factual quality on this data room. This is consistent with published findings that decentralized teams carry overhead. One run per arm cannot say whether the quality difference the judge saw (4.4 vs 4.0 vs 3.0) is real.
- **Swarm health:** all 10 peers ran (episodes per peer 2-9), none retired or exhausted, no errors, no unreviewed optional tasks, `final_source` was the accepted dossier. The validators and cross-family review did their job (the dossier task needed two review rounds).
- **Spend accounting:** the swarm's ledger figure ($1.025) was about 2.7% below the model-level meter ($1.053); the gap is the calls the ledger does not see (summarization). The meter figure is the one reported.
- **Limits not binding:** nobody got near $3 or 1500 s, so the budget and wall clock never cut any arm short in this pilot.
- **Judge and parsing:** the judge returned parseable scores for all three dossiers; no judge failure notes.
- **Length:** with the equal 700-word limit in the brief, dossiers were 628 (swarm) and 732 (supervisor, about 5% over) words.

## Fairness asymmetries that still apply (state these with any result)

- The swarm enforces domain validators (citations resolve, summary block present) that the baselines only receive as instructions.
- The baselines stop voluntarily at 90% of budget or after 20 episodes; the swarm stops on done, budget, timeout or stall. Neither limit was reached in the pilot.
- The supervisor's subagent call limit applies per delegation (about 1.5 times the single arm's per-episode calls under the approximate step mapping); cumulative bounds are budget and wall clock only.
- Per-peer swarm budget is budget / 4.
- Keyword detectors are per-line matches with known false negatives; one judge per run.
- The swarm runs with no shutdown grace period (`grace_s = 0`) to match the hard-cut baselines.

## What the pilot cannot say, and what to do next

- No swarm-versus-baseline conclusion: n = 1, one data-room variant, one judge, one seed.
- The decision rule needs at least 3 rows per side and a GLM baseline row. The next step is a larger study (for example 3 to 5 variants x 3 seeds x all 7 arms: at the pilot's per-run costs one full set of 7 arms is roughly $4-5, so about $40-65 plus judge calls, dominated by the swarm arms), run only after the spend is confirmed.
- Before that, settle the open design question from the final review: the pre-registered rule requires both margins for a win and both for a loss, and recall (keyword) should probably not be a primary metric. Consider `summary_accuracy` plus the judge as primary, and re-score saved texts with the widened detectors.
