"""Watch a run from its ledger: readable progress logs and a live HTML view.

Both read the SQLite ledger through their own read-only connections, so they work for a run in this
process (`agora run --watch`), a run in another process, or a finished run (`agora watch <db>`).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agora.result import choose_final_tasks

log = logging.getLogger("agora")

POLL_S = 1.0
MAX_ROWS = 2000
SPEND_STEP_USD = 0.10


class LedgerReader:
    """Incremental reads of a ledger file; each call opens a short-lived read-only connection."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection | None:
        if not Path(self.db_path).exists():
            return None
        conn = sqlite3.connect(f"file:{Path(self.db_path).resolve()}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError:  # table not created yet, or a ledger from before the events table
            return []

    def state(self, notes: int = 0, messages: int = 0, events: int = 0) -> dict:
        """Everything after the given ids, plus the full task list and spend totals."""
        conn = self._connect()
        if conn is None:
            return {"waiting": True}
        try:
            tasks = self._rows(conn, "SELECT id, title, objective, kind, status, owner, owner_family, required, "
                                     "review_of, artifact_id, version FROM tasks ORDER BY rowid")
            deps: dict[str, list[str]] = {}
            for d in self._rows(conn, "SELECT task_id, dep_id FROM task_deps ORDER BY rowid"):
                deps.setdefault(d["task_id"], []).append(d["dep_id"])
            for t in tasks:
                t["deps"] = deps.get(t["id"], [])
            spend = self._rows(conn, "SELECT agent_id, COUNT(*) AS calls, SUM(usd) AS usd, "
                                     "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
                                     "FROM spend GROUP BY agent_id")
            first = self._rows(conn, "SELECT detail, created_at FROM events WHERE kind='run_start' "
                                     "ORDER BY id DESC LIMIT 1")
            end = self._rows(conn, "SELECT detail, created_at FROM events WHERE kind='run_end' "
                                   "ORDER BY id DESC LIMIT 1")
            brief_rows = self._rows(conn, "SELECT value FROM run_meta WHERE key='brief'")
            return {
                "waiting": False,
                "roster": json.loads(first[0]["detail"]) if first else None,
                "started_at": first[0]["created_at"] if first else None,
                "ended": {"status": end[0]["detail"], "at": end[0]["created_at"]} if end else None,
                "brief": brief_rows[0]["value"] if brief_rows else None,
                "final": self._final(conn, tasks),
                "tasks": tasks,
                "spend": spend,
                "notes": self._rows(conn, "SELECT id, author, type, text, task_id, detail, created_at, invalidated "
                                          "FROM notes WHERE id>? ORDER BY id LIMIT ?", (notes, MAX_ROWS)),
                "messages": self._rows(conn, "SELECT id, sender, recipient, text, urgent, created_at "
                                             "FROM messages WHERE id>? ORDER BY id LIMIT ?", (messages, MAX_ROWS)),
                "events": self._rows(conn, "SELECT id, actor, kind, task_id, detail, created_at "
                                           "FROM events WHERE id>? ORDER BY id LIMIT ?", (events, MAX_ROWS)),
            }
        finally:
            conn.close()

    def agent(self, agent_id: str) -> dict | None:
        """Recorded profile, or the original roster entry for an older ledger."""
        conn = self._connect()
        if conn is None:
            return None
        try:
            rows = self._rows(conn, "SELECT detail FROM agent_profiles WHERE agent_id=?", (agent_id,))
            if rows:
                return json.loads(rows[0]["detail"])
            starts = self._rows(conn, "SELECT detail FROM events WHERE kind='run_start' ORDER BY id DESC LIMIT 1")
            peers = json.loads(starts[0]["detail"]).get("peers", []) if starts else []
            for peer in peers:
                if peer["id"] == agent_id:
                    return {**peer, "recorded": False}
            # Old ledgers without roster events can still identify active peers.
            known = self._rows(conn, "SELECT author FROM notes WHERE author=? LIMIT 1", (agent_id,))
            known += self._rows(conn, "SELECT actor FROM events WHERE actor=? LIMIT 1", (agent_id,))
            return {"id": agent_id, "recorded": False} if known else None
        finally:
            conn.close()

    def _final(self, conn: sqlite3.Connection, tasks: list[dict]) -> list[dict]:
        chosen = []
        for task in choose_final_tasks(tasks):
            rows = self._rows(conn, "SELECT id, task_id, author, version, content FROM artifacts "
                                    "WHERE task_id=? ORDER BY version DESC LIMIT 1", (task["id"],))
            if not rows:
                continue
            art = rows[0]
            chosen.append({"task_id": task["id"], "title": task["title"], "id": art["id"],
                           "author": art["author"], "content": art["content"]})
        return chosen

    def artifact(self, task_id: str) -> dict | None:
        conn = self._connect()
        if conn is None:
            return None
        try:
            rows = self._rows(conn, "SELECT id, task_id, author, version, content, created_at FROM artifacts "
                                    "WHERE task_id=? ORDER BY version DESC LIMIT 1", (task_id,))
            return rows[0] if rows else None
        finally:
            conn.close()


# ---- console progress log -----------------------------------------------------
def _short(text: str | None, n: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


class ConsoleTail:
    """Background thread that turns new ledger rows into log lines on the `agora` logger."""

    def __init__(self, db_path: str, poll_s: float = POLL_S):
        self.reader = LedgerReader(db_path)
        self.poll_s = poll_s
        self._ids = {"notes": 0, "messages": 0, "events": 0}
        self._tasks: dict[str, tuple] = {}
        self._episodes: dict[str, int] = {}
        self._spend_mark = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="agora-console-tail", daemon=True)

    def start(self) -> ConsoleTail:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self.poll()  # flush whatever landed after the last tick

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_s):
            try:
                self.poll()
            except sqlite3.Error as e:  # a busy or half-written ledger: try again next tick
                log.debug("console tail: %s", e)

    def poll(self) -> None:
        s = self.reader.state(**self._ids)
        if s.get("waiting"):
            return
        lines: list[tuple[float, int, str]] = []
        for e in s["events"]:
            self._ids["events"] = e["id"]
            level, text = self._event_line(e)
            if text:
                lines.append((e["created_at"], level, text))
        for n in s["notes"]:
            self._ids["notes"] = n["id"]
            task = f" {n['task_id']}" if n["task_id"] else ""
            lines.append((n["created_at"], logging.INFO, f"{n['author']:<7} 📝 {n['type']}{task}: {_short(n['text'])}"))
        for m in s["messages"]:
            self._ids["messages"] = m["id"]
            to = m["recipient"] or "all"
            flag = " (urgent)" if m["urgent"] else ""
            lines.append((m["created_at"], logging.INFO, f"{m['sender']:<7} ✉  → {to}{flag}: {_short(m['text'])}"))
        for ts, level, text in sorted(lines, key=lambda x: x[0]):
            log.log(level, text)
        self._log_tasks(s["tasks"])
        self._log_spend(s)

    def _event_line(self, e: dict) -> tuple[int, str]:
        actor, kind, detail = e["actor"], e["kind"], e["detail"]
        if kind == "run_start":
            r = json.loads(detail)
            peers = ", ".join(f"{p['id']}({p['family']})" for p in r["peers"])
            return logging.INFO, f"run {r['run_name']} started: {len(r['peers'])} peers [{peers}], " \
                                 f"budget ${r['swarm_usd']}, {r['wall_clock_s']}s"
        if kind == "run_end":
            return logging.INFO, f"run ended: {detail}"
        if kind == "episode_start":
            self._episodes[actor] = self._episodes.get(actor, 0) + 1
            return logging.INFO, f"{actor:<7} ▶  episode {self._episodes[actor]} starts ({_short(detail, 60)})"
        if kind == "episode_end":
            return logging.DEBUG, f"{actor:<7} ■  episode {self._episodes.get(actor, 0)} ends ({detail})"
        if kind == "episode_failed":
            return logging.WARNING, f"{actor:<7} ✗  episode failed: {_short(detail)}"
        if kind == "tool":
            return logging.DEBUG, f"{actor:<7} 🔧 {_short(detail)}"
        if kind == "claim_refused":  # expected: another peer won, or the task is still blocked
            return logging.DEBUG, f"{actor:<7} ·  {_short(detail, 220)}"
        if kind == "tool_error":  # keep the error readable: shorten the call, not the reason
            call, _, error = (detail or "").partition(" -> ")
            return logging.INFO, f"{actor:<7} ⚠  {_short(call, 90)} -> {_short(error, 220)}"
        if kind == "nudge":
            return logging.INFO, f"runner  👉 nudged {detail} (no board note last episode)"
        if kind in ("budget_warning", "peer_retired", "peer_exhausted"):
            return logging.WARNING, f"runner  ⚠  {kind.replace('_', ' ')}: {_short(detail)}"
        return logging.DEBUG, f"{actor:<7} {kind}: {_short(detail)}"

    def _log_tasks(self, tasks: list[dict]) -> None:
        for t in tasks:
            key = (t["status"], t["owner"])
            old = self._tasks.get(t["id"])
            self._tasks[t["id"]] = key
            if old == key:
                continue
            label = f"{t['id']} ({_short(t['title'], 50)})"
            if old is None:
                if t["kind"] == "review":
                    log.info("task    ＋ %s created to review %s", label, t["review_of"])
                elif not t["required"]:
                    log.info("task    ＋ %s proposed by a peer", label)
                if t["status"] == "open" or t["kind"] == "review":
                    continue
                old = ("open", None)  # claimed between two polls of a task we had not seen yet
            if t["status"] == "claimed" and old[0] == "open":
                log.info("task    ✋ %s claimed by %s", label, t["owner"])
            elif t["status"] == "claimed" and old[0] == "in_review":
                log.info("task    ↩ %s sent back to %s by review", label, t["owner"])
            elif t["status"] == "open":
                log.info("task    ↺ %s released by %s", label, old[1])
            elif t["status"] == "in_review":
                log.info("task    🔍 %s submitted for review by %s", label, t["owner"])
            elif t["status"] == "done":
                log.info("task    ✅ %s done", label)

    def _log_spend(self, s: dict) -> None:
        total = sum(r["usd"] or 0 for r in s["spend"])
        if total >= self._spend_mark + SPEND_STEP_USD:
            self._spend_mark = total - (total % SPEND_STEP_USD)
            budget = s["roster"]["swarm_usd"] if s["roster"] else None
            done = sum(1 for t in s["tasks"] if t["status"] == "done")
            of = f" / ${budget:.2f}" if budget else ""
            log.info("spend   💲 $%.2f%s  ·  tasks done %d/%d", total, of, done, len(s["tasks"]))


# ---- live HTML view -------------------------------------------------------------
def _page() -> bytes:
    return files("agora").joinpath("web/live.html").read_bytes()


def _handler(reader: LedgerReader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal for the progress log
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    return self._send(200, _page(), "text/html; charset=utf-8")
                if url.path == "/api/state":
                    ids = {k: int(q.get(k, 0)) for k in ("notes", "messages", "events")}
                    return self._send(200, json.dumps(reader.state(**ids)).encode(), "application/json")
                if url.path == "/api/artifact":
                    art = reader.artifact(q.get("task", ""))
                    return self._send(200 if art else 404, json.dumps(art).encode(), "application/json")
                if url.path == "/api/agent":
                    agent = reader.agent(q.get("id", ""))
                    return self._send(200 if agent else 404, json.dumps(agent).encode(), "application/json")
                return self._send(404, b"not found", "text/plain")
            except (ValueError, sqlite3.Error) as e:
                return self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")

    return Handler


class LiveServer:
    """Serve the live view of one ledger on localhost from a daemon thread."""

    def __init__(self, db_path: str, port: int = 8765):
        handler = _handler(LedgerReader(db_path))
        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError:  # port taken: let the OS pick one
            self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="agora-live-view", daemon=True)

    def start(self, open_browser: bool = True) -> LiveServer:
        self._thread.start()
        log.info("live view: %s", self.url)
        if open_browser:
            webbrowser.open(self.url)
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class _StderrHandler(logging.StreamHandler):
    """Writes to whatever sys.stderr is at emit time (stdout stays pure JSON)."""

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, _):
        pass


def setup_logging(verbosity: int) -> None:
    """verbosity: -1 quiet (warnings only), 0 progress, 1 progress plus every tool call."""
    level = {-1: logging.WARNING, 0: logging.INFO}.get(verbosity, logging.DEBUG)
    logger = logging.getLogger("agora")
    logger.setLevel(level)
    if not any(isinstance(h, _StderrHandler) for h in logger.handlers):
        h = _StderrHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logger.addHandler(h)
        logger.propagate = False
