"""Command line entry point: `agora run`."""
from __future__ import annotations

import argparse
import json
import sys
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agora.domain import build_domain
from agora.config import ConfigError, load_roster
from agora.api import run_swarm
from agora.ledger.types import LedgerError
from agora.observe import ConsoleTail, LiveServer, setup_logging
from agora.templates import load_template
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
    _view_args(run)
    run.add_argument("--watch", action="store_true",
                     help="serve a live HTML view of the run and open it in the browser")
    run.add_argument("-v", "--verbose", action="store_true", help="also log every tool call")
    run.add_argument("-q", "--quiet", action="store_true", help="no progress log, only warnings")
    watch = sub.add_parser("watch", help="live HTML view of a ledger (a running or a finished run)")
    watch.add_argument("db", help="ledger path, e.g. runs/<run-id>.sqlite")
    _view_args(watch)
    return p


def _view_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=8765, help="live view port (default 8765; any free port if taken)")
    p.add_argument("--no-browser", action="store_true", help="do not open the live view in a browser")


def _wait_for_ctrl_c(message: str) -> None:
    print(message, file=sys.stderr)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def _watch(args: argparse.Namespace) -> int:
    if not Path(args.db).exists():
        raise ConfigError(f"ledger {args.db} does not exist")
    server = LiveServer(args.db, args.port).start(open_browser=not args.no_browser)
    _wait_for_ctrl_c(f"serving {args.db} at {server.url} (Ctrl-C to stop)")
    server.stop()
    return 0


def _run(args: argparse.Namespace) -> int:
    roster = load_roster(args.roster)
    if args.domain and roster.data_dir is None:
        raise ConfigError("--domain needs a roster with data_dir")
    if args.domain and not Path(roster.data_dir).is_dir():
        raise ConfigError(f"data_dir {roster.data_dir} does not exist (run scripts/make_dataroom.py first)")
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
    setup_logging(-1 if args.quiet else (1 if args.verbose else 0))
    tail = ConsoleTail(db_path).start()
    server = LiveServer(db_path, args.port).start(open_browser=not args.no_browser) if args.watch else None
    try:
        outcome = run_swarm(roster, specs, brief, db_path, validators=validators, admission=admission)
    finally:
        tail.stop()
    result, ledger = outcome.result, outcome.ledger
    tasks = []
    for t in ledger.tasks.list():
        art = ledger.artifacts.latest(t.id)
        tasks.append({"id": t.id, "kind": t.kind, "required": t.required,
                      "status": t.status, "artifact_id": art.id if art else None})
    print(json.dumps({"run_id": run_id, "db": db_path, **asdict(result), "tasks": tasks},
                     indent=2, sort_keys=True), flush=True)
    if server is not None:
        _wait_for_ctrl_c(f"run finished ({result.status}); live view still at {server.url} (Ctrl-C to exit)")
        server.stop()
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
        return _watch(args) if args.command == "watch" else _run(args)
    except (ConfigError, LedgerError, yaml.YAMLError, OSError) as e:
        print(f"error: {' '.join(str(e).split())}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
