import pytest

from agora.config import load_roster
from agora.ledger import open_ledger
from agora.ledger.types import TaskSpec


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def ledger(tmp_path, clock):
    led = open_ledger(
        str(tmp_path / "l.sqlite"),
        clock=clock,
        prices=load_roster("roster.example.yaml").models,
    )
    yield led
    led.db.close()


def spec(id, deps=(), kind="work", title=None, required=True):
    return TaskSpec(
        id=id,
        title=title if title is not None else f"Task {id}",
        objective="Produce the deliverable described by this task.",
        output_format="Markdown document with headings.",
        acceptance=["criterion one", "criterion two", "criterion three"],
        deps=list(deps),
        required=required,
        kind=kind,
    )


def claimed_with_artifact(ledger, task_id, agent, family):
    """Create task_id if missing, claim it, commit a 300-char artifact, return the Artifact."""
    if not ledger.db.read("SELECT 1 FROM tasks WHERE id=?", (task_id,)):
        ledger.tasks.create_task(spec(task_id))
    ledger.tasks.claim(task_id, agent, family)
    return ledger.artifacts.commit(task_id, agent, "x" * 300)


def approve_through_review(ledger, task_id):
    """Drive task_id to done: work as P01/deepseek, review-approve as P03/anthropic."""
    t = ledger.tasks.get(task_id)
    if t.status != "claimed":
        ledger.tasks.claim(task_id, "P01", "deepseek")
        t = ledger.tasks.get(task_id)
    art = ledger.artifacts.commit(task_id, t.owner, "y" * 300)
    review = ledger.tasks.submit_for_review(task_id, t.owner, art.id)
    ledger.tasks.claim(review.id, "P03", "anthropic")
    return ledger.tasks.record_verdict(review.id, "P03", True, "looks good")


def task_args(**overrides):
    """Valid args dict for the create_task tool, with overrides applied."""
    args = {
        "title": "Sub task",
        "objective": "Produce the deliverable described by this task.",
        "output_format": "Markdown document with headings.",
        "acceptance": ["criterion one", "criterion two", "criterion three"],
        "deps": [],
    }
    args.update(overrides)
    return args


def make_tools_by_name(agent_id, ledger, family="deepseek"):
    from agora.tools import make_peer_tools

    return {t.name: t for t in make_peer_tools(agent_id, family, ledger)}
