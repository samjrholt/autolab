"""MLflow-style filter DSL over the Record ledger.

Grammar (tiny on purpose)::

    filter    ::= clause (" and " clause)*
    clause    ::= path op value
    path      ::= namespace "." field
    namespace ::= "tags" | "outputs" | "inputs" | "record" | "decision" | "metadata"
    op        ::= "=" | "!=" | ">=" | "<=" | ">" | "<" | "in" | "not_in"
    value     ::= number | quoted-string | list

Examples::

    tags.sensor = 'superellipse' and outputs.sensitivity >= 1.5
    record.operation = 'superellipse_hysteresis' and record.record_status = 'completed'
    inputs.Ms > 800000
    tags in ['demo', 'sensor']

Semantics
---------

- ``tags`` namespace: membership check against ``record.tags`` list.
  ``tags.foo = 'bar'`` means "the tag ``foo:bar`` is present" (colon-
  delimited tag convention).  ``tags in ['demo']`` means "any of these
  tags is present in record.tags".
- ``record.<field>`` accesses top-level fields (``operation``,
  ``record_status``, ``failure_mode``, ``campaign_id``, ``sample_id``,
  ``module``, ``gate_result``, ``outcome_class``, …).
- Other namespaces access the matching dict field on the Record.

Unknown paths evaluate to ``None`` and fail any equality/ordering check.
The DSL is permissive on whitespace and quote style.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

from autolab.models import Record

_SUPPORTED_NS = {"tags", "outputs", "inputs", "record", "decision", "metadata"}
_OPS = ("!=", ">=", "<=", ">", "<", "=", " in ", " not_in ")


class QueryError(ValueError):
    """Raised on malformed filter expressions."""


def apply(records: Sequence[Record] | Iterable[Record], expression: str) -> list[Record]:
    """Return the subset of ``records`` matching ``expression``.

    Empty / blank expression returns the full list (no filter).
    """
    expression = (expression or "").strip()
    if not expression:
        return list(records)
    clauses = _split_clauses(expression)
    predicates = [_parse_clause(c) for c in clauses]
    return [r for r in records if all(p(r) for p in predicates)]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _split_clauses(expression: str) -> list[str]:
    out: list[str] = []
    buf = []
    depth = 0
    in_quote: str | None = None
    tokens = re.split(r"(\s+and\s+)", expression, flags=re.IGNORECASE)
    # re.split keeps separators; rebuild respecting quoted strings.
    for tok in tokens:
        if tok.strip().lower() == "and" and in_quote is None and depth == 0:
            clause = "".join(buf).strip()
            if clause:
                out.append(clause)
            buf = []
            continue
        for ch in tok:
            if in_quote:
                if ch == in_quote:
                    in_quote = None
            elif ch in "\"'":
                in_quote = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
        buf.append(tok)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _parse_clause(clause: str):
    for op in _OPS:
        idx = _find_op(clause, op)
        if idx is not None:
            op_clean = op.strip()
            path = clause[:idx].strip()
            value_raw = clause[idx + len(op) :].strip()
            value = _parse_value(value_raw)
            return _build_predicate(path, op_clean, value)
    raise QueryError(f"no recognised operator in clause {clause!r}")


def _find_op(clause: str, op: str) -> int | None:
    # Skip inside quotes.
    idx = 0
    in_quote: str | None = None
    while idx < len(clause):
        ch = clause[idx]
        if in_quote:
            if ch == in_quote:
                in_quote = None
            idx += 1
            continue
        if ch in "\"'":
            in_quote = ch
            idx += 1
            continue
        if clause.startswith(op, idx):
            return idx
        idx += 1
    return None


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        raise QueryError("empty value in clause")
    if raw[0] in "'\"" and raw[-1] == raw[0]:
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        parts = re.split(r"\s*,\s*", inner)
        return [_parse_value(p) for p in parts]
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        # Unquoted bare word: treat as string.
        return raw


def _build_predicate(path: str, op: str, value: Any):
    namespace, _, field = path.partition(".")
    namespace = namespace.strip()
    field = field.strip()
    if namespace == "tags" and not field:
        # Bare tags check: `tags in [...]` / `tags = 'foo'`.
        def _pred(rec: Record) -> bool:
            return _compare_tags(rec.tags, op, value)

        return _pred
    if namespace not in _SUPPORTED_NS:
        raise QueryError(f"unknown namespace {namespace!r} in {path!r}")

    def _pred(rec: Record) -> bool:
        actual = _resolve(rec, namespace, field)
        return _compare(actual, op, value)

    return _pred


def _resolve(rec: Record, namespace: str, field: str) -> Any:
    if namespace == "tags":
        # tags.foo → True if "foo:<value>" style tag is present; exact value compared in caller.
        prefix = f"{field}:"
        for t in rec.tags:
            if t == field or t.startswith(prefix):
                return t.split(":", 1)[1] if ":" in t else t
        return None
    if namespace == "record":
        return getattr(rec, field, None)
    holder = getattr(rec, namespace, None)
    if isinstance(holder, dict):
        return holder.get(field)
    return None


def _compare_tags(tags: list[str], op: str, value: Any) -> bool:
    if op in ("=", "!="):
        present = value in tags or any(t.startswith(f"{value}:") for t in tags)
        return present if op == "=" else not present
    if op == "in":
        if not isinstance(value, list):
            return False
        return any(v in tags or any(t.startswith(f"{v}:") for t in tags) for v in value)
    if op == "not_in":
        if not isinstance(value, list):
            return True
        return not any(v in tags or any(t.startswith(f"{v}:") for t in tags) for v in value)
    raise QueryError(f"operator {op!r} not supported on bare `tags`")


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "=":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return isinstance(expected, list) and actual in expected
    if op == "not_in":
        return isinstance(expected, list) and actual not in expected
    if actual is None:
        return False
    try:
        if op == ">=":
            return float(actual) >= float(expected)
        if op == "<=":
            return float(actual) <= float(expected)
        if op == ">":
            return float(actual) > float(expected)
        if op == "<":
            return float(actual) < float(expected)
    except (TypeError, ValueError):
        return False
    raise QueryError(f"unsupported operator {op!r}")


__all__ = ["QueryError", "apply"]
