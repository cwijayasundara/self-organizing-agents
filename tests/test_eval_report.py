import pytest

from agora.eval.report import aggregate, decide, render_markdown
from agora.eval.runner import ResultRow


def row(arm, recall=0.5, judge=3.0, spend=1.0, status="done", seed=0, elapsed=10.0):
    return ResultRow(arm, 0, seed, status, spend, elapsed, recall, recall, True, 1.0, 1, [], [],
                     judge, "haiku" if judge is not None else None, 0.0, "", {})


def side(arm, n, **kw):
    return [row(arm, seed=i, **kw) for i in range(n)]


def test_aggregate_math():
    rows = [row("c1-10", 0.2, 2.0, 1.0, "done", 0, 10), row("c1-10", 0.6, 4.0, 3.0, "done", 1, 30),
            row("c1-10", 0.0, None, 9.0, "error", 2, 99), row("c0-glm", 0.5)]
    s = aggregate(rows)
    assert [x.arm for x in s] == ["c0-glm", "c1-10"]
    a = s[1]
    assert a.n == 3 and a.n_ok == 2 and a.recall_mean == pytest.approx(0.4) and a.judge_mean == pytest.approx(3.0)
    assert a.spend_mean == pytest.approx(2.0) and a.elapsed_mean == pytest.approx(20.0)
    assert a.done_rate == pytest.approx(2 / 3) and a.error_rate == pytest.approx(1 / 3)


def test_judge_none_ignored():
    s = aggregate([row("c1-10", judge=None), row("c1-10", judge=4.0, seed=1)])
    assert s[0].judge_mean == 4.0
    assert aggregate([row("c1-10", judge=None)])[0].judge_mean is None


def test_decide_swarm_wins():
    d = decide(side("c1-10", 3, recall=0.8, judge=4.0, spend=2.0) + side("c0-glm", 3, recall=0.5, judge=3.0)
               + side("c0-deepseek", 3, recall=0.3, judge=2.0))
    assert d.verdict == "swarm wins" and d.details["base_arm"] == "c0-glm"
    assert d.details["cost_ratio"] == pytest.approx(2.0)


def test_decide_swarm_loses():
    d = decide(side("c1-10", 3, recall=0.3, judge=2.0) + side("c0-glm", 3, recall=0.5, judge=3.0))
    assert d.verdict == "swarm loses"


def test_decide_inconclusive():
    d = decide(side("c1-10", 3, recall=0.55, judge=3.2) + side("c0-glm", 3, recall=0.5, judge=3.0))
    assert d.verdict == "inconclusive"
    d = decide(side("c1-10", 3, recall=0.8, judge=3.1) + side("c0-glm", 3, recall=0.5, judge=3.0))
    assert d.verdict == "inconclusive"  # recall margin met, judge margin not


def test_decide_too_few_rows():
    d = decide(side("c1-10", 2, recall=0.9) + side("c0-glm", 3, recall=0.1))
    assert d.verdict == "inconclusive" and ">= 3 rows" in d.reason


def test_decide_no_judge_scores():
    d = decide(side("c1-10", 3, recall=0.9, judge=None) + side("c0-glm", 3, recall=0.1, judge=3.0))
    assert d.verdict == "inconclusive" and "judge" in d.reason


def test_render_markdown_contains_every_arm_decision_and_caveats():
    rows = side("c1-10", 3) + side("c0-glm", 3) + side("c2-3", 1)
    md = render_markdown(aggregate(rows), decide(rows))
    for a in ("c1-10", "c0-glm", "c2-3"):
        assert a in md
    assert "Decision" in md and "inconclusive" in md and "Caveats" in md
    assert "single judge" in md and "keyword" in md


def test_decide_excludes_error_rows_and_reports_n_error():
    rows = (side("c1-10", 2, recall=0.9, judge=4.0) + [row("c1-10", 0.0, None, status="error", seed=9)]
            + side("c0-glm", 3, recall=0.1, judge=2.0))
    d = decide(rows)
    assert d.verdict == "inconclusive" and ">= 3 rows" in d.reason
    assert d.details["n_error_swarm"] == 1 and d.details["n_swarm"] == 2
    d = decide(rows + [row("c1-10", 0.9, 4.0, seed=3)])
    assert d.verdict == "swarm wins" and d.details["n_error_swarm"] == 1


def test_latest_row_per_key_wins():
    rows = [row("c1-10", 0.0, None, status="error", seed=0), row("c1-10", 0.8, 4.0, seed=0)]
    a = aggregate(rows)[0]
    assert a.n == 1 and a.n_ok == 1 and a.recall_mean == 0.8 and a.error_rate == 0


def test_decide_float_boundary():
    win = decide(side("c1-10", 3, recall=0.6, judge=3.5) + side("c0-glm", 3, recall=0.5, judge=3.0))
    assert win.verdict == "swarm wins"
    below = decide(side("c1-10", 3, recall=0.59, judge=3.5) + side("c0-glm", 3, recall=0.5, judge=3.0))
    assert below.verdict == "inconclusive"
    lose = decide(side("c1-10", 3, recall=0.5, judge=3.0) + side("c0-glm", 3, recall=0.6, judge=3.5))
    assert lose.verdict == "swarm loses"


def test_caveats_mention_errors_and_done_rate():
    md = render_markdown(aggregate(side("c1-10", 1)), decide([]))
    assert "excluded" in md and "retried" in md and "not comparable" in md
