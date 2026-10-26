"""Evaluation runner: sequential matrix with resume, a hard total spend cap and per-run isolation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

from agora.config import ModelSpec
from agora.dataroom.generate import generate_dataroom
from agora.dataroom.models import GoldKey
from agora.eval.arms import run_arm
from agora.eval.config import EvalConfig
from agora.eval.judge import judge_dossier_with_reason, pick_judge
from agora.eval.meter import SpendMeter, detach_all
from agora.eval.scoring import score_dossier
from agora.models import build_model

log = logging.getLogger(__name__)

JUDGE_TIMEOUT_S = 180
RUN_TIMEOUT_MULT = 1.2
RUN_TIMEOUT_SLACK_S = 120


@dataclass(frozen=True)
class ResultRow:
    arm: str
    variant: int
    seed: int
    status: str
    spend_usd: float
    elapsed_s: float
    recall: float
    summary_accuracy: float
    summary_present: bool
    citation_validity: float
    citations: int
    found: list
    missed: list
    judge_mean: float | None
    judge_id: str | None
    judge_usd: float
    final_text_path: str
    notes: dict = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        d["notes"] = json.loads(json.dumps(d["notes"], default=str))
        return json.dumps(d, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "ResultRow":
        return cls(**json.loads(s))

    @property
    def key(self) -> tuple[str, int, int]:
        return (self.arm, self.variant, self.seed)


@dataclass(frozen=True)
class RunEvalResult:
    rows: list[ResultRow]
    stopped_by_cap: bool
    spent_total_usd: float


def default_models_factory(cfg: EvalConfig) -> dict[str, tuple[ModelSpec, BaseChatModel]]:
    return {k: (spec, build_model(spec)) for k, spec in cfg.team_models.items()}


def load_rows(path: str | Path) -> list[ResultRow]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(ResultRow.from_json(line))
        except (ValueError, TypeError) as e:  # a truncated line from an interrupted run
            log.warning("skipping unreadable results line: %s", e)
    return rows


def _append(path: Path, row: ResultRow) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.exists() and path.stat().st_size > 0:
        with open(path, "rb") as f:
            f.seek(-1, 2)
            if f.read(1) != b"\n":
                prefix = "\n"
    with open(path, "a") as f:
        f.write(prefix + row.to_json() + "\n")
        f.flush()


def _spend(row: ResultRow) -> float:
    return row.spend_usd + row.judge_usd


async def _judge(cfg, judge_id, judge_model, dossier, gold, timeout_s, meter=None):
    """-> (judge_mean | None, judge_usd, note | None). Never raises."""
    spec = cfg.judges[judge_id]
    meter = meter or SpendMeter(cap_usd=float("inf"))
    model = judge_model if judge_model is not None else None
    try:
        if model is None:
            model = build_model(spec)
        meter.attach(model, spec)
        res, why = await asyncio.wait_for(judge_dossier_with_reason(model, judge_id, dossier, gold),
                                          timeout=timeout_s)
        if res is None:
            return None, meter.total_usd, why or "no usable score"
        return res.mean, meter.total_usd, None
    except asyncio.TimeoutError:
        return None, meter.total_usd, "timeout"
    except Exception as e:
        return None, meter.total_usd, f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        if model is not None:
            detach_all(model)


def _is_ok(r: ResultRow) -> bool:
    return r.status != "error"


def _quarantine_ledger(db_path: Path) -> str | None:
    """Move a stale ledger (and WAL/SHM sidecars) aside; return the new name."""
    if not db_path.exists():
        return None
    n = 1
    while True:
        target = db_path.with_name(f"{db_path.stem}.crashed-{n}{db_path.suffix}")
        if not target.exists():
            break
        n += 1
    os.rename(db_path, target)
    for suffix in ("-wal", "-shm"):
        side = db_path.with_name(db_path.name + suffix)
        if side.exists():
            os.rename(side, target.with_name(target.name + suffix))
    return target.name


def _preflight(cfg, factory, judges_override, pending) -> None:
    """Build (no network) the models a run would need so a missing key fails before any spend."""
    if not pending:
        return
    models = factory(cfg)
    for _, m in models.values():
        detach_all(m)
    for jid in sorted({pick_judge(sorted(cfg.judges), v, sd) for _, v, sd in pending}):
        if jid not in (judges_override or {}):
            build_model(cfg.judges[jid])


async def run_eval(cfg: EvalConfig, *, max_total_usd: float, models_factory=None, judges_override=None,
                   run_arm_fn=None, clock=time.monotonic, judge_timeout_s: float = JUDGE_TIMEOUT_S,
                   run_timeout_s: float | None = None) -> RunEvalResult:
    out = Path(cfg.out_dir)
    results_path = out / "results.jsonl"
    rows = load_rows(results_path)
    done = {r.key for r in rows if _is_ok(r)}  # error rows are retried
    spent = sum(_spend(r) for r in rows)  # but all spend counts
    for r in rows:
        old = r.notes.get("budget_usd")
        if old is not None and old != cfg.budget_usd:
            print(f"warning: resumed row {r.key} was written under budget_usd={old}, "
                  f"now {cfg.budget_usd}", file=sys.stderr)
            break
    factory = models_factory or default_models_factory
    arm_fn = run_arm_fn or run_arm
    timeout = run_timeout_s if run_timeout_s is not None else (
        cfg.wall_clock_s * RUN_TIMEOUT_MULT + RUN_TIMEOUT_SLACK_S)
    brief = Path(cfg.brief_path).read_text()
    matrix = [(a, v, sd) for v in cfg.variants for sd in range(cfg.seeds) for a in cfg.arms]
    _preflight(cfg, factory, judges_override, [k for k in matrix if k not in done])

    for arm, variant, seed in matrix:
        if (arm, variant, seed) in done:
            continue
        if spent + cfg.budget_usd > max_total_usd:
            return RunEvalResult(rows, True, spent)
        data_dir = Path(cfg.data_root) / f"v{variant}"
        gold_path = Path(cfg.gold_root) / f"v{variant}.json"
        if not data_dir.is_dir() or not gold_path.is_file():
            generate_dataroom(variant, str(data_dir), str(gold_path))
        gold = GoldKey.from_json(gold_path.read_text())
        db_path = out / "ledgers" / f"{arm}_v{variant}_s{seed}.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        stale = _quarantine_ledger(db_path)
        row = await _one_run(cfg, arm, variant, seed, brief, str(data_dir), str(db_path), gold,
                             factory, arm_fn, judges_override, clock, judge_timeout_s, out, timeout, stale)
        _append(results_path, row)
        rows.append(row)
        if _is_ok(row):
            done.add(row.key)
        spent += _spend(row)
    return RunEvalResult(rows, False, spent)


async def _one_run(cfg, arm, variant, seed, brief, data_dir, db_path, gold, factory, arm_fn,
                   judges_override, clock, judge_timeout_s, out, timeout, stale) -> ResultRow:
    meter = SpendMeter(cap_usd=cfg.budget_usd)
    acct = SpendMeter(cap_usd=float("inf"))  # independent accounting, sees swarm spend too
    base_notes = {"budget_usd": cfg.budget_usd, "wall_clock_s": cfg.wall_clock_s}
    if stale:
        base_notes["stale_ledger"] = stale
    models = factory(cfg)  # a ConfigError (missing key) is fatal for the whole evaluation
    t0 = clock()
    st = {"outcome": None, "text_path": "", "jmeter": SpendMeter(cap_usd=float("inf"))}
    try:
        for spec, m in models.values():
            acct.attach(m, spec)
        try:
            outcome = await asyncio.wait_for(
                arm_fn(arm, cfg, models, brief, data_dir, db_path, variant, seed, meter), timeout=timeout)
        except asyncio.TimeoutError:
            err = f"TimeoutError: run exceeded hard timeout of {timeout:.0f}s"
            spend = max(acct.total_usd, meter.total_usd)
            return ResultRow(arm, variant, seed, "error", spend, clock() - t0, 0.0, 0.0, False, 0.0, 0,
                             [], [], None, None, 0.0, "",
                             {**base_notes, "error": err, "acct_usd": acct.total_usd})
        except Exception as e:
            spend = max(acct.total_usd, meter.total_usd)
            return ResultRow(arm, variant, seed, "error", spend, clock() - t0, 0.0, 0.0, False, 0.0, 0,
                             [], [], None, None, 0.0, "",
                             {**base_notes, "error": f"{type(e).__name__}: {str(e)[:300]}",
                              "acct_usd": acct.total_usd})
        st["outcome"] = outcome
        spend = max(acct.total_usd, outcome.spend_usd)
        notes = {**dict(outcome.notes or {}), **base_notes, "acct_usd": acct.total_usd}
        if spend > cfg.budget_usd * 1.5:
            notes["overspend"] = True
            log.warning("%s v%s s%s overspent: $%.4f vs budget $%.2f", arm, variant, seed, spend,
                        cfg.budget_usd)
        text_path = out / "texts" / f"{arm}_v{variant}_s{seed}.md"
        try:
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(outcome.final_text)
            st["text_path"] = str(text_path)
            scores = score_dossier(outcome.final_text, gold, data_dir)
        except Exception as e:
            notes["scoring_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            return ResultRow(arm, variant, seed, outcome.status, spend, outcome.elapsed_s, 0.0, 0.0,
                             False, 0.0, 0, [], [], None, None, 0.0, "", notes)
        judge_mean, judge_id, judge_usd = None, None, 0.0
        if not outcome.final_text.strip():
            notes["judge"] = "empty dossier"
            notes["judge_error"] = "empty dossier"
        else:
            judge_id = pick_judge(sorted(cfg.judges), variant, seed)
            jm = (judges_override or {}).get(judge_id)
            judge_mean, judge_usd, note = await _judge(cfg, judge_id, jm, outcome.final_text, gold,
                                                       judge_timeout_s, st["jmeter"])
            if note:
                notes["judge"] = note
                notes["judge_error"] = note
        return ResultRow(arm, variant, seed, outcome.status, spend, outcome.elapsed_s,
                         scores.recall, scores.summary_accuracy, scores.summary_present,
                         scores.citation_validity, scores.citations, list(scores.found),
                         list(scores.missed), judge_mean, judge_id, judge_usd, str(text_path), notes)
    except (asyncio.CancelledError, KeyboardInterrupt):
        oc = st["outcome"]
        spend = max(acct.total_usd, meter.total_usd, oc.spend_usd if oc else 0.0)
        notes = {**base_notes, "error": "interrupted", "acct_usd": acct.total_usd,
                 "interrupted_phase": "post-arm" if oc else "arm"}
        if oc:
            notes["partial"] = True
        try:
            _append(out / "results.jsonl", ResultRow(
                arm, variant, seed, "error", spend, clock() - t0, 0.0, 0.0, False, 0.0, 0, [], [],
                None, None, st["jmeter"].total_usd, st["text_path"], notes))
        except Exception as e:  # the original interrupt must always propagate
            print(f"warning: could not record interrupted run: {e}", file=sys.stderr)
        raise
    finally:
        for _, m in models.values():
            detach_all(m)
