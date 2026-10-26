"""Command line entry point: `agora run`."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from agora.config import ConfigError, load_roster
from agora.ledger import open_ledger
from agora.models import build_model
from agora.peer import make_peer
from agora.runner import SwarmRunner
from agora.templates import load_template, seed_tasks

EXIT_CODES = {"done": 0, "budget": 2, "timeout": 3, "stalled": 4}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agora")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a swarm on a task template")
    run.add_argument("--roster", required=True)
    run.add_argument("--template", required=True)
    run.add_argument("--brief", required=True)
    run.add_argument("--db", default=None, help="ledger path (default runs/<run-id>.sqlite)")
    run.add_argument("--run-id", default=None, help="default: UTC timestamp")
    return p


def _run(args: argparse.Namespace) -> int:
    roster = load_roster(args.roster)
    specs = load_template(args.template)
    brief = Path(args.brief).read_text()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    db_path = args.db or f"runs/{run_id}.sqlite"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    models = {}
    for key in dict.fromkeys(p.model for p in roster.peers):  # only models that peers use
        models[key] = build_model(roster.models[key])

    ledger = open_ledger(
        db_path,
        lease_s=roster.budget.lease_s,
        prices=roster.models,
        reviewer_family_must_differ=roster.review_policy.reviewer_family_must_differ,
    )
    seed_tasks(ledger, specs)
    checkpointer = InMemorySaver()
    peers = {
        p.id: make_peer(
            p, roster.models[p.model], models[p.model], ledger, roster.budget,
            len(roster.peers), brief, checkpointer, data_dir=roster.data_dir,
        )
        for p in roster.peers
    }
    result = asyncio.run(SwarmRunner(roster, ledger, peers).run())

    print(json.dumps({"run_id": run_id, "db": db_path, **asdict(result)}, indent=2, sort_keys=True))
    print()
    for t in ledger.tasks.list():
        if t.required:
            art = ledger.artifacts.latest(t.id)
            print(f"{t.id}\t{t.status}\t{art.id if art else '-'}")
    return EXIT_CODES[result.status]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except (ConfigError, yaml.YAMLError, OSError) as e:
        print(f"error: {' '.join(str(e).split())}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
