"""Aggregation, the pre-registered decision rule and the Markdown report."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agora.eval.arms import ARM_IDS

DONE_STATUSES = {"done", "finished"}
MIN_ROWS = 3
RECALL_MARGIN = 0.10
JUDGE_MARGIN = 0.5
EPS = 1e-9  # float tolerance at the pre-registered boundaries


@dataclass(frozen=True)
class ArmSummary:
    arm: str
    n: int
    n_ok: int
    recall_mean: float
    summary_accuracy_mean: float
    judge_mean: float | None
    spend_mean: float
    elapsed_mean: float
    done_rate: float
    error_rate: float


@dataclass(frozen=True)
class Decision:
    verdict: Literal["swarm wins", "swarm loses", "inconclusive"]
    reason: str
    details: dict


def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _judge_mean(rows) -> float | None:
    js = [r.judge_mean for r in rows if r.judge_mean is not None]
    return sum(js) / len(js) if js else None


def latest_rows(rows) -> list:
    """The latest row per (arm, variant, seed); a retry replaces an earlier error row."""
    latest: dict = {}
    for r in rows:
        latest[(r.arm, r.variant, r.seed)] = r
    return list(latest.values())


def aggregate(rows) -> list[ArmSummary]:
    out = []
    rows = latest_rows(rows)
    for arm in ARM_IDS:
        rs = [r for r in rows if r.arm == arm]
        if not rs:
            continue
        ok = [r for r in rs if r.status != "error"]
        out.append(ArmSummary(
            arm, len(rs), len(ok), _mean(r.recall for r in ok), _mean(r.summary_accuracy for r in ok),
            _judge_mean(ok), _mean(r.spend_usd for r in ok), _mean(r.elapsed_s for r in ok),
            sum(r.status in DONE_STATUSES for r in rs) / len(rs),
            sum(r.status == "error" for r in rs) / len(rs)))
    return out


def decide(rows) -> Decision:
    rows = latest_rows(rows)
    ok_rows = [r for r in rows if r.status != "error"]
    n_err = lambda arm: sum(r.arm == arm and r.status == "error" for r in rows)
    swarm = [r for r in ok_rows if r.arm == "c1-10"]
    bases = {a: [r for r in ok_rows if r.arm == a] for a in ("c0-deepseek", "c0-glm")}
    bases = {a: rs for a, rs in bases.items() if rs}
    if not bases:
        return Decision("inconclusive", "needs >= 3 rows per side",
                        {"n_swarm": len(swarm), "n_base": 0, "n_error_swarm": n_err("c1-10"),
                         "n_error_base": n_err("c0-deepseek") + n_err("c0-glm")})
    base_arm = min(bases, key=lambda a: (-_mean(r.recall for r in bases[a]), _mean(r.spend_usd for r in bases[a])))
    base = bases[base_arm]
    details: dict = {"base_arm": base_arm, "n_swarm": len(swarm), "n_base": len(base),
                      "n_error_swarm": n_err("c1-10"), "n_error_base": n_err(base_arm)}
    if len(swarm) < MIN_ROWS or len(base) < MIN_ROWS:
        return Decision("inconclusive", "needs >= 3 rows per side", details)
    sr, br = _mean(r.recall for r in swarm), _mean(r.recall for r in base)
    ss, bs = _mean(r.spend_usd for r in swarm), _mean(r.spend_usd for r in base)
    sj, bj = _judge_mean(swarm), _judge_mean(base)
    details.update(swarm_recall=sr, base_recall=br, swarm_judge=sj, base_judge=bj,
                   cost_ratio=(ss / bs if bs else None))
    if sj is None or bj is None:
        return Decision("inconclusive", "no judge scores on at least one side", details)
    d_recall, d_judge = sr - br, sj - bj
    details.update(d_recall=d_recall, d_judge=d_judge)
    msg = f"d_recall={d_recall:+.3f}, d_judge={d_judge:+.2f} vs {base_arm}"
    if d_recall >= RECALL_MARGIN - EPS and d_judge >= JUDGE_MARGIN - EPS:
        return Decision("swarm wins", msg, details)
    if d_recall <= -RECALL_MARGIN + EPS and d_judge <= -JUDGE_MARGIN + EPS:
        return Decision("swarm loses", msg, details)
    return Decision("inconclusive", "margins not met: " + msg, details)


_CAVEATS = """\
- Recall detectors are per-line keyword matches and have known false negatives.
- Judge scores come from a single judge per run, not an ensemble.
- Error rows (status "error") are not observations: they are excluded from means and the decision, and an interrupted or failed run is retried on resume (the latest row per run wins).
- done_rate counts the baselines' "finished" (which includes hitting the episode cap) against the swarm's "done" and is not comparable.
- With the example config every pilot run is judged by the same single judge (pick_judge rotation uses variant+seed).
- peer_usd per swarm peer is budget/4.
- The supervisor's subagent call limit is applied per delegation and is about 1.5x the single arm's per-episode calls (approximate step mapping).
- The pre-registered rule requires BOTH margins for a win and BOTH for a loss (the plan text said "either" for a loss; the code and tests encode "both").
- Arm asymmetries: validators are enforced only for the swarm arms; baselines stop at 90% of spend or 20 episodes; the subagent call limit is per delegation.
"""


def _f(x, spec: str) -> str:
    return "n/a" if x is None else format(x, spec)


def render_markdown(summaries, decision: Decision) -> str:
    lines = ["# Evaluation report", "",
             "| arm | n (ok) | recall | summary acc. | judge | spend (USD) | elapsed (s) | done rate | error rate |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        lines.append(f"| {s.arm} | {s.n} ({s.n_ok}) | {s.recall_mean:.3f} | {s.summary_accuracy_mean:.3f} | "
                     f"{_f(s.judge_mean, '.2f')} | {s.spend_mean:.3f} | {s.elapsed_mean:.0f} | "
                     f"{s.done_rate:.2f} | {s.error_rate:.2f} |")
    lines += ["", "## Decision", "", f"**{decision.verdict}**: {decision.reason}", ""]
    for k, v in decision.details.items():
        lines.append(f"- {k}: {v if not isinstance(v, float) else round(v, 4)}")
    lines += ["", "## Caveats", "", _CAVEATS]
    return "\n".join(lines)
