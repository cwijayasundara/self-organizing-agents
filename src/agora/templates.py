"""Task templates: load/validate YAML and seed the ledger."""
from __future__ import annotations

import yaml

from agora.config import ConfigError
from agora.ledger.types import TaskSpec

_REQUIRED = {"id", "title", "objective", "output_format", "acceptance", "deps"}
_OPTIONAL = {"required", "kind"}


def _parse(raw: object, index: int) -> TaskSpec:
    if not isinstance(raw, dict):
        raise ConfigError(f"task #{index}: must be a mapping")
    name = raw.get("id", f"#{index}")
    unknown = set(raw) - _REQUIRED - _OPTIONAL
    if unknown:
        raise ConfigError(f"task {name}: unknown keys {sorted(unknown)}")
    missing = _REQUIRED - set(raw)
    if missing:
        raise ConfigError(f"task {name}: missing keys {sorted(missing)}")
    kind = raw.get("kind", "work")
    if kind not in ("work", "integration"):
        raise ConfigError(f"task {name}: invalid kind {kind!r} (review tasks cannot be templated)")
    for key in ("acceptance", "deps"):
        if not isinstance(raw[key], list):
            raise ConfigError(f"task {name}: {key} must be a list")
    return TaskSpec(
        id=str(raw["id"]), title=str(raw["title"]), objective=str(raw["objective"]),
        output_format=str(raw["output_format"]), acceptance=[str(a) for a in raw["acceptance"]],
        deps=[str(d) for d in raw["deps"]], required=bool(raw.get("required", True)), kind=kind,
    )


def _topo(specs: list[TaskSpec]) -> list[TaskSpec]:
    """Dependencies-first order; raises ConfigError naming a task on a cycle."""
    by_id = {s.id: s for s in specs}
    order: list[TaskSpec] = []
    state: dict[str, int] = {}  # 1 = visiting, 2 = done

    def visit(tid: str) -> None:
        if state.get(tid) == 2:
            return
        if state.get(tid) == 1:
            raise ConfigError(f"dependency cycle involving task {tid}")
        state[tid] = 1
        for d in by_id[tid].deps:
            visit(d)
        state[tid] = 2
        order.append(by_id[tid])

    for s in specs:
        visit(s.id)
    return order


def load_template(path: str) -> list[TaskSpec]:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"cannot read template {path}: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list) or not data["tasks"]:
        raise ConfigError(f"template {path}: needs a non-empty top-level 'tasks' list")
    unknown_top = set(data) - {"tasks"}
    if unknown_top:
        raise ConfigError(f"template {path}: unknown top-level keys {sorted(unknown_top)}")
    specs = [_parse(raw, i) for i, raw in enumerate(data["tasks"])]
    seen: set[str] = set()
    for s in specs:
        if s.id in seen:
            raise ConfigError(f"duplicate task id {s.id}")
        seen.add(s.id)
    for s in specs:
        for d in s.deps:
            if d not in seen:
                raise ConfigError(f"task {s.id}: unknown dependency {d}")
    _topo(specs)
    if not any(s.kind == "integration" for s in specs):
        raise ConfigError("template has no task of kind: integration")
    return specs


def seed_tasks(ledger, specs: list[TaskSpec]) -> None:
    for s in _topo(specs):
        ledger.tasks.create_task(s)
