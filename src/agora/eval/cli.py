"""`agora-eval`: run the evaluation matrix under a hard total spend cap."""
from __future__ import annotations

import argparse
import asyncio
import math
import sys
from pathlib import Path

import yaml

from agora.config import ConfigError
from agora.eval.arms import ARM_IDS
from agora.eval.config import load_eval_config
from agora.eval.report import aggregate, decide, render_markdown
from agora.eval.runner import load_rows, run_eval


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="agora-eval")
    p.add_argument("--config", required=True)
    p.add_argument("--max-total-usd", type=float, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--arms", default=None, help="comma-separated arm ids")
    p.add_argument("--variants", default=None, help="comma-separated variant numbers")
    p.add_argument("--seeds", type=int, default=None)
    return p


def _ints(s: str, what: str) -> list[int]:
    try:
        return [int(x) for x in s.split(",") if x.strip()]
    except ValueError:
        raise _UsageError(f"{what} must be comma-separated integers, got {s!r}")


def _run(args) -> int:
    cfg = load_eval_config(args.config)
    updates = {}
    if args.arms is not None:
        arms = [a.strip() for a in args.arms.split(",") if a.strip()]
        bad = [a for a in arms if a not in ARM_IDS]
        if bad or not arms or len(set(arms)) != len(arms):
            raise _UsageError(f"invalid --arms {args.arms!r}; expected distinct ids from {list(ARM_IDS)}")
        updates["arms"] = arms
    if args.variants is not None:
        v = _ints(args.variants, "--variants")
        if not v:
            raise _UsageError("--variants must not be empty")
        updates["variants"] = v
    if args.seeds is not None:
        if args.seeds < 1:
            raise _UsageError("--seeds must be >= 1")
        updates["seeds"] = args.seeds
    if updates:
        cfg = cfg.model_copy(update=updates)
    matrix = [(a, v, s) for v in cfg.variants for s in range(cfg.seeds) for a in cfg.arms]

    if args.dry_run:
        for a, v, s in matrix:
            print(f"run: arm={a} variant={v} seed={s}")
        print(f"{len(matrix)} runs; worst-case cost ${len(matrix) * cfg.budget_usd:.2f} "
              f"(runs x ${cfg.budget_usd:.2f} budget); judge calls add a small extra")
        return 0
    if args.max_total_usd is None:
        raise _UsageError("--max-total-usd is required for a live run (use --dry-run to preview cost)")
    if not math.isfinite(args.max_total_usd):
        raise _UsageError("--max-total-usd must be a finite number")
    if args.max_total_usd < cfg.budget_usd:
        raise _UsageError(f"--max-total-usd ${args.max_total_usd:.2f} is smaller than one run's "
                          f"budget ${cfg.budget_usd:.2f}")
    out = Path(cfg.out_dir)
    interrupted = False
    result = None
    try:
        result = asyncio.run(run_eval(cfg, max_total_usd=args.max_total_usd))
    except KeyboardInterrupt:
        interrupted = True
    rows = load_rows(out / "results.jsonl")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(aggregate(rows), decide(rows)))
    if interrupted:
        print(f"interrupted; {len(rows)} runs recorded; report: {out / 'report.md'}", file=sys.stderr)
        return 130
    print(f"{len(result.rows)} runs recorded; total spend ${result.spent_total_usd:.4f}; "
          f"stopped by cap: {result.stopped_by_cap}; report: {out / 'report.md'}")
    return 5 if result.stopped_by_cap else 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except _UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    try:
        return _run(args)
    except _UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (ConfigError, yaml.YAMLError, OSError) as e:
        print(f"error: {' '.join(str(e).split())}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
