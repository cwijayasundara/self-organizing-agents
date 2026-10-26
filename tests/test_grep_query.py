import pytest

from agora.ledger.grep_query import QueryError, compile_query


@pytest.mark.parametrize("q,text,hit", [
    ("pricing", "Pricing tier set", True),
    ("pricing & germany", "pricing for Germany", True),
    ("pricing & germany", "pricing for France", False),
    ("france | germany", "germany first", True),
    ("(france | germany) & churn", "germany churn spike", True),
    ('"price war"', "a price war looms", True),
    ('"price war"', "price and war", False),
    ("a | b & c", "a only", True),      # & binds tighter than |
    ("a | b & c", "b only", False),
    ("a | b & c", "b and c", True),
    ("pricing", "nothing here", False),
])
def test_compile_query(q, text, hit):
    assert compile_query(q)(text) is hit


@pytest.mark.parametrize("bad", ["", "   ", "a &", "| a", "a & | b", "(a | b", "a ) b", "()", "a b"])
def test_bad_query_raises(bad):
    with pytest.raises(QueryError):
        compile_query(bad)
