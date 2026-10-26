import pytest

from agora.eval.report import aggregate, decide, render_markdown
from agora.eval.runner import ResultRow


def row(arm, recall=0.5, judge=3.0, spend=1.0, status="done", seed=0, elapsed=10.0):
    return ResultRow(arm, 0, seed, status, spend, elapsed, recall, recall, True, 1.0, 1, [], [],
                     judge, "haiku" if judge is not None else None, 0.0, "", {})


def side(arm, n, **kw):
    return [row(arm, seed=i, **kw) for i in range(n)]


def test_aggregate_math():
    rows = [row("c1-10", 0.2, 2.0, 1.0, "done", 0, 10), row("c1-10", 0.6, 4.0, 3.0, "error", 1, 30),
            row("c0-glm", 0.5)]
    s = aggregate(rows)
    assert [x.arm for x in s] == ["c0-glm", "c1-10"]
    a = s[1]
    assert a.n == 2 and a.recall_mean == pytest.approx(0.4) and a.judge_mean == pytest.approx(3.0)
    assert a.spend_mean == pytest.approx(2.0) and a.elapsed_mean == pytest.approx(20.0)
    assert a.done_rate == 0.5 and a.error_rate == 0.5


def test_judge_none_ignored():
    s = aggregate([row("c1-10", judge=None), row("c1-10", judge=4.0)])
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
