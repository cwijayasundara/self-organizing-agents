"""Command line entry point: `agora run`."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agora.domain import build_domain
from agora.config import ConfigError, load_roster
from agora.api import run_swarm
from agora.ledger.types import LedgerError
from agora.templates import load_template, seed_tasks
from agora.validators import non_empty

EXIT_CODES = {"done": 0, "budget": 2, "timeout": 3, "stalled": 4}


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # argparse would sys.exit(2), which is the budget exit code
        raise _UsageError(message)


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="agora")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a swarm on a task template")
    run.add_argument("--roster", required=True)
    run.add_argument("--template", required=True)
    run.add_argument("--brief", required=True)
    run.add_argument("--db", default=None, help="ledger path (default runs/<run-id>.sqlite)")
    run.add_argument("--run-id", default=None, help="default: UTC timestamp")
    run.add_argument("--domain", default=None, help="domain validators/admission (needs roster data_dir)")
    return p


def _run(args: argparse.Namespace) -> int:
    roster = load_roster(args.roster)
    if args.domain and roster.data_dir is None:
        raise ConfigError("--domain needs a roster with data_dir")
    specs = load_template(args.template)
    brief = Path(args.brief).read_text()

    run_id = args.run_id or _default_run_id()
    db_path = args.db or f"runs/{run_id}.sqlite"
    if Path(db_path).exists():
        raise ConfigError(f"ledger {db_path} already exists (choose another --run-id or --db)")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    validators, admission = [non_empty()], []
    if args.domain:
        validators, admission = build_domain(args.domain, roster.data_dir)
    outcome = run_swarm(roster, specs, brief, db_path, validators=validators, admission=admission)
    result, ledger = outcome.result, outcome.ledger
    tasks = []
    for t in ledger.tasks.list():
        art = ledger.artifacts.latest(t.id)
        tasks.append({"id": t.id, "kind": t.kind, "required": t.required,
                      "status": t.status, "artifact_id": art.id if art else None})
    print(json.dumps({"run_id": run_id, "db": db_path, **asdict(result), "tasks": tasks},
                     indent=2, sort_keys=True))
    return EXIT_CODES[result.status]


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except _UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except SystemExit as e:  # --help exits 0
        return e.code if isinstance(e.code, int) else 0
    try:
        return _run(args)
    except (ConfigError, LedgerError, yaml.YAMLError, OSError) as e:
        print(f"error: {' '.join(str(e).split())}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
