# EU Market-Entry Example and Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the `agora` framework to a 10-agent EU market-entry dossier over a synthetic data room with planted facts, and build an evaluation that tests whether the self-organizing team beats a single agent and a supervisor-led team at equal budget.

**Architecture:** A deterministic data-room generator writes CSV and Markdown files plus a hidden gold key (planted facts and expected answers). The 12-task dossier template, a GLM+DeepSeek 10-peer roster and domain checks (citations that resolve to data-room files, a machine-readable summary block) run on the existing framework. An evaluation harness runs seven arms (two single-agent baselines, a supervisor team, swarms of 10, 5 and 3 peers, and a same-family-review ablation) through one budget meter, scores each dossier deterministically against the gold key, and adds a cross-vendor LLM-judge score. The framework gains the fixes the two live runs called for.

**Tech Stack:** Python 3.12, existing agora stack (deepagents 0.7.32, langchain 1.4.7, langgraph 1.2.17), stdlib `csv`/`json`/`hashlib`/`random`, pydantic v2, PyYAML, pytest. No new third-party dependencies.

**Spec:** `reports/Supervisorless self organizing agents.md` (sections "Ten peers build an EU market-entry dossier from a sealed data room" and "A budget-matched single agent is the bar the swarm must clear"); `docs/research/Self organizing deep agents approach.md` (evaluation arms, error injection, negative control); `docs/superpowers/plans/2026-10-26-agora-framework-core.md` (Plan 1); `docs/phase3-toy-run.md` and `docs/phase4-glm-deepseek-toy-run.md` (live findings).

**Scope decisions (the user can overrule):**
- The public benchmarks (Finance Agent Benchmark slice, DABstep negative control) are **out of scope** here. They need external downloads and their own graders; they become Plan 3.
- MAST failure tagging and human grading are deferred; the harness stores each dossier and ledger path so both can be added later.
- The team models are GLM 5.3 Flash and DeepSeek V4.1 Flash (the user's choice). Judges are Claude Haiku 5.5 and GPT-6 Luna, which are not on the team.

## Global Constraints

- Python `>=3.12,<3.14`; runtime pins from Plan 1 unchanged (`deepagents==0.7.32`, `langchain==1.4.7`, `langchain-core==1.7.0`, `langgraph==1.2.17`, `langchain-fireworks==1.7.1`, `langchain-anthropic==1.7.6`, `langchain-openai==1.7.2`). No new dependencies.
- Candidate countries, exactly: `Germany, France, Netherlands, Spain, Poland`. Segments, exactly: `SMB, Mid-market, Enterprise`.
- The gold key is **never** inside a data room directory and never in any prompt, template or brief given to a team arm. It is only read by the scorer and the judge.
- The final dossier must contain one fenced JSON block directly after the line `DOSSIER_SUMMARY` with exactly these keys: `recommendation` (`"enter"` or `"hold"`), `country_order` (list of the 5 candidate countries, best first), `blocker_country`, `anomaly_segment`, `undercutting_competitor`, `arith_mismatch_eur` (number).
- Data-room citations in agent text use the form `[file.ext]` or `[file.ext:detail]`, where `file.ext` is a path relative to the data-room root ending in `.csv` or `.md`.
- Every arm receives the same budget: `budget_usd` and `wall_clock_s` from the eval config. Defaults: `3.0` USD and `1500` s per run.
- Cross-family review stays on in every swarm arm except the ablation arm `a1-same-family`.
- Live model calls only happen in Task 14, only with `--max-total-usd`, and only after the user confirms the spend. API keys come from the environment (`uv run --env-file .env ...`); never print, log or write them.
- Generated data (`data/`) and evaluation output (`eval_runs/`) are git-ignored.
- Run tests with `.venv/bin/python -m pytest -q` (if `import agora` fails on macOS, run `chflags -R nohidden .venv`).

## Review Focus

1. **Gold-key leakage.** A planted-fact answer visible to the agents makes the whole evaluation meaningless. Tests: gold path inside the data room is refused (Task 3); no gold string appears in any generated data-room file or in `brief.md` (Task 4, Task 6).
2. **Surprise spend.** An eval matrix can cost hundreds of dollars. Tests: `--dry-run` prints worst-case cost; a live run without `--max-total-usd` is refused; the run stops before starting a run it cannot afford (Task 13).
3. **Scorer false positives.** A dossier that mentions a country without the blocker, or a number without context, must not count as finding the fact. Negative tests (Task 7).
4. **Judge failures scored as zero.** An unparsable judge reply must be recorded as missing, never as a low score (Task 8).
5. **Unequal budgets across arms.** A baseline that overspends or ignores the wall clock invalidates the comparison. Tests: the meter hard-stops at the cap and the single and supervisor arms stop on wall-clock (Tasks 9-11).
6. **Resumed evaluations double-counting.** A resumed run must skip finished (arm, variant, seed) rows (Task 13).

---

## File Structure

```
src/agora/api.py                       # run_swarm / arun_swarm, SwarmOutcome (extracted from cli)
src/agora/domain.py                    # citation resolver, FACT admission, summary-block validator, domain registry
src/agora/dataroom/__init__.py
src/agora/dataroom/models.py           # PlantedFact, GoldKey
src/agora/dataroom/generate.py         # generate_dataroom(variant, out_dir, gold_path) -> GoldKey
src/agora/eval/__init__.py
src/agora/eval/config.py               # EvalConfig, ArmBudget
src/agora/eval/scoring.py              # Scores, score_dossier
src/agora/eval/judge.py                # RUBRIC, JudgeResult, judge_dossier, pick_judge
src/agora/eval/meter.py                # BudgetExceeded, SpendMeter
src/agora/eval/arms/__init__.py        # ARM_IDS, run_arm dispatcher
src/agora/eval/arms/types.py           # ArmOutcome
src/agora/eval/arms/single.py          # run_single_arm (+ shared episode driver)
src/agora/eval/arms/supervisor.py      # run_supervisor_arm
src/agora/eval/arms/swarm.py           # build_swarm_roster, run_swarm_arm
src/agora/eval/runner.py               # run_eval, ResultRow (JSONL, resume, spend cap)
src/agora/eval/report.py               # aggregate, decide, render_markdown
src/agora/eval/cli.py                  # agora-eval entry point
examples/eu_market_entry/{brief.md,template.yaml,roster.yaml,eval.yaml}
scripts/make_dataroom.py
tests/test_api.py test_closing.py test_dataroom.py test_domain.py test_eu_assets.py
tests/test_scoring.py test_judge.py test_meter.py test_arms_single.py test_arms_supervisor.py
tests/test_arms_swarm.py test_eval_runner.py test_eval_report.py test_eval_cli.py
```

Modified: `src/agora/cli.py`, `src/agora/ledger/__init__.py`, `src/agora/ledger/tasks.py`, `src/agora/runner.py`, `src/agora/protocol.py`, `pyproject.toml`, `.gitignore`, `README.md`, existing tests that assert the old CLI output.

---

### Task 1: `run_swarm` API, admission wiring, JSON-only CLI

**Files:**
- Create: `src/agora/api.py`, `tests/test_api.py`
- Modify: `src/agora/ledger/__init__.py`, `src/agora/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `open_ledger`, `make_peer`, `SwarmRunner`, `load_roster`, `load_template`, `seed_tasks`, `build_model`.
- Produces:
  - `open_ledger(..., admission: Sequence[Admission] = ())` passes `admission` to `Board(...)`.
  - `@dataclass(frozen=True) class SwarmOutcome: result: RunResult; ledger: Ledger; db_path: str`
  - `async def arun_swarm(roster: RosterConfig, specs: list[TaskSpec], brief: str, db_path: str, *, models: dict[str, BaseChatModel] | None = None, validators: Sequence[Validator] = (), admission: Sequence[Admission] = (), runner_kwargs: dict | None = None) -> SwarmOutcome`
  - `def run_swarm(...) -> SwarmOutcome` with the same parameters (wraps `asyncio.run`).
  - `models` maps roster model keys to chat models; when absent, models are built with `build_model` for the keys used by peers only. `runner_kwargs` is passed to `SwarmRunner` (tests inject a fast clock, `grace_s`).
  - CLI stdout becomes ONE JSON object: the existing `RunResult` fields plus `run_id`, `db`, and `tasks: [{"id","kind","required","status","artifact_id"}]` (artifact_id null when none). The TSV table is removed.

- [ ] **Step 1: Write the failing tests** in `tests/test_api.py`:
  - `test_run_swarm_offline_uses_injected_models`: roster from `roster.example.yaml` trimmed to 2 peers on 2 families via `model_copy`, `ScriptedChatModel`s injected through `models=`, tiny `wall_clock_s`, `runner_kwargs={"grace_s": 0.1}`; assert `outcome.result.status == "timeout"` and the sqlite file exists.
  - `test_admission_is_applied`: pass an admission hook that rejects every `FACT`; assert `outcome.ledger.board.write_note("P01","FACT","x")` raises `LedgerError` matching `admission`.
  - `test_unused_model_not_built`: a roster model whose key is absent from the environment and unused by peers does not raise.
  In `tests/test_cli.py` update the existing offline test to `json.loads(stdout)` and assert `"tasks"` is a list of dicts with the five keys; add `test_cli_stdout_is_pure_json` asserting `json.loads(capsys.readouterr().out)` succeeds.

- [ ] **Step 2: Run them.** `.venv/bin/python -m pytest tests/test_api.py tests/test_cli.py -q`. Expected: FAIL (no `agora.api`).

- [ ] **Step 3: Implement** `agora/api.py` by moving the body of `cli._run` after config loading (ledger path check stays in the CLI), and have `cli._run` call `run_swarm`. Keep exit-code mapping and error handling unchanged. Wire `admission` through `open_ledger`.

- [ ] **Step 4: Run the full non-live suite.** Expected: all pass.

- [ ] **Step 5: Commit.** `git commit -m "feat: run_swarm API with injectable models, admission wiring, JSON-only CLI"`

---

### Task 2: Closing flag, unreviewed work, runner errors, duplicate-task rule

**Files:**
- Modify: `src/agora/ledger/tasks.py`, `src/agora/runner.py`, `src/agora/protocol.py`
- Test: `tests/test_closing.py`; update `tests/test_runner.py`, `tests/test_peer.py` only where counts or text change

**Interfaces:**
- Produces:
  - `TaskLedger.closed: bool` (default False) and `TaskLedger.close() -> None`. When closed, `reserve` and `submit_for_review` raise `LedgerError("run is closing: no new tasks or submissions")`. `create_task` (template seeding), `commit`, and `record_verdict` keep working.
  - `SwarmRunner` calls `ledger.tasks.close()` the moment it decides to stop (before the grace period).
  - `RunResult.unreviewed: list[str]` (default empty): ids of non-required, non-review tasks whose status is not `done`, sorted.
  - `RunResult.errors: dict[str, str]` (default empty): per peer, the last failure as `"<ExceptionClass>: <message>"` truncated to 200 characters.
  - PROTOCOL BOARD RULES gains the line: `- Create a new task only for work no existing task covers; never create a task that duplicates an existing task's deliverable.`

- [ ] **Step 1: Write the failing tests** in `tests/test_closing.py`:
  - `test_closed_ledger_refuses_reserve_and_submit`: after `close()`, `tasks.reserve(spec("x"))` and `tasks.submit_for_review(...)` raise `LedgerError` matching `closing`.
  - `test_closed_ledger_still_allows_verdict_and_commit`: with a review pending, `record_verdict` still approves and `artifacts.commit` on a claimed task still works.
  - `test_runner_closes_ledger_on_stop`: after a runner test run ends, `ledger.tasks.closed is True`.
  - `test_unreviewed_lists_optional_tasks`: a run that ends with an optional `sub:P01:1` in `in_review` has `result.unreviewed == ["sub:P01:1"]`.
  - `test_errors_record_last_failure`: a FakePeer raising `RuntimeError("boom")` yields `result.errors["P01"].startswith("RuntimeError: boom")`.
  - `test_protocol_forbids_duplicate_tasks`: `"never create a task that duplicates"` is in `PROTOCOL`; `test_protocol_differs_only_in_fields` still passes.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** The closed check goes inside the same transaction guards as the existing ones (read the flag before opening the write block).
- [ ] **Step 4: Run the full non-live suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat: close ledger on stop, report unreviewed work and peer errors, forbid duplicate tasks"`

---

### Task 3: Data-room generator core

**Files:**
- Create: `src/agora/dataroom/__init__.py`, `models.py`, `generate.py`, `tests/test_dataroom.py`

**Interfaces:**
- Produces in `models.py` (frozen dataclasses):
  - `PlantedFact(id: str, description: str, detectors: list[list[str]])` — detectors are OR-of-AND groups of lowercase substrings.
  - `GoldKey(variant: int, countries: list[str], blocker_country: str, anomaly_segment: str, undercutting_competitor: str, mismatch_delta_eur: float, mismatch_files: list[str], misleading_interview: str, country_order: list[str], planted: list[PlantedFact])` with `to_json() -> str` and `GoldKey.from_json(s: str) -> GoldKey`.
- Produces in `generate.py`: `generate_dataroom(variant: int, out_dir: str, gold_path: str) -> GoldKey`.
  - Raises `ValueError` if `gold_path` resolves inside `out_dir`.
  - Uses only `random.Random(variant)`; same variant gives byte-identical output.
  - Writes (this task): `crm_pipeline.csv` (columns `account_id,country,segment,arr_eur,stage,months_active,churned`; about 600 rows over the 5 countries and 3 segments; the anomaly segment's churn rate is at least 2.5 times each other segment's), `cost_structure.csv`, `competitor_prices.md` (4 competitors; exactly one, the undercutting competitor, priced at least 30% below the company's price and labeled only by its price sheet, never by the word "undercut"), `hiring_costs_by_country.csv`, `hiring_costs_summary.csv` (its stated total differs from the sum of the by-country rows by `mismatch_delta_eur`, an integer between 20,000 and 120,000), and `README.md` indexing every data-room file with one line each.
  - Fills `GoldKey` fields except `misleading_interview`, `country_order` and `planted` (Task 4 completes them; here they are `""`, `[]`, `[]`).

- [ ] **Step 1: Write the failing tests** in `tests/test_dataroom.py`:
  - `test_same_variant_is_byte_identical`: generate variant 3 twice into two tmp dirs; the `sha256` of every file matches; different variants differ.
  - `test_gold_inside_dataroom_refused`: `gold_path` under `out_dir` raises `ValueError`.
  - `test_countries_and_segments_fixed`: `GoldKey.countries == ["Germany","France","Netherlands","Spain","Poland"]`; CRM segments are exactly `{"SMB","Mid-market","Enterprise"}`.
  - `test_anomaly_segment_has_triple_churn`: computing churn rates from `crm_pipeline.csv`, the gold anomaly segment's rate is `>= 2.5 *` each other segment's, for variants 0..4.
  - `test_hiring_summary_mismatch_matches_gold`: `abs(summary_total - sum(by_country)) == gold.mismatch_delta_eur` for variants 0..4.
  - `test_undercutter_is_30_percent_below`: parse the price table in `competitor_prices.md`; only the gold competitor is `<= 0.7 *` our price.
  - `test_readme_indexes_existing_files`: every file named in `README.md` exists; the gold JSON roundtrips through `to_json/from_json`.
  - `test_no_gold_words_in_dataroom`: none of the strings `"undercut"`, `"planted"`, `"gold"` appears in any generated file.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `models.py` and the core of `generate.py`. The blocker country and anomaly segment rotate with the variant (`countries[(variant * 2) % 5]`, `segments[variant % 3]`); competitor names come from a fixed list indexed by the variant.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: deterministic data-room generator with planted CRM, cost and competitor facts"`

---

### Task 4: Interviews, regulatory memos, completed gold key

**Files:**
- Modify: `src/agora/dataroom/generate.py`; extend `tests/test_dataroom.py`

**Interfaces:**
- Consumes: Task 3 generator.
- Produces: additional data-room files `interviews/interview_01.md` .. `interview_20.md` (customer interviews about price sensitivity; 19 are consistent; exactly one, the misleading interview, contains a statement such as "we would pay 40% more" that contradicts that same customer's CRM record in `crm_pipeline.csv` — the account exists with a discount flag or a churned status) and `regulatory/<country>.md` for each country (one memo per country; the blocker country's memo states that a mandatory local data-processing licence cannot be obtained within 18 months, using exactly the words `licence` and `18 months`; the other memos describe obtainable licences with timelines under 9 months). `README.md` indexes the new files too.
  - `GoldKey.misleading_interview` is the file stem (for example `interview_07`).
  - `GoldKey.country_order` ranks the countries by `addressable_accounts / entry_cost_eur` (addressable accounts counted from the CRM with stage `lead` or `qualified`; entry cost from `cost_structure.csv`), with the blocker country forced last.
  - `GoldKey.planted` holds exactly 5 `PlantedFact`s with ids and detectors (lowercase; a group is satisfied when all its substrings appear in the lowercased dossier):
    - `reg_blocker`: `[[blocker, "licen"], [blocker, "block"]]`
    - `churn_anomaly`: `[[segment, "churn"]]` (segment lowercased, e.g. `"smb"`)
    - `undercut`: `[[competitor, "undercut"], [competitor, "cheaper"], [competitor, "lower price"], [competitor, "below"]]`
    - `arith_mismatch`: `[["hiring", "inconsisten"], ["hiring", "mismatch"], ["hiring", "discrepan"], ["hiring", "<delta as integer without separators>"], ["hiring", "<delta with thousands commas>"]]`
    - `misleading_quote`: `[[stem, "contradict"], [stem, "misleading"], [stem, "inconsisten"], [stem, "outlier"]]`

- [ ] **Step 1: Write the failing tests** in `tests/test_dataroom.py`:
  - `test_twenty_interviews_one_misleading`: 20 files exist; exactly one contains the contradiction phrase; it equals the gold stem; the account it names exists in the CRM.
  - `test_only_blocker_memo_has_blocker_phrase`: the blocker country's memo contains `licence` and `18 months`; no other memo does.
  - `test_gold_has_five_planted_facts_with_lowercase_detectors`: five ids as listed; every detector substring equals its own `.lower()`.
  - `test_country_order_blocker_last_and_complete`: `sorted(order) == sorted(countries)` and `order[-1] == blocker` for variants 0..4.
  - `test_no_planted_answer_in_dataroom_text`: the blocker memo does not contain the words `blocker` or `planted`; no file contains a gold detector phrase combined with `answer`.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the document generators with fixed sentence templates (no LLM), keeping determinism.
- [ ] **Step 4: Run all dataroom tests.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: interviews, regulatory memos and complete gold key for the data room"`

---

### Task 5: Domain checks and registry

**Files:**
- Create: `src/agora/domain.py`, `tests/test_domain.py`

**Interfaces:**
- Consumes: `Validator`, `Admission`, `Task`, `Artifact`.
- Produces:
  - `CITATION_RE` matching `[<path>.csv]`, `[<path>.md]` and the `:detail` form; `extract_citations(text: str) -> list[str]` returns the path parts in order.
  - `citations_resolve(data_dir: str, min_citations: int = 1) -> Validator`: for tasks of kind `work` or `integration`, the artifact must cite at least `min_citations` files and every cited path must exist under `data_dir`; absolute paths and `..` segments are errors. Error strings are prefixed `citations_resolve:` and name the bad citation.
  - `fact_citation_admission(data_dir: str) -> Admission`: for `FACT` notes the `detail` must contain a citation to an existing file; error `"FACT needs a data-room citation in detail"`; other note types pass.
  - `SUMMARY_KEYS = ("recommendation","country_order","blocker_country","anomaly_segment","undercutting_competitor","arith_mismatch_eur")`; `parse_dossier_summary(text: str) -> dict | None` finds the line `DOSSIER_SUMMARY` followed by a fenced json block and returns the parsed object only if all keys are present and `country_order` is a list of 5 strings; else `None`.
  - `dossier_summary_block() -> Validator`: only for the task with id `dossier`; error `"dossier_summary_block: missing or invalid DOSSIER_SUMMARY block"`; other tasks return `[]`.
  - `build_domain(name: str, data_dir: str) -> tuple[list[Validator], list[Admission]]` with registry names `"eu_market_entry"` (returns `[non_empty(), citations_resolve(data_dir), dossier_summary_block()]` and `[fact_citation_admission(data_dir)]`); unknown names raise `ConfigError`.

- [ ] **Step 1: Write the failing tests** in `tests/test_domain.py`: `test_extract_citations` (several forms, ignores non-file brackets such as `[x]`); `test_citations_resolve_accepts_existing_files` (tmp data dir with two files); `test_citations_reject_missing_traversal_and_absolute` (`[nope.csv]`, `[../x.csv]`, `[/etc/passwd.md]`); `test_min_citations_enforced`; `test_validator_skips_review_tasks`; `test_fact_admission_requires_detail_citation` and `test_fact_admission_ignores_other_types`; `test_parse_summary_valid`, `test_parse_summary_rejects_missing_key_wrong_order_length_and_bad_json`, `test_dossier_summary_block_only_for_dossier_task`; `test_build_domain_registry_and_unknown_name`.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Resolve paths with `os.path.normpath` against `data_dir` and verify the result stays inside it.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: domain checks - citation resolver, FACT admission, dossier summary block"`

---

### Task 6: EU example assets, `--domain` flag, data-room script

**Files:**
- Create: `examples/eu_market_entry/brief.md`, `template.yaml`, `roster.yaml`, `scripts/make_dataroom.py`, `tests/test_eu_assets.py`
- Modify: `src/agora/cli.py`, `.gitignore` (add `data/` and `eval_runs/`)

**Interfaces:**
- Produces:
  - `brief.md`: the company ("Lumen Analytics", mid-market B2B SaaS), the decision (enter the EU within 18 months? in which country order, at what price, with what 3-year P&L and risks), the data-room location `/data/`, the citation rule, and the exact `DOSSIER_SUMMARY` format from Global Constraints. It lists no answers.
  - `template.yaml`, 12 tasks with 3-4 concrete acceptance criteria each (every criterion names the file kinds to cite). Ids and deps exactly: `sizing`, `competitors`, `pricing`, `gtm`, `customer_evidence`, `regulatory`, `ops_cost` (no deps); `country_sequence` (sizing, regulatory, ops_cost); `pnl_3yr` (sizing, pricing, gtm, ops_cost); `risk_register` (regulatory, competitors, customer_evidence); `recommendation` (country_sequence, pnl_3yr, risk_register); `dossier` (kind integration; deps all eleven others).
  - `roster.yaml`: 10 peers `P01..P10`, models `deepseek` and `glm` only (same model definitions as `roster.glm-deepseek.yaml`), 5 of each; lenses as in `roster.glm-deepseek.yaml`; `budget: {swarm_usd: 3, peer_usd: 0.6, wall_clock_s: 1500}`; `data_dir: data/eu/v0`.
  - `scripts/make_dataroom.py --variant N --out DIR --gold PATH`: calls `generate_dataroom`, prints the file count (never the gold).
  - CLI flag `agora run --domain NAME`: builds validators and admission via `build_domain(NAME, roster.data_dir)`; without it behavior is unchanged (`[non_empty()]`, no admission). `--domain` with a roster lacking `data_dir` exits 1 with an error.

- [ ] **Step 1: Write the failing tests** in `tests/test_eu_assets.py`: `test_template_loads_with_expected_dag` (12 tasks, one integration `dossier` depending on the other 11, `country_sequence` deps exactly as listed); `test_roster_loads_two_families_ten_peers` (10 peers, families `{"deepseek","zhipu"}`, `data_dir == "data/eu/v0"`); `test_brief_has_summary_format_and_no_answers` (contains `DOSSIER_SUMMARY`; for variants 0..4 none of the gold's blocker country combined with `licence`, anomaly segment, or competitor name is stated as an answer — assert the brief contains none of the gold competitor names); `test_make_dataroom_script` (call `main(argv)` into tmp dirs; the gold file is outside the out dir and the printed output contains no gold value); `test_cli_domain_flag_requires_data_dir` and `test_cli_domain_flag_wires_validators` (monkeypatch `agora.cli.build_domain` and assert it received `roster.data_dir`).

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the files and the CLI flag.
- [ ] **Step 4: Run the full non-live suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat: EU market-entry example assets, --domain flag and data-room script"`

---

### Task 7: Deterministic scorer

**Files:**
- Create: `src/agora/eval/__init__.py`, `src/agora/eval/scoring.py`, `tests/test_scoring.py`

**Interfaces:**
- Consumes: `GoldKey`, `parse_dossier_summary`, `extract_citations`.
- Produces: `@dataclass(frozen=True) class Scores: recall: float; found: list[str]; missed: list[str]; summary_present: bool; summary_accuracy: float; citation_validity: float; citations: int` and `score_dossier(text: str, gold: GoldKey, data_dir: str) -> Scores`.
  - `recall`: planted facts with at least one detector group fully present (case-insensitive) divided by 5.
  - `summary_accuracy`: of five checks, the fraction correct: `blocker_country`, `anomaly_segment` and `undercutting_competitor` equal the gold (case-insensitive); `country_order` correct iff first and last elements equal the gold's first and last; `arith_mismatch_eur` within 1.0 of `mismatch_delta_eur`. It is 0.0 and `summary_present` False when the block is absent or invalid.
  - `citation_validity`: cited files that exist under `data_dir` divided by all cited files; 0.0 when none are cited; `citations` is the count.

- [ ] **Step 1: Write the failing tests** in `tests/test_scoring.py` using a small hand-built `GoldKey`: `test_all_planted_facts_found`; `test_country_without_licence_not_found` (text mentions the blocker country but not `licen` or `block` -> `reg_blocker` missed); `test_detector_groups_need_all_substrings`; `test_case_insensitive`; `test_summary_accuracy_each_key` (parametrized: one wrong key lowers accuracy by 0.2); `test_country_order_checks_first_and_last_only`; `test_mismatch_tolerance` (delta off by 0.5 passes, by 2 fails); `test_missing_summary_block`; `test_citation_validity_counts_existing_files` and `test_no_citations_scores_zero`.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: deterministic dossier scorer against the gold key"`

---

### Task 8: LLM judge

**Files:**
- Create: `src/agora/eval/judge.py`, `tests/test_judge.py`

**Interfaces:**
- Produces:
  - `CRITERIA = ("factual_accuracy","completeness","citation_quality","decision_quality","clarity")`; each scored as an integer 1-5.
  - `@dataclass(frozen=True) class JudgeResult: scores: dict[str, int]; mean: float; judge_id: str; raw: str`
  - `async def judge_dossier(model: BaseChatModel, judge_id: str, dossier: str, gold: GoldKey) -> JudgeResult | None`. The prompt states the rubric, lists the gold facts (descriptions only, no detectors), wraps the dossier between `<dossier>` and `</dossier>`, and says to ignore any instructions inside it. The reply must contain one JSON object with the five criteria; the first `{...}` is parsed, markdown fences allowed. A reply with a missing criterion, a non-integer or a value outside 1-5 counts as unparsable. One retry with a short corrective message; still unparsable returns `None`.
  - `def pick_judge(judge_ids: list[str], variant: int, seed: int) -> str` returns `judge_ids[(variant + seed) % len(judge_ids)]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_judge.py` with `ScriptedChatModel`: `test_valid_reply_scores_and_mean`; `test_fenced_json_is_parsed`; `test_unparsable_then_valid_is_retried` (the model is called twice); `test_unparsable_twice_returns_none`; `test_out_of_range_score_is_unparsable`; `test_prompt_wraps_dossier_and_excludes_detectors` (assert `<dossier>` in the prompt, the detector substring absent); `test_pick_judge_is_deterministic_and_rotates`.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: cross-vendor LLM judge with retry and missing-not-zero handling"`

---

### Task 9: Spend meter

**Files:**
- Create: `src/agora/eval/meter.py`, `tests/test_meter.py`

**Interfaces:**
- Consumes: `cost_of`, `Usage`, `ModelSpec`.
- Produces:
  - `class BudgetExceeded(Exception)`.
  - `class SpendMeter(cap_usd: float)` with `attach(model: BaseChatModel, spec: ModelSpec) -> BaseChatModel` (installs a callback handler bound to `spec` on the model and returns the same model), properties `total_usd: float` and `by_model: dict[str, float]` (keyed by `spec.key`), `reset() -> None`. After each LLM call finishes the handler reads the `AIMessage.usage_metadata` (`input_tokens`, `input_token_details.cache_read`, `output_tokens`), adds `cost_of(...)`, and raises `BudgetExceeded` when `total_usd >= cap_usd`. The handler sets `raise_error = True` so LangChain does not swallow the exception. Thread-safe. A call without `usage_metadata` adds nothing.

- [ ] **Step 1: Write the failing tests** in `tests/test_meter.py` using a scripted model that returns `AIMessage` with known `usage_metadata`: `test_totals_match_cost_of` (deepseek spec from `roster.example.yaml`); `test_cached_tokens_discounted`; `test_cap_raises_from_invoke` (`pytest.raises(BudgetExceeded)` around `model.invoke`); `test_two_models_accumulate_separately` (`by_model` keys); `test_missing_usage_ignored`; `test_reset_clears_totals`; `test_exception_not_swallowed_in_graph` (a minimal `create_react_agent`-style or `RunnableLambda` chain around the model still raises `BudgetExceeded`).

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Check `BaseCallbackHandler` and how a chat model accepts `callbacks` in langchain-core 1.7.0 before coding; use the real names.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: spend meter with hard cap across graphs and subagents"`

---

### Task 10: Single-agent baseline arm

**Files:**
- Create: `src/agora/eval/__init__.py` (exists), `src/agora/eval/config.py`, `src/agora/eval/arms/__init__.py`, `types.py`, `single.py`, `tests/test_arms_single.py`

**Interfaces:**
- Produces:
  - `config.py`: `@dataclass(frozen=True) ArmBudget(usd: float, wall_clock_s: float)`.
  - `types.py`: `@dataclass(frozen=True) ArmOutcome(arm: str, variant: int, seed: int, status: str, final_text: str, spend_usd: float, elapsed_s: float, notes: dict)` where `status` is one of `"finished" | "done" | "budget" | "timeout" | "stalled"`.
  - `single.py`: `SINGLE_PROMPT` (the brief plus: work alone, read `/data/`, plan with the todo tool, write the final dossier to `/dossier.md` with the DOSSIER_SUMMARY block); `CONTINUATION = "Re-check your dossier against the brief and the data room. Fix errors and missing items and rewrite /dossier.md. If it is final, reply with the single word FINAL."`; `async def run_single_arm(arm: str, spec: ModelSpec, model: BaseChatModel, brief: str, data_dir: str, budget: ArmBudget, meter: SpendMeter, variant: int, seed: int, clock=time.monotonic) -> ArmOutcome`.
  - Behavior: `create_deep_agent(model, system_prompt, backend=composite with read-only /data/, middleware=[TodoListMiddleware()], checkpointer=InMemorySaver())`; the model gets `meter.attach` before use. The first turn asks for the dossier; after each episode, if the reply is exactly `FINAL` and `/dossier.md` exists, stop with `"finished"`; otherwise, while episodes < 8 and spend < 90% of `budget.usd` and time remains, send `CONTINUATION`. Each episode runs under `asyncio.wait_for` with the remaining wall-clock. `BudgetExceeded` ends the arm with status `"budget"`; wall-clock expiry ends it with `"timeout"`. `final_text` is the content of `/dossier.md` read from the checkpointed state (`graph.get_state(config)`) or the last AI message when the file is absent. `spend_usd` is `meter.total_usd` at the end.
  - `arms/__init__.py`: `ARM_IDS = ("c0-deepseek","c0-glm","c1-10","c2-5","c2-3","c3-supervisor","a1-same-family")`.

- [ ] **Step 1: Inspect the real API.** Print how `create_deep_agent` exposes the virtual files after a run (`result["files"]` or state), and the shape of a file entry in deepagents 0.7.32; use the real shape.
- [ ] **Step 2: Write the failing tests** in `tests/test_arms_single.py` with `ScriptedChatModel`: `test_finished_when_final_reply_and_file_written` (script: a `write_file` tool call to `/dossier.md`, an AI message, then `FINAL`; outcome `status == "finished"`, `final_text` equals the written content); `test_continuation_sent_until_final` (two continuations counted via `model.seen`); `test_budget_exceeded_returns_partial_text` (the scripted `usage_metadata` pushes the meter over the cap after the file is written; status `"budget"`, `final_text` is the file content, no exception escapes); `test_wall_clock_timeout` (fake clock; status `"timeout"`); `test_data_dir_is_read_only`; `test_episode_cap` (never `FINAL`: exactly 8 episodes).
- [ ] **Step 3: Run them.** Expected: FAIL.
- [ ] **Step 4: Implement** `run_single_arm` and the shared helper `drive_agent(agent, config, first_message, continuation, budget, meter, clock) -> tuple[str, str]` (status, last_reply) in `single.py`, importable by the supervisor arm.
- [ ] **Step 5: Run them.** Expected: PASS.
- [ ] **Step 6: Commit.** `git commit -m "feat: single-agent baseline arm with equal budget and wall clock"`

---

### Task 11: Supervisor arm

**Files:**
- Create: `src/agora/eval/arms/supervisor.py`, `tests/test_arms_supervisor.py`

**Interfaces:**
- Consumes: `drive_agent`, `SpendMeter`, `ArmOutcome`, deepagents subagents.
- Produces: `SUBAGENT_DEFS` (four specialists: `market-analyst`, `financial-modeler`, `regulatory-analyst`, `customer-researcher`, each with a one-sentence description, a system prompt that says to read `/data/`, cite files as `[file]` and return findings to the supervisor, and a model key alternating `glm` / `deepseek`); `SUPERVISOR_PROMPT` (plan, delegate with the `task` tool, integrate, write `/dossier.md` with the DOSSIER_SUMMARY block); `async def run_supervisor_arm(arm: str, supervisor_spec: ModelSpec, supervisor_model: BaseChatModel, subagent_models: dict[str, tuple[ModelSpec, BaseChatModel]], brief: str, data_dir: str, budget: ArmBudget, meter: SpendMeter, variant: int, seed: int, clock=time.monotonic) -> ArmOutcome`. The supervisor is DeepSeek. Every subagent model is attached to the same `meter`.

- [ ] **Step 1: Inspect the real API.** Print the subagent spec shape accepted by `create_deep_agent(subagents=[...])` in 0.7.32 (field names, how a per-subagent `model` is passed, whether subagents inherit the backend). Use the real shape.
- [ ] **Step 2: Write the failing tests** in `tests/test_arms_supervisor.py`: `test_supervisor_delegates_and_writes_dossier` (a scripted supervisor emits a `task` call to `market-analyst`, whose scripted model returns text; then writes `/dossier.md` and replies `FINAL`; outcome status `"finished"`, `final_text` equals the file); `test_spend_counted_across_supervisor_and_subagent` (`meter.by_model` has both model keys); `test_budget_cap_stops_run_with_partial_text`; `test_subagent_data_access_is_read_only`.
- [ ] **Step 3: Run them.** Expected: FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run them.** Expected: PASS.
- [ ] **Step 6: Commit.** `git commit -m "feat: supervisor-led arm using deepagents subagents under the same budget"`

---

### Task 12: Swarm arm adapter

**Files:**
- Create: `src/agora/eval/arms/swarm.py`, `tests/test_arms_swarm.py`

**Interfaces:**
- Consumes: `arun_swarm`, `build_domain`, `load_template`, `RosterConfig`.
- Produces:
  - `LENSES` (12 strings; the first 10 are the lenses in `examples/eu_market_entry/roster.yaml`).
  - `build_swarm_roster(n_peers: int, models: dict[str, ModelSpec], budget: BudgetSpec, data_dir: str, reviewer_family_must_differ: bool = True, run_name: str = "eval") -> RosterConfig`: `n_peers` in 3..10; peers alternate `deepseek`, `glm`, starting with `deepseek`, lenses taken in order; `models` must contain exactly the keys `deepseek` and `glm`.
  - `async def run_swarm_arm(arm: str, n_peers: int, same_family_review: bool, models: dict[str, tuple[ModelSpec, BaseChatModel]], brief: str, template_path: str, data_dir: str, budget: ArmBudget, db_path: str, variant: int, seed: int) -> ArmOutcome`: builds the roster (swarm_usd = `budget.usd`, wall_clock_s = `budget.wall_clock_s`, peer_usd = `budget.usd / 4` rounded to 2 decimals), runs `arun_swarm` with `build_domain("eu_market_entry", data_dir)` checks, and returns the outcome. `final_text` is the latest artifact of task `dossier` if present, else the latest artifacts of the done tasks joined by `\n\n---\n\n`. `spend_usd` is `ledger.budget.spent()`. `status` is the `RunResult` status. `notes` holds `unreviewed`, `retired`, `exhausted`, `errors`, `episodes`, `db_path`.

- [ ] **Step 1: Write the failing tests** in `tests/test_arms_swarm.py`: `test_roster_sizes_and_families` (n=3,5,10 build valid `RosterConfig`s with both families, correct counts, `data_dir` set); `test_same_family_flag_sets_policy`; `test_peer_budget_is_quarter_of_swarm`; `test_rejects_bad_model_keys_and_peer_counts`; `test_swarm_arm_offline_times_out_with_empty_text` (ScriptedChatModels that do nothing, tiny `wall_clock_s`; `status == "timeout"`, `final_text == ""`, `spend_usd == 0.0`, `notes["db_path"]` exists); `test_final_text_prefers_dossier_artifact` (seed a done `dossier` task through ledger helpers and assert its artifact is used).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: swarm arm adapter with configurable team size and review ablation"`

---

### Task 13: Evaluation runner, report, CLI

**Files:**
- Create: `src/agora/eval/runner.py`, `report.py`, `cli.py`, `src/agora/eval/config.py` (extend), `examples/eu_market_entry/eval.yaml`, `tests/test_eval_runner.py`, `tests/test_eval_report.py`, `tests/test_eval_cli.py`
- Modify: `pyproject.toml` (`agora-eval = "agora.eval.cli:main"`)

**Interfaces:**
- Produces:
  - `EvalConfig` (pydantic, `extra="forbid"`): `data_root: str`, `gold_root: str`, `out_dir: str`, `brief_path: str`, `template_path: str`, `budget_usd: float`, `wall_clock_s: float`, `team_models: dict[str, ModelSpec]` (keys `deepseek`, `glm`), `judges: dict[str, ModelSpec]` (non-empty; keys must not equal a team model key), `arms: list[str]` (subset of `ARM_IDS`), `variants: list[int]`, `seeds: int`; `load_eval_config(path) -> EvalConfig`.
  - `@dataclass(frozen=True) ResultRow`: `arm, variant, seed, status, spend_usd, elapsed_s, recall, summary_accuracy, citation_validity, judge_mean (float | None), judge_id (str | None), final_text_path, notes` with `to_json()/from_json()`.
  - `async def run_eval(cfg: EvalConfig, *, max_total_usd: float, models_override: dict | None = None, judges_override: dict | None = None, run_arm_fn=None) -> list[ResultRow]`: sequential over variants x seeds x arms; for each run it generates the data room (cached) and writes the final text to `out_dir/texts/<arm>_v<variant>_s<seed>.md`, scores it, judges it (judge chosen with `pick_judge`), appends the row to `out_dir/results.jsonl`. **Resume:** rows already present for `(arm, variant, seed)` are skipped. **Spend cap:** before each run, stop if `spent_so_far + cfg.budget_usd > max_total_usd`; the function returns what it has and the CLI exits 5.
  - `report.py`: `ArmSummary(arm, n, recall_mean, summary_accuracy_mean, judge_mean, spend_mean, elapsed_mean, done_rate)`; `aggregate(rows) -> list[ArmSummary]` (judge mean ignores `None`); `decide(rows) -> Decision` with a pre-registered rule: with at least 3 rows for each of `c1-10` and the best of `c0-deepseek`/`c0-glm` (by recall), the swarm **wins** if `recall` is at least 0.10 higher and `judge_mean` at least 0.5 higher; **loses** if either is lower by the same margins; otherwise **inconclusive**; fewer than 3 rows gives **inconclusive**; the cost ratio is reported either way; `render_markdown(summaries, decision) -> str`.
  - `cli.py`: `agora-eval --config PATH [--max-total-usd X] [--dry-run] [--arms A,B] [--variants 0,1] [--seeds N]`. `--dry-run` prints the run matrix, the run count and the worst-case cost (`runs * budget_usd`) and exits 0 without any model call or API key. Without `--dry-run`, `--max-total-usd` is required (exit 1 with `error:` otherwise). Exit codes: 0 finished, 1 usage/config error, 5 stopped early by the spend cap. After a run it writes `out_dir/report.md`.

- [ ] **Step 1: Write the failing tests:**
  - `tests/test_eval_runner.py`: `test_run_eval_writes_rows_and_texts` (a fake `run_arm_fn` returns canned `ArmOutcome`s; judge models are `ScriptedChatModel`s; rows contain scores computed against the generated gold); `test_resume_skips_existing_rows`; `test_spend_cap_stops_before_unaffordable_run` (`max_total_usd` less than two runs' budget yields exactly one row); `test_judge_failure_recorded_as_none_not_zero`; `test_gold_never_reaches_arms` (the `brief` and `data_dir` passed to the fake `run_arm_fn` contain no gold string and the gold path is outside `data_dir`).
  - `tests/test_eval_report.py`: `test_aggregate_math`, `test_judge_none_ignored`, `test_decide_swarm_wins_loses_inconclusive_and_too_few_rows` (crafted rows), `test_render_markdown_contains_every_arm_and_decision`.
  - `tests/test_eval_cli.py`: `test_dry_run_prints_matrix_and_worst_case_without_keys` (clear all API-key env vars; assert `"7 arms"`-style counts and the dollar figure); `test_live_run_requires_max_total_usd`; `test_cli_exit_5_on_cap` (fake runner); `test_eval_yaml_loads` for `examples/eu_market_entry/eval.yaml` (7 arms, judges `haiku` and `luna`, team models only `deepseek` and `glm`, `budget_usd == 3`, `wall_clock_s == 1500`, `variants == [0]`, `seeds == 1`).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** `eval.yaml` points `data_root` at `data/eu`, `gold_root` at `data/eu_gold`, `out_dir` at `eval_runs/pilot`; judge price specs: haiku `0.10/0.01/0.50` (tier above 100000: `0.50/0.05/2.50`), luna `0.10/0.01/0.50` (tier above 272000: `0.20/0.02/0.75`).
- [ ] **Step 4: Run the full non-live suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat: evaluation runner with resume and spend cap, aggregation, pre-registered decision rule, agora-eval CLI"`

---

### Task 14: Pilot evaluation (live, needs the user's spend approval)

**Files:**
- Create: `docs/phase5-eu-pilot.md`
- Modify: `README.md` (evaluation section and known limitations)

**Interfaces:**
- Consumes: everything above. Keys come from `.env` via `set -a; . ./.env; set +a` or `uv run --env-file .env`.

- [ ] **Step 1: Offline checks.** Run `agora-eval --config examples/eu_market_entry/eval.yaml --dry-run`. Expected: 7 runs, worst case `$21.00`. Generate the variant-0 data room with the script and confirm `data/eu/v0` and the gold file exist and the gold is outside the data room.
- [ ] **Step 2: Ask the user to confirm the spend.** Pilot: 1 variant x 7 arms x 1 seed, hard cap `--max-total-usd 25`, estimated real cost $5-15 (the toy runs cost under $0.10 each; the dossier is larger). Do not run live steps until the user confirms in this conversation.
- [ ] **Step 3: Run the pilot.** `agora-eval --config examples/eu_market_entry/eval.yaml --max-total-usd 25` in the foreground with a long tool timeout (the run takes up to about 30 minutes); never print keys.
- [ ] **Step 4: Record the results** in `docs/phase5-eu-pilot.md`: the command (no secrets), total spend, one table per arm (status, spend, elapsed, recall, summary_accuracy, citation_validity, judge mean and judge id), the decision-rule output with the caveat that n=1 is inconclusive by design, per-arm failure notes (retirements, exhausted peers, errors, unreviewed tasks), and honest observations including anything that looks like a framework or scoring bug. Do not change framework behavior in this task; report issues instead.
- [ ] **Step 5: Update `README.md`** with a short evaluation section (how to dry-run, how to run with a cap, where results go) and the known limitations from the pilot.
- [ ] **Step 6: Commit** the docs. `git commit -m "docs: EU market-entry pilot results and evaluation usage"`
- [ ] **Step 7: Stop and report.** The full study (about 5 variants x 3 seeds, an estimated $60-150) needs the user's explicit go-ahead on spend and is not part of this plan.

---

## Out of scope (Plan 3 candidates)

Public benchmark slices (Finance Agent Benchmark, DABstep negative control), MAST failure tagging, a human-graded sample, a Postgres ledger, an injected-false-fact (error amplification) experiment, and the Plan 1 deferred minors not listed above.
