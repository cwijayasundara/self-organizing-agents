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
