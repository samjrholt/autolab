"""Evaluator for the dict-of-rules :class:`~autolab.models.AcceptanceCriteria`.

Inputs come from an Operation's ``outputs`` dict (typically scalar numbers).
The evaluator returns a structured :class:`GateVerdict` carrying:

- an aggregate ``result`` (``pass`` / ``soft_fail`` / ``fail``),
- a short, human-readable ``reason`` (for the PolicyProvider to read),
- a ``failures`` tuple of reason-strings (one per failing rule), and
- a ``details`` dict (``{output_key: GateDetail}``) giving per-rule
  pass/fail, operator, threshold and actual value.

The per-rule ``details`` map is how an LLM PolicyProvider decides *which*
rule is the problem when a gate fails — not just "something failed". It
also drives the ML dataset: ``GateDetail.passed`` becomes a column per
criterion when a Campaign is exported via :class:`autolab.DatasetBuilder`.

See [docs/design/GLOSSARY.md](../../docs/design/GLOSSARY.md) — entry
"AcceptanceCriteria".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autolab.models import AcceptanceCriteria, GateResult

_OPERATORS: dict[str, Any] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


@dataclass(frozen=True)
class GateDetail:
    """Per-rule evaluation result.

    ``actual`` is whatever was in ``outputs[key]`` (or ``None`` if the key
    was missing). ``reason`` is a short human string; empty when the rule
    passed cleanly.
    """

    key: str
    operator: str
    threshold: Any
    actual: Any
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class GateVerdict:
    """Aggregate acceptance verdict.

    ``details`` always has exactly one entry per rule in the criteria (by
    key) — so a PolicyProvider can iterate ``verdict.details.values()``
    and read per-rule pass/fail without re-parsing ``reason``.
    """

    result: GateResult
    reason: str
    failures: tuple[str, ...] = ()
    details: dict[str, GateDetail] = field(default_factory=dict)


def evaluate(
    criteria: AcceptanceCriteria | None,
    outputs: dict[str, Any],
    *,
    soft_fail_keys: set[str] | None = None,
) -> GateVerdict:
    """Apply each rule to the matching key in ``outputs``.

    A missing output key is a hard fail. A rule failure on a key in
    ``soft_fail_keys`` produces ``soft_fail`` instead of ``fail`` (but
    only if *every* failure is a soft-fail — any hard failure wins). If
    no rules are present the gate auto-passes with an empty details dict.
    """
    if criteria is None or not criteria.rules:
        return GateVerdict(result="pass", reason="no acceptance criteria configured")

    failures: list[str] = []
    hard_fail = False
    soft_fail_hit = False
    soft_fail_keys = soft_fail_keys or set()
    details: dict[str, GateDetail] = {}

    for key, rule in criteria.rules.items():
        if key not in outputs:
            msg = f"missing output {key!r}"
            failures.append(msg)
            details[key] = GateDetail(
                key=key,
                operator="missing",
                threshold=None,
                actual=None,
                passed=False,
                reason=msg,
            )
            if key in soft_fail_keys:
                soft_fail_hit = True
            else:
                hard_fail = True
            continue

        actual = outputs[key]
        rule_passed = True
        rule_reason = ""
        last_op = ""
        last_threshold: Any = None

        for op, threshold in rule.items():
            last_op = op
            last_threshold = threshold
            fn = _OPERATORS.get(op)
            if fn is None:
                rule_passed = False
                rule_reason = f"{key}: unknown operator {op!r}"
                failures.append(rule_reason)
                hard_fail = True
                break
            try:
                ok = bool(fn(actual, threshold))
            except Exception as exc:
                rule_passed = False
                rule_reason = f"{key}: evaluator error {exc!r}"
                failures.append(rule_reason)
                hard_fail = True
                break
            if not ok:
                rule_passed = False
                rule_reason = f"{key}={actual!r} fails {op} {threshold!r}"
                failures.append(rule_reason)
                if key in soft_fail_keys:
                    soft_fail_hit = True
                else:
                    hard_fail = True
                break

        details[key] = GateDetail(
            key=key,
            operator=last_op,
            threshold=last_threshold,
            actual=actual,
            passed=rule_passed,
            reason=rule_reason,
        )

    if not failures:
        return GateVerdict(
            result="pass",
            reason="all acceptance rules satisfied",
            details=details,
        )
    result: GateResult = "soft_fail" if soft_fail_hit and not hard_fail else "fail"
    return GateVerdict(
        result=result,
        reason="; ".join(failures),
        failures=tuple(failures),
        details=details,
    )


__all__ = ["GateDetail", "GateVerdict", "evaluate"]
