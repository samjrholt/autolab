"""EstimationEngine — per-(operation, resource) duration model.

Builds a best-guess duration estimate for every known Operation by
reading completed Records out of the Ledger and taking the median
measured ``duration_ms`` per ``(operation, resource_name)`` pair.

Fallback chain, in order:

1. Median measured duration for ``(operation, resource_name)`` in the
   ledger (if we have at least 2 samples).
2. Median measured duration for ``operation`` on *any* resource.
3. ``ToolDeclaration.typical_duration_s`` on the registered tool.
4. A module-level default (60 seconds) — better than lying.

The engine is read-only: it reads the Ledger; it never writes.  It is
cheap to call and safe to call often, so the server just rebuilds it
on demand rather than caching aggressively.

ETA projection
--------------

:meth:`eta_for_campaign` projects the finish time of an in-flight
Campaign by summing the estimated durations of every ``pending`` and
``running`` Record.  A running Record's remaining time is assumed to
be ``max(0, estimate - elapsed)``.  Concurrency across resources is
honoured by grouping pending work per ``resource_name`` — at most one
Operation per resource instance at a time — and returning the max of
the per-resource sums.

This is a *projection*, not a guarantee; it is what the Console shows
in the ETA column.  The Ledger is still the ground truth.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import TYPE_CHECKING

from autolab.models import Record

if TYPE_CHECKING:
    from autolab.lab import Lab
    from autolab.tools.registry import ToolRegistry

DEFAULT_DURATION_S = 60


@dataclass(frozen=True)
class DurationEstimate:
    """Best-guess duration for one (operation, resource) pair."""

    operation: str
    resource_name: str | None
    seconds: float
    source: str  # "measured" | "measured_any_resource" | "declared" | "default"
    n_samples: int


class EstimationEngine:
    """Duration estimates from historical Records + tool declarations."""

    def __init__(self, lab: Lab) -> None:
        self._lab = lab

    # ------------------------------------------------------------------
    # Duration estimates
    # ------------------------------------------------------------------

    def estimate(
        self,
        operation: str,
        resource_name: str | None = None,
    ) -> DurationEstimate:
        measured_pair: list[float] = []
        measured_any: list[float] = []

        for rec in self._lab.ledger.iter_records():
            if rec.operation != operation:
                continue
            if rec.record_status != "completed":
                continue
            if rec.duration_ms is None:
                continue
            measured_any.append(rec.duration_ms / 1000.0)
            if resource_name and rec.resource_name == resource_name:
                measured_pair.append(rec.duration_ms / 1000.0)

        if resource_name and len(measured_pair) >= 2:
            return DurationEstimate(
                operation=operation,
                resource_name=resource_name,
                seconds=float(median(measured_pair)),
                source="measured",
                n_samples=len(measured_pair),
            )
        if len(measured_any) >= 2:
            return DurationEstimate(
                operation=operation,
                resource_name=resource_name,
                seconds=float(median(measured_any)),
                source="measured_any_resource",
                n_samples=len(measured_any),
            )
        declared = _declared_duration(self._lab.tools, operation)
        if declared is not None:
            return DurationEstimate(
                operation=operation,
                resource_name=resource_name,
                seconds=float(declared),
                source="declared",
                n_samples=0,
            )
        return DurationEstimate(
            operation=operation,
            resource_name=resource_name,
            seconds=float(DEFAULT_DURATION_S),
            source="default",
            n_samples=0,
        )

    def summary(self) -> list[dict]:
        """One row per registered Operation, for the Console table."""
        rows: list[dict] = []
        for decl in self._lab.tools.list():
            est = self.estimate(decl.capability)
            rows.append(
                {
                    "operation": decl.capability,
                    "resource_kind": decl.resource_kind,
                    "declared_seconds": decl.typical_duration_s,
                    "estimate_seconds": est.seconds,
                    "source": est.source,
                    "n_samples": est.n_samples,
                }
            )
        return rows

    # ------------------------------------------------------------------
    # ETA projection
    # ------------------------------------------------------------------

    def eta_for_campaign(self, campaign_id: str) -> dict:
        """Project remaining-seconds and finish-time for a Campaign.

        Honours concurrency: per-resource queues are summed independently
        and the overall finish is ``max(queue_duration_per_resource)``.
        Pending Records without an assigned ``resource_name`` fall into a
        virtual ``"_unassigned"`` queue (assumed fully parallel).
        """
        now = datetime.now(UTC)
        per_resource_pending: dict[str, float] = defaultdict(float)
        pending_count = 0
        running_count = 0

        for rec in self._lab.ledger.iter_records(campaign_id=campaign_id):
            if rec.record_status == "pending":
                pending_count += 1
                est = self.estimate(rec.operation, rec.resource_name).seconds
                key = rec.resource_name or "_unassigned"
                per_resource_pending[key] += est
            elif rec.record_status == "running":
                running_count += 1
                est = self.estimate(rec.operation, rec.resource_name).seconds
                elapsed = (now - rec.created_at).total_seconds()
                remaining = max(0.0, est - elapsed)
                key = rec.resource_name or "_unassigned"
                per_resource_pending[key] += remaining

        # Finish time = max across resources (concurrent lanes).
        if per_resource_pending:
            finish_s = max(per_resource_pending.values())
        else:
            finish_s = 0.0

        return {
            "campaign_id": campaign_id,
            "now_iso": now.isoformat(),
            "pending_records": pending_count,
            "running_records": running_count,
            "per_resource_seconds": dict(per_resource_pending),
            "remaining_seconds": finish_s,
            "finish_iso": (now + timedelta(seconds=finish_s)).isoformat(),
        }

    # ------------------------------------------------------------------
    # ETA projection for a proposed workflow
    # ------------------------------------------------------------------

    def eta_for_workflow(
        self,
        operations: list[str],
        *,
        resource_hint: str | None = None,
    ) -> dict:
        """Rough ETA for a *proposed* sequence of Operations.

        Sums estimated durations in order (no DAG / parallelism —
        pessimistic upper bound).  Useful for the campaign-design
        preview panel.
        """
        total = 0.0
        per_op: list[dict] = []
        for op in operations:
            est = self.estimate(op, resource_hint)
            per_op.append(
                {
                    "operation": op,
                    "seconds": est.seconds,
                    "source": est.source,
                }
            )
            total += est.seconds
        return {"total_seconds": total, "steps": per_op}


def _declared_duration(tools: ToolRegistry, operation: str) -> int | None:
    if not tools.has(operation):
        return None
    return tools.get(operation).typical_duration_s


def wire_learning_hook(lab: Lab) -> None:
    """Register a no-op post hook so future iterations can add live learning.

    Today the engine recomputes on demand from the Ledger, so no hook is
    strictly needed — but every write going through the Orchestrator
    makes the next ``estimate()`` call more accurate automatically.  This
    function is a placeholder so callers can opt in to an event-driven
    cache without changing call sites later.
    """
    _ = lab  # reserved for future in-memory cache; Ledger is source of truth.


__all__ = ["DurationEstimate", "EstimationEngine", "wire_learning_hook"]
