"""Planner — the decision engine for a Campaign.

Two abstract methods:

- ``plan(context) → list[ProposedStep]`` — propose the next batch
- ``react(context) → Action`` — adapt after one step completes (default:
  delegates to the :class:`PolicyProvider`)

Separation of concerns
----------------------

The :class:`Planner` structures the decision problem.
The :class:`PolicyProvider` actually decides.

This lets an LLM-backed PolicyProvider live behind a BO Planner, or a
heuristic short-circuit run in front of an LLM, without touching the
Planner class. The two are composable and swappable independently.

Failure-aware heuristics
------------------------

The default :class:`HeuristicPolicyProvider` reads one optional field on
the :class:`~autolab.models.Record`:

``failure_mode``
    *Why* the operation stopped.  Drives the retry/escalate decision:

    - ``equipment_failure`` → retry (instrument glitch, sample unchanged)
    - ``process_deviation`` → escalate (conditions drifted, human should review)
    - ``measurement_rejection`` → retry (sample intact, measurement was bad)
    - ``synthesis_deviation`` → continue/explore (unexpected but valid result)

For *completed* Records, the :class:`~autolab.acceptance.GateVerdict` tells
the policy whether the result met the acceptance criteria. Gate pass →
``accept``; gate fail → ``replan``. A failed furnace run should be retried;
a synthesis that produced an unexpected product should be explored, not
discarded.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from autolab.acceptance import GateVerdict
from autolab.models import (
    AcceptanceCriteria,
    Action,
    ActionType,
    Objective,
    ProposedStep,
    Record,
    Resource,
)


@dataclass
class PlanContext:
    """Snapshot of campaign state handed to a Planner's ``plan()``.

    ``objective`` is the typed :class:`~autolab.models.Objective` the
    Campaign is driving toward.
    """

    campaign_id: str
    objective: Objective
    history: Sequence[Record]
    resources: Sequence[Resource]
    acceptance: AcceptanceCriteria | None = None
    remaining_budget: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionContext:
    """Snapshot of campaign state handed to a PolicyProvider's ``decide()``.

    Carries the just-finalised Record, the gate verdict, and the open
    Action set the PolicyProvider may choose from.
    """

    campaign_id: str
    record: Record
    gate: GateVerdict
    history: Sequence[Record]
    allowed_actions: tuple[ActionType, ...]
    remaining_budget: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failure_mode(self) -> str | None:
        return self.record.failure_mode  # type: ignore[return-value]


class PolicyProvider(ABC):
    """Decides which Action a Planner returns from ``react()``."""

    @abstractmethod
    def decide(self, context: DecisionContext) -> Action: ...


class Planner(ABC):
    """Abstract Planner — ``plan()`` proposes batches, ``react()`` adapts."""

    name: str = "anonymous"

    def __init__(self, policy: PolicyProvider | None = None) -> None:
        self.policy = policy or HeuristicPolicyProvider()

    @abstractmethod
    def plan(self, context: PlanContext) -> list[ProposedStep]:
        """Propose the next batch of Operations."""

    def react(self, context: DecisionContext) -> Action:
        """Default: delegate to the PolicyProvider."""
        return self.policy.decide(context)


# ---------------------------------------------------------------------------
# HeuristicPolicyProvider — failure-aware, deterministic, no LLM
# ---------------------------------------------------------------------------


class HeuristicPolicyProvider(PolicyProvider):
    """Cheap, deterministic policy driven by the failure taxonomy.

    Decision tree:

    1. **Equipment failure + retry allowed + retries remaining** → ``retry_step``
       (instrument glitch; sample is unchanged, safe to retry)

    2. **Measurement rejection + retry allowed + retries remaining** → ``retry_step``
       (measurement was bad; sample is intact, just re-measure)

    3. **Process deviation + escalate allowed** → ``escalate``
       (conditions drifted; a human should review before we retry)

    4. **Synthesis deviation** → ``continue``
       (Operation reported the product differs from target; keep exploring)

    5. **Gate pass** → ``accept`` if allowed

    6. **Gate fail** → ``replan`` if allowed, else ``continue``

    7. **Otherwise** → ``continue``
    """

    def __init__(self, max_retries: int = 1) -> None:
        self.max_retries = max_retries

    def decide(self, context: DecisionContext) -> Action:
        rec = context.record
        allowed = set(context.allowed_actions)
        fmode = context.failure_mode

        # --- Equipment failure: retry if safe ---
        if (
            rec.record_status == "failed"
            and fmode == "equipment_failure"
            and ActionType.RETRY_STEP in allowed
        ):
            already = self._failed_count(context, fmode="equipment_failure")
            if already <= self.max_retries:
                return Action(
                    type=ActionType.RETRY_STEP,
                    reason=(
                        f"equipment_failure on {rec.operation!r}; "
                        f"retry {already}/{self.max_retries}"
                    ),
                    payload={"source_record_ids": rec.source_record_ids},
                )

        # --- Measurement rejection: retry measurement ---
        if (
            rec.record_status == "failed"
            and fmode == "measurement_rejection"
            and ActionType.RETRY_STEP in allowed
        ):
            already = self._failed_count(context, fmode="measurement_rejection")
            if already <= self.max_retries:
                return Action(
                    type=ActionType.RETRY_STEP,
                    reason=(
                        f"measurement_rejection on {rec.operation!r}; "
                        f"sample intact, retry measurement {already}/{self.max_retries}"
                    ),
                    payload={"source_record_ids": rec.source_record_ids},
                )

        # --- Process deviation: escalate for human review ---
        if rec.record_status == "failed" and fmode == "process_deviation":
            if ActionType.ESCALATE in allowed:
                return Action(
                    type=ActionType.ESCALATE,
                    reason=(
                        f"process_deviation on {rec.operation!r}; "
                        "conditions drifted — human review required before retry"
                    ),
                )

        # --- Synthesis deviation: Operation self-reported off-target, keep exploring ---
        if fmode == "synthesis_deviation":
            return Action(
                type=ActionType.CONTINUE,
                reason=(
                    f"synthesis_deviation on {rec.operation!r}; "
                    "unexpected product is a discovery — continuing exploration"
                ),
            )

        # --- Standard gate logic ---
        if context.gate.result == "pass" and ActionType.ACCEPT in allowed:
            return Action(type=ActionType.ACCEPT, reason=context.gate.reason)
        if context.gate.result == "fail" and ActionType.REPLAN in allowed:
            return Action(type=ActionType.REPLAN, reason=context.gate.reason)

        return Action(type=ActionType.CONTINUE, reason=context.gate.reason)

    def _failed_count(self, context: DecisionContext, *, fmode: str) -> int:
        """Count prior failures with the given failure_mode for this operation."""
        return sum(
            1
            for r in context.history
            if r.operation == context.record.operation
            and r.record_status == "failed"
            and r.failure_mode == fmode
        )


__all__ = [
    "DecisionContext",
    "HeuristicPolicyProvider",
    "PlanContext",
    "Planner",
    "PolicyProvider",
]
