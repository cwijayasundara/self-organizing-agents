"""Board grep query language: terms, quoted phrases, `&`, `|`, parentheses.

Grammar:  or := and ('|' and)* ;  and := atom ('&' atom)* ;  atom := TERM | '(' or ')'
Terms match as case-insensitive substrings.
"""
from __future__ import annotations

import re
from typing import Callable

_TOKEN = re.compile(r'\s*(?:(?P<op>[&|()])|"(?P<q>[^"]*)"|(?P<w>[^\s&|()"]+))')


class QueryError(ValueError):
    pass


def _tokenize(q: str) -> list[tuple[str, str]]:
    toks: list[tuple[str, str]] = []
    pos = 0
    q = q.rstrip()
    while pos < len(q):
        m = _TOKEN.match(q, pos)
        if not m:
            raise QueryError(f"unterminated quote in query: {q!r}")
        if m.group("op"):
            toks.append(("op", m.group("op")))
        elif m.group("q") is not None:
            if not m.group("q").strip():
                raise QueryError("empty quoted term")
            toks.append(("term", m.group("q").lower()))
        else:
            toks.append(("term", m.group("w").lower()))
        pos = m.end()
    return toks


def compile_query(q: str) -> Callable[[str], bool]:
    toks = _tokenize(q)
    if not toks:
        raise QueryError("empty query")
    i = 0

    def peek() -> tuple[str, str] | None:
        return toks[i] if i < len(toks) else None

    def parse_or() -> Callable[[str], bool]:
        nonlocal i
        parts = [parse_and()]
        while peek() == ("op", "|"):
            i += 1
            parts.append(parse_and())
        return lambda t: any(p(t) for p in parts)

    def parse_and() -> Callable[[str], bool]:
        nonlocal i
        parts = [parse_atom()]
        while peek() == ("op", "&"):
            i += 1
            parts.append(parse_atom())
        return lambda t: all(p(t) for p in parts)

    def parse_atom() -> Callable[[str], bool]:
        nonlocal i
        tok = peek()
        if tok is None:
            raise QueryError("dangling operator: expected a term")
        kind, val = tok
        if kind == "term":
            i += 1
            return lambda t: val in t.lower()
        if val == "(":
            i += 1
            inner = parse_or()
            if peek() != ("op", ")"):
                raise QueryError("unbalanced parentheses: missing ')'")
            i += 1
            return inner
        raise QueryError(f"unexpected {val!r}")

    fn = parse_or()
    if i != len(toks):
        raise QueryError(f"unexpected {toks[i][1]!r}")
    return fn
