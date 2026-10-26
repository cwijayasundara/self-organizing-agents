"""Ledger-backed tools a peer agent can call. Authorship is always the calling agent."""
from __future__ import annotations

import functools

from langchain_core.tools import BaseTool, tool

from agora.ledger import Ledger
from agora.ledger.grep_query import QueryError
from agora.ledger.types import LedgerError, Task, TaskSpec
from agora.render import note_line, render_notes, task_line, wrap_block, wrap_lines


def _safe(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (LedgerError, QueryError) as e:
            return f"ERROR: {e}"
    return inner


def _task_detail(t: Task) -> str:
    body = "\n".join([f"{t.id}: {t.title}", f"Objective: {t.objective}",
                      f"Output format: {t.output_format}", "Acceptance:", *[f"- {a}" for a in t.acceptance]])
    return wrap_block(body)


def make_peer_tools(agent_id: str, family: str, ledger: Ledger) -> list[BaseTool]:
    def mk(fn):
        return tool(_safe(fn))

    def board_read(since_id: int = 0) -> str:
        """Read the notes posted to the shared board after note id since_id (0 for the latest notes)."""
        return render_notes(ledger.board.recent(since_id=since_id))

    def board_write(type: str, text: str, task_id: str | None = None, detail: str | None = None) -> str:
        """Post a typed note (FACT, OBSERVED, FAIL, CLAIM, PATCH_SUMMARY, DISSENT or DECISION) to the shared board."""
        if type == "REVIEW":
            raise LedgerError("REVIEW notes are reserved for review verdicts; use review_verdict")
        note = ledger.board.write_note(agent_id, type, text, task_id=task_id, detail=detail)  # type: ignore[arg-type]
        return f"OK: wrote note G{note.id}"

    def board_grep(query: str) -> str:
        """Search all board notes (text and detail) with a query when you need earlier evidence."""
        return render_notes(ledger.board.grep(query))

    def board_unfold(note_id: int) -> str:
        """Show the full text and detail of one board note by its numeric id."""
        n = ledger.board.unfold(note_id)
        lines = [note_line(n), f"detail: {n.detail or '-'}"]
        return wrap_block("\n".join(lines))

    def list_tasks() -> str:
        """List every task with its status and owner to decide what to claim or wait on."""
        tasks = ledger.tasks.list()
        if not tasks:
            return "(none)"
        return wrap_lines([task_line(t, True) for t in tasks])

    def claim_task(task_id: str) -> str:
        """Claim an open, unblocked task so you can work on it; you may hold only one task at a time."""
        t = ledger.tasks.claim(task_id, agent_id, family)
        return f"OK: claimed {t.id}\n{_task_detail(t)}"

    def renew_task(task_id: str) -> str:
        """Extend the lease on a task you hold when you need more time to finish it."""
        ledger.tasks.renew(task_id, agent_id)
        return f"OK: renewed {task_id}"

    def release_task(task_id: str, reason: str) -> str:
        """Give up a task you hold, with a short reason, when you cannot finish it."""
        ledger.tasks.release(task_id, agent_id, reason)
        return f"OK: released {task_id}"

    def create_task(title: str, objective: str, output_format: str, acceptance: list[str], deps: list[str]) -> str:
        """Propose a new optional sub-task when you find necessary work no existing task covers."""
        prefix = f"sub:{agent_id}:"
        n = sum(1 for t in ledger.tasks.list() if t.id.startswith(prefix)) + 1
        spec = TaskSpec(id=f"{prefix}{n}", title=title, objective=objective, output_format=output_format,
                        acceptance=list(acceptance), deps=list(deps), required=False)
        task, created = ledger.tasks.reserve(spec)
        if created:
            return f"OK: created task {task.id}"
        return f"OK: a task with that title already exists: {task.id}"

    def commit_artifact(task_id: str, content: str) -> str:
        """Save your work product as a new artifact version for a task you hold."""
        a = ledger.artifacts.commit(task_id, agent_id, content)
        return f"OK: committed {a.id}"

    def read_artifact(task_id: str) -> str:
        """Read the latest artifact of a work task, or the artifact under review when given a review task id."""
        t = ledger.tasks.get(task_id)
        if t.kind == "review" and t.artifact_id:
            a = ledger.artifacts.get(t.artifact_id)
        else:
            a = ledger.artifacts.latest(task_id)
        if a is None:
            raise LedgerError(f"no artifact for {task_id}")
        return f"{a.id} by {a.author}\n{wrap_block(a.content)}"

    def send_dm(to: str, text: str, urgent: bool = True) -> str:
        """Send a direct message to one peer when you need their attention on something specific."""
        m = ledger.mail.send(agent_id, to, text, urgent)
        return f"OK: sent message {m.id} to {to}"

    def submit_for_review(task_id: str) -> str:
        """Submit your latest artifact for a task you hold once the work is complete."""
        a = ledger.artifacts.latest(task_id)
        if a is None:
            raise LedgerError(f"commit an artifact for {task_id} before submitting")
        review = ledger.tasks.submit_for_review(task_id, agent_id, a.id)
        return f"OK: submitted {a.id}; review task {review.id} created"

    def review_verdict(review_task_id: str, approve: bool, reasons: str) -> str:
        """Record your approve or reject verdict, with reasons, on a review task you hold."""
        work = ledger.tasks.record_verdict(review_task_id, agent_id, approve, reasons)
        return f"OK: verdict recorded; {work.id} is now {work.status}"

    return [mk(f) for f in (board_read, board_write, board_grep, board_unfold, list_tasks, claim_task,
                            renew_task, release_task, create_task, commit_artifact, read_artifact,
                            send_dm, submit_for_review, review_verdict)]

