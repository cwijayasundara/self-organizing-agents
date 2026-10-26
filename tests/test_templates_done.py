import pytest

from agora.config import ConfigError
from agora.done import DoneStatus, evaluate_done
from agora.ledger.types import TaskSpec
from agora.templates import load_template, seed_tasks
from conftest import approve_through_review, spec


def task_yaml(id, deps=(), kind=None, extra=""):
    s = (
        f"  - id: {id}\n    title: T {id}\n    objective: obj\n    output_format: md\n"
        f"    acceptance: [a, b]\n    deps: [{', '.join(deps)}]\n"
    )
    if kind:
        s += f"    kind: {kind}\n"
    return s + extra


def write(tmp_path, body):
    p = tmp_path / "t.yaml"
    p.write_text(body)
    return str(p)


def tpl(tmp_path, *tasks):
    return write(tmp_path, "tasks:\n" + "".join(tasks))


def test_load_valid(tmp_path):
    specs = load_template(tpl(tmp_path, task_yaml("A"), task_yaml("I", ["A"], "integration")))
    assert [s.id for s in specs] == ["A", "I"]
    assert specs[0].required is True and specs[0].kind == "work"
    assert specs[1].kind == "integration" and specs[1].deps == ["A"]
    assert specs[0].acceptance == ["a", "b"]


def test_required_false_parsed(tmp_path):
    specs = load_template(tpl(tmp_path, task_yaml("A", extra="    required: false\n"), task_yaml("I", [], "integration")))
    assert specs[0].required is False


def test_cycle_rejected(tmp_path):
    p = tpl(tmp_path, task_yaml("A", ["B"]), task_yaml("B", ["A"]), task_yaml("I", ["A"], "integration"))
    with pytest.raises(ConfigError, match="cycle"):
        load_template(p)


def test_missing_integration_rejected(tmp_path):
    with pytest.raises(ConfigError, match="integration"):
        load_template(tpl(tmp_path, task_yaml("A")))


def test_unknown_dep_rejected(tmp_path):
    p = tpl(tmp_path, task_yaml("A", ["ZZ"]), task_yaml("I", [], "integration"))
    with pytest.raises(ConfigError, match="ZZ"):
        load_template(p)


def test_duplicate_id_rejected(tmp_path):
    p = tpl(tmp_path, task_yaml("A"), task_yaml("A"), task_yaml("I", [], "integration"))
    with pytest.raises(ConfigError, match="duplicate.*A"):
        load_template(p)


def test_missing_key_rejected(tmp_path):
    p = write(tmp_path, "tasks:\n  - id: A\n    title: t\n    kind: integration\n")
    with pytest.raises(ConfigError, match="A"):
        load_template(p)


def test_unknown_key_rejected(tmp_path):
    p = tpl(tmp_path, task_yaml("A", extra="    bogus: 1\n"), task_yaml("I", [], "integration"))
    with pytest.raises(ConfigError, match="bogus"):
        load_template(p)


def test_review_kind_rejected(tmp_path):
    p = tpl(tmp_path, task_yaml("A", kind="review"), task_yaml("I", [], "integration"))
    with pytest.raises(ConfigError, match="review"):
        load_template(p)


def test_empty_task_list_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_template(write(tmp_path, "tasks: []\n"))
    with pytest.raises(ConfigError):
        load_template(write(tmp_path, "other: 1\n"))


def test_malformed_yaml_wrapped(tmp_path):
    with pytest.raises(ConfigError):
        load_template(write(tmp_path, "tasks: [unclosed\n  - : :"))


def test_missing_file_wrapped(tmp_path):
    with pytest.raises(ConfigError):
        load_template(str(tmp_path / "nope.yaml"))


def test_seed_topological(ledger):
    specs = [spec("I", deps=["B"], kind="integration"), spec("B", deps=["A"]), spec("A")]
    seed_tasks(ledger, specs)
    assert {t.id for t in ledger.tasks.list()} == {"A", "B", "I"}
    assert ledger.tasks.get("I").deps == ["B"]


def test_done_only_when_all_required_done(ledger):
    seed_tasks(ledger, [spec("A"), spec("I", deps=["A"], kind="integration")])
    ledger.tasks.create_task(TaskSpec(id="sub:P01:1", title="t", objective="o", output_format="f", acceptance=[], deps=[], required=False))
    assert evaluate_done(ledger) == DoneStatus(False, ["A", "I"])
    approve_through_review(ledger, "A")
    approve_through_review(ledger, "I")
    assert evaluate_done(ledger).done is True


def test_empty_ledger_not_done(ledger):
    assert evaluate_done(ledger) == DoneStatus(False, [])
