"""Orchestrator — the only thing in the framework that writes Records.

For each Operation:

1. Materialise a write-ahead Record with ``record_status="pending"`` and
   persist it through the Ledger (crash before the run → breadcrumb).
2. Acquire the Operation's Resource (atomic, blocks until free).
3. Update the Record to ``running``.
4. Run the Operation.
5. On exception → ``failed`` Record with ``failure_mode="equipment_failure"``.
   On ``OperationResult.status="failed"`` → ``failed`` Record with
   ``failure_mode`` taken from the result (or ``"process_deviation"`` if
   not set by the Operation). On success → finalise with outputs, features,
   gate verdict, and ``outcome_class``.
6. Publish events around each transition.

Failure taxonomy
----------------

The Orchestrator stamps three distinct failure modes:

``equipment_failure``
    The ``Operation.run()`` raised an unhandled exception. The instrument
    did not complete. The sample is unchanged. Retry is safe.

``process_deviation``
    The Operation returned ``OperationResult(status="failed")`` without
    providing its own ``failure_mode``. The instrument ran but something
    went wrong in the process (e.g. sintering temperature not reached).
    Human review is warranted before retry.

``measurement_rejection``
    The Operation self-reported ``failure_mode="measurement_rejection"``.
    The measurement ran; the data is unreliable. The sample is intact.

``synthesis_deviation``
    The Operation self-reported this, or the gate failed on a *completed*
    result. The process ran; the product differed from the intended target.
    This is a *discovery*, not a failure — the Planner should explore it.

``outcome_class``
    On *completed* Records: ``on_target`` (gate passed), ``off_target``
    (gate failed), or ``exceptional`` (Operation self-reported).

These fields are orthogonal to ``record_status`` and give the Planner
the information it needs to decide *retry* vs *explore* vs *escalate*.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from autolab.acceptance import GateVerdict, evaluate
from autolab.events import Event, EventBus
from autolab.models import (
    AcceptanceCriteria,
    FailureMode,
    OperationResult,
    OutcomeClass,
    ProposedStep,
    Record,
    Resource,
    Sample,
    Session,
)
from autolab.operations.base import Operation, OperationContext
from autolab.provenance.store import Ledger
from autolab.resources.manager import ResourceManager
from autolab.tools.registry import ToolDeclaration, ToolRegistry

PreHook = Callable[["OperationContext", "OrchestratorState"], Awaitable[None] | None]
PostHook = Callable[
    ["OperationContext", "OrchestratorState", OperationResult, GateVerdict],
    Awaitable[None] | None,
]


@dataclass
class OrchestratorState:
    """Mutable per-Operation state passed to hooks."""

    record: Record
    resource: Resource | None = None
    sample: Sample | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignRun:
    """Identifier bundle the Orchestrator carries through one campaign run."""

    lab_id: str
    campaign_id: str
    session: Session


class Orchestrator:
    """Owns the provenance contract — the only writer of Records."""

    def __init__(
        self,
        ledger: Ledger,
        resources: ResourceManager,
        tools: ToolRegistry,
        events: EventBus | None = None,
    ) -> None:
        self.ledger = ledger
        self.resources = resources
        self.tools = tools
        self.events = events or EventBus()
        self.pre_hooks: list[PreHook] = []
        self.post_hooks: list[PostHook] = []

    # ------------------------------------------------------------------
    # Hook registration
    # ------------------------------------------------------------------

    def add_pre_hook(self, hook: PreHook) -> None:
        self.pre_hooks.append(hook)

    def add_post_hook(self, hook: PostHook) -> None:
        self.post_hooks.append(hook)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run_step(
        self,
        step: ProposedStep,
        run: CampaignRun,
        *,
        acceptance: AcceptanceCriteria | None = None,
        upstream_samples: list[Sample] | None = None,
    ) -> tuple[Record, GateVerdict]:
        """Run one ProposedStep through the full provenance contract."""
        decl = self.tools.get(step.operation)
        adapter_cls = self.tools.adapter(step.operation)

        record = self._make_pending_record(step, decl, run, upstream_samples or [])
        record = await self.ledger.append(record)
        self.events.publish(
            Event(kind="record.pending", payload={"record": record.model_dump(mode="json")})
        )

        try:
            if decl.resource_kind:
                async with self.resources.acquire(
                    decl.resource_kind,
                    requires=decl.requires,
                    holder=record.id,
                ) as resource:
                    return await self._run_with_resource(
                        record=record,
                        adapter_cls=adapter_cls,
                        decl=decl,
                        step=step,
                        run=run,
                        upstream_samples=upstream_samples or [],
                        acceptance=acceptance,
                        resource=resource,
                    )
            return await self._run_with_resource(
                record=record,
                adapter_cls=adapter_cls,
                decl=decl,
                step=step,
                run=run,
                upstream_samples=upstream_samples or [],
                acceptance=acceptance,
                resource=None,
            )
        except Exception as exc:
            # Exception escaped resource acquisition — treat as equipment failure.
            record = await self._fail(record, exc, failure_mode="equipment_failure")
            return record, GateVerdict(result="fail", reason=f"orchestrator error: {exc!r}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_pending_record(
        self,
        step: ProposedStep,
        decl: ToolDeclaration,
        run: CampaignRun,
        upstream_samples: list[Sample],
    ) -> Record:
        resource_asset_id: str | None = None
        return Record(
            lab_id=run.lab_id,
            campaign_id=run.campaign_id,
            experiment_id=step.experiment_id,
            session_id=run.session.id,
            operation=step.operation,
            module=decl.module,
            tool_declaration_hash=decl.declaration_hash,
            inputs=dict(step.inputs),
            source_record_ids=list(step.source_record_ids),
            parent_ids=list(step.source_record_ids),
            parent_sample_ids=[s.id for s in upstream_samples],
            resource_kind=decl.resource_kind,
            resource_asset_id=resource_asset_id,
            record_status="pending",
            decision=dict(step.decision),
            tags=[],
        )

    async def _run_with_resource(
        self,
        *,
        record: Record,
        adapter_cls: type[Operation],
        decl: ToolDeclaration,
        step: ProposedStep,
        run: CampaignRun,
        upstream_samples: list[Sample],
        acceptance: AcceptanceCriteria | None,
        resource: Resource | None,
    ) -> tuple[Record, GateVerdict]:
        running = record.model_copy(
            update={
                "record_status": "running",
                "resource_name": resource.name if resource else None,
                "resource_asset_id": resource.asset_id if resource else None,
            }
        )
        running = await self.ledger.append(running)
        self.events.publish(
            Event(kind="record.running", payload={"record": running.model_dump(mode="json")})
        )

        ctx = OperationContext(
            record_id=running.id,
            operation=step.operation,
            resource=resource,
            upstream_samples=upstream_samples,
            metadata={"campaign_id": run.campaign_id},
        )

        await self._fire_pre_hooks(ctx, OrchestratorState(record=running, resource=resource))

        start = time.perf_counter()
        try:
            result = await adapter_cls.call(step.inputs, ctx)
        except Exception as exc:
            # Unhandled exception from the Operation → equipment failure.
            failed = await self._fail(running, exc, failure_mode="equipment_failure")
            return failed, GateVerdict(
                result="fail",
                reason=f"operation raised {type(exc).__name__}: {exc}",
            )

        duration_ms = int((time.perf_counter() - start) * 1000)

        if result.status != "completed":
            # The Operation itself reported failure.
            fmode: FailureMode = result.failure_mode or "process_deviation"
            failed = await self._fail_result(running, result, duration_ms, failure_mode=fmode)
            return failed, GateVerdict(
                result="fail",
                reason=result.error or f"operation returned status={result.status!r}",
            )

        gate = evaluate(acceptance, result.outputs)

        # Determine outcome_class: prefer what the Operation told us, else derive from gate.
        oclass: OutcomeClass
        if result.outcome_class is not None:
            oclass = result.outcome_class
        elif gate.result == "pass":
            oclass = "on_target"
        else:
            oclass = "off_target"

        sample = result.new_sample
        if sample is None and decl.produces_sample:
            sample = Sample(
                parent_sample_ids=[s.id for s in upstream_samples],
                label=f"{step.operation} output",
            )

        finalised = running.model_copy(
            update={
                "record_status": result.status,
                "outputs": dict(result.outputs),
                "features": result.features,
                "error": result.error,
                "duration_ms": duration_ms,
                "sample_id": sample.id if sample else running.sample_id,
                "parent_sample_ids": [s.id for s in upstream_samples],
                "gate_result": gate.result,
                "decision_grade": gate.result == "pass",
                "outcome_class": oclass,
                "failure_mode": None,
                "finalised_at": datetime.now(UTC),
            }
        )
        finalised = await self.ledger.append(finalised)

        await self._fire_post_hooks(
            ctx,
            OrchestratorState(record=finalised, resource=resource, sample=sample),
            result,
            gate,
        )

        self.events.publish(
            Event(
                kind=f"record.{result.status}",
                payload={
                    "record": finalised.model_dump(mode="json"),
                    "gate": {"result": gate.result, "reason": gate.reason},
                    "outcome_class": oclass,
                },
            )
        )
        return finalised, gate

    async def _fail(
        self,
        record: Record,
        exc: BaseException,
        *,
        failure_mode: FailureMode = "equipment_failure",
    ) -> Record:
        failed = record.model_copy(
            update={
                "record_status": "failed",
                "failure_mode": failure_mode,
                "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
                "finalised_at": datetime.now(UTC),
            }
        )
        failed = await self.ledger.append(failed)
        self.events.publish(
            Event(
                kind="record.failed",
                payload={
                    "record": failed.model_dump(mode="json"),
                    "failure_mode": failure_mode,
                },
            )
        )
        return failed

    async def _fail_result(
        self,
        record: Record,
        result: OperationResult,
        duration_ms: int,
        *,
        failure_mode: FailureMode,
    ) -> Record:
        """Persist a non-exception Operation failure (result.status != completed)."""
        failed = record.model_copy(
            update={
                "record_status": "failed",
                "failure_mode": failure_mode,
                "error": result.error or f"status={result.status!r}",
                "outputs": dict(result.outputs),
                "duration_ms": duration_ms,
                "finalised_at": datetime.now(UTC),
            }
        )
        failed = await self.ledger.append(failed)
        self.events.publish(
            Event(
                kind="record.failed",
                payload={
                    "record": failed.model_dump(mode="json"),
                    "failure_mode": failure_mode,
                },
            )
        )
        return failed

    async def _fire_pre_hooks(self, ctx: OperationContext, state: OrchestratorState) -> None:
        for hook in self.pre_hooks:
            res = hook(ctx, state)
            if hasattr(res, "__await__"):
                await res  # type: ignore[func-returns-value]

    async def _fire_post_hooks(
        self,
        ctx: OperationContext,
        state: OrchestratorState,
        result: OperationResult,
        gate: GateVerdict,
    ) -> None:
        for hook in self.post_hooks:
            res = hook(ctx, state, result, gate)
            if hasattr(res, "__await__"):
                await res  # type: ignore[func-returns-value]


__all__ = ["CampaignRun", "Orchestrator", "OrchestratorState"]
