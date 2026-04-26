"""Campaign — one goal-directed search inside a Lab.

Shape
-----

:class:`Campaign`
    Pydantic model authored in Python (or submitted over HTTP as JSON).
    Carries the objective, acceptance criteria, budget, and metadata.
    Immutable for the life of the run — if the scientist wants to change
    the objective, they start a new Campaign.

:class:`CampaignRunner`
    Drives the plan/dispatch/react loop against a running Lab.  Owns the
    Planner and the async lifecycle.  Every step is wrapped in the
    Orchestrator's provenance contract.

:class:`CampaignSummary`
    Returned by :meth:`CampaignRunner.run`.  Contains the accepted Record
    (if any), the best-so-far Record, and the full ledger tail.

Escalation parking
------------------

When the Planner's :class:`~autolab.planners.base.PolicyProvider` returns
``ActionType.ESCALATE``, the runner **parks** the current batch:

1. Creates an :class:`~autolab.models.Escalation` record.
2. Stores an ``asyncio.Event`` keyed by the escalation id.
3. Awaits the event — the runner is suspended until a human responds.
4. On resolution via :meth:`CampaignRunner.resolve_escalation`, the event
   is fired with an :class:`~autolab.models.EscalationResolution` attached.
5. The runner applies the resolution (continue / retry / stop / add_step)
   and resumes.

The escalation and its resolution are both written as Records to the
ledger so the full reasoning trail is preserved.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from contextlib import suppress
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from autolab.acceptance import GateVerdict
from autolab.events import Event
from autolab.models import (
    AcceptanceCriteria,
    Action,
    ActionType,
    Annotation,
    Escalation,
    EscalationResolution,
    Objective,
    ProposedStep,
    Record,
    WorkflowTemplate,
)
from autolab.orchestrator import CampaignRun
from autolab.planners.base import DecisionContext, PlanContext, Planner
from autolab.workflow import StepResult, WorkflowResult

if TYPE_CHECKING:
    from autolab.lab import Lab


# ---------------------------------------------------------------------------
# Campaign — Pydantic, user-authored
# ---------------------------------------------------------------------------


class Campaign(BaseModel):
    """A goal-directed search inside a Lab.

    ``objective`` is required and immutable for the run. ``acceptance`` is
    optional — if absent the run stops on budget alone.

    Examples
    --------
    >>> from autolab import AcceptanceCriteria, Campaign, Objective
    >>> campaign = Campaign(
    ...     name="bo-quadratic",
    ...     objective=Objective(key="score", direction="maximise"),
    ...     acceptance=AcceptanceCriteria(rules={"score": {">=": 0.95}}),
    ...     budget=24,
    ... )
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"camp-{uuid4().hex[:10]}")
    name: str
    objective: Objective
    description: str | None = None
    acceptance: AcceptanceCriteria | None = None
    budget: int | None = 32
    parallelism: int = 1
    workflow: WorkflowTemplate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignSummary(BaseModel):
    """Lightweight summary returned at the end of a run."""

    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    status: str  # accepted | budget_exhausted | stopped | empty | cancelled
    reason: str
    steps_run: int
    accepted_record_id: str | None = None
    best_record_id: str | None = None
    best_outputs: dict[str, Any] | None = None
    records: list[Record] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CampaignRunner — drives the plan/dispatch/react loop
# ---------------------------------------------------------------------------


class CampaignRunner:
    """Drives the plan/dispatch/react loop for one :class:`Campaign`."""

    def __init__(
        self,
        *,
        campaign: Campaign,
        planner: Planner,
        lab: Lab,
        session: Any,
    ) -> None:
        self.campaign = campaign
        self.planner = planner
        self.lab = lab
        self.session = session
        self._run = CampaignRun(
            lab_id=lab.lab_id,
            campaign_id=campaign.id,
            session=session,
        )
        self._steps_run = 0
        self._accepted: Record | None = None
        self._stopped: tuple[str, str] | None = None

        # Escalation tracking: {esc_id → (asyncio.Event, resolution | None)}
        self._escalations: dict[str, tuple[asyncio.Event, EscalationResolution | None]] = {}

    @property
    def id(self) -> str:
        return self.campaign.id

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> CampaignSummary:
        self.lab.events.publish(
            Event(
                kind="campaign.started",
                payload={
                    "campaign_id": self.campaign.id,
                    "name": self.campaign.name,
                    "objective": self.campaign.objective.model_dump(),
                },
            )
        )

        try:
            while not self._is_done():
                history = list(self.lab.ledger.iter_records(campaign_id=self.campaign.id))
                ctx = PlanContext(
                    campaign_id=self.campaign.id,
                    objective=self.campaign.objective,
                    history=history,
                    resources=self.lab.resources.list(),
                    acceptance=self.campaign.acceptance,
                    remaining_budget=self._remaining_budget(),
                    metadata=self.campaign.metadata,
                )
                proposals = self.planner.plan(ctx)
                if not proposals:
                    self._stopped = ("empty", "planner returned no proposals")
                    break
                await self._dispatch_batch(proposals)
        finally:
            self.lab.events.publish(
                Event(
                    kind="campaign.finished",
                    payload={"campaign_id": self.campaign.id, "status": self._status_text()},
                )
            )

        return self._summary()

    # ------------------------------------------------------------------
    # Escalation resolution (called externally by Lab / HTTP handler)
    # ------------------------------------------------------------------

    def resolve_escalation(self, escalation_id: str, resolution: EscalationResolution) -> None:
        """Resolve a parked escalation and resume the campaign.

        Called by :meth:`~autolab.lab.Lab.resolve_escalation` or the HTTP
        handler.  Fires the event that unblocks the waiting ``_react``
        coroutine.
        """
        if escalation_id not in self._escalations:
            raise KeyError(f"no pending escalation {escalation_id!r}")
        event, _ = self._escalations[escalation_id]
        self._escalations[escalation_id] = (event, resolution)
        event.set()

    def pending_escalations(self) -> list[Escalation]:
        """Return all escalations that have not yet been resolved."""
        return [
            Escalation(
                id=eid,
                campaign_id=self.campaign.id,
                record_id="",  # filled in _park_escalation
                reason="pending",
            )
            for eid, (evt, res) in self._escalations.items()
            if not evt.is_set()
        ]

    # ------------------------------------------------------------------
    # Loop internals
    # ------------------------------------------------------------------

    async def _dispatch_batch(self, proposals: Sequence[ProposedStep]) -> None:
        normalised: list[ProposedStep] = []
        for p in proposals:
            if p.experiment_id is None:
                p = p.model_copy(update={"experiment_id": f"exp-{uuid4().hex[:8]}"})
            normalised.append(p)

        sem = asyncio.Semaphore(max(1, self.campaign.parallelism))

        async def go(step: ProposedStep) -> tuple[ProposedStep, Record, GateVerdict]:
            async with sem:
                if self._is_done():
                    raise asyncio.CancelledError("campaign already finished")

                # If a workflow is configured, run it with the proposed step's inputs
                if self.campaign.workflow is not None:
                    workflow_step_ids = _find_workflow_steps(self.campaign.workflow, step.operation)
                    # Default: broadcast the flat inputs to every workflow step
                    # that matches the planner's target operation.
                    input_overrides: dict[str, dict[str, Any]] = {
                        sid: dict(step.inputs) for sid in workflow_step_ids
                    }
                    # Routed step_inputs override the broadcast for any step they
                    # cover (this is how a planner spreads trial parameters
                    # across e.g. material → step1, geometry → step2).
                    if step.step_inputs:
                        for sid, sinputs in step.step_inputs.items():
                            input_overrides[sid] = dict(sinputs)
                    wf_result = await self.lab._workflow_engine.run(
                        self.campaign.workflow,
                        self._run,
                        input_overrides=input_overrides,
                        decision_overrides={
                            step_id: dict(step.decision) for step_id in workflow_step_ids
                        },
                        acceptance=self.campaign.acceptance,
                    )
                    # For the planner's react() loop, use the workflow step that
                    # corresponds to the planner proposal, not an upstream setup step.
                    target = _find_workflow_result(wf_result, workflow_step_ids)
                    rec = (
                        target.record
                        if target is not None
                        else (wf_result.records[-1] if wf_result.records else None)
                    )
                    if rec is None:
                        raise RuntimeError("workflow failed before producing any records")
                    gate = (
                        target.gate
                        if target is not None
                        else GateVerdict(
                            result="fail",
                            reason="workflow failed before target step completed",
                        )
                    )
                    self._steps_run += 1
                    return step, rec, gate

                # Otherwise, dispatch the step normally
                rec, gate = await self.lab.orchestrator.run_step(
                    step, self._run, acceptance=self.campaign.acceptance
                )
                self._steps_run += 1
                return step, rec, gate

        results: list[tuple[ProposedStep, Record, GateVerdict]] = []
        for coro in asyncio.as_completed([go(p) for p in normalised]):
            try:
                results.append(await coro)
            except asyncio.CancelledError:
                continue

        for step, rec, gate in results:
            if self._accepted is not None or self._stopped is not None:
                break
            await self._react(step, rec, gate)

    async def _react(self, step: ProposedStep, record: Record, gate: GateVerdict) -> None:
        history = list(self.lab.ledger.iter_records(campaign_id=self.campaign.id))
        decision_ctx = DecisionContext(
            campaign_id=self.campaign.id,
            record=record,
            gate=gate,
            history=history,
            allowed_actions=(
                ActionType.CONTINUE,
                ActionType.STOP,
                ActionType.RETRY_STEP,
                ActionType.REPLAN,
                ActionType.ADD_STEP,
                ActionType.ESCALATE,
                *((ActionType.ACCEPT,) if self.campaign.acceptance is not None else ()),
            ),
            remaining_budget=self._remaining_budget(),
            metadata={"objective": self.campaign.objective},
        )
        action = self.planner.react(decision_ctx)
        await self._apply_action(step, record, action)

    async def _apply_action(self, step: ProposedStep, record: Record, action: Action) -> None:
        await self.lab.annotate(
            Annotation(
                target_record_id=record.id,
                kind="claim",
                body={
                    "action": action.type,
                    "reason": action.reason,
                    "payload": action.payload,
                },
                author=self.planner.name,
            )
        )

        if action.type is ActionType.ACCEPT:
            self._accepted = record

        elif action.type is ActionType.STOP:
            self._stopped = ("stopped", action.reason)

        elif action.type is ActionType.ESCALATE:
            await self._park_escalation(step, record, action)

        elif action.type is ActionType.RETRY_STEP:
            retry = step.model_copy(
                update={
                    "id": f"prop-{uuid4().hex[:12]}",
                    "decision": {
                        **step.decision,
                        "retry_of": record.id,
                        "reason": action.reason,
                    },
                    "source_record_ids": list(
                        action.payload.get("source_record_ids") or step.source_record_ids
                    ),
                }
            )
            await self._dispatch_batch([retry])

        elif action.type is ActionType.ADD_STEP:
            extra = action.payload.get("step")
            if isinstance(extra, ProposedStep):
                await self._dispatch_batch([extra])

        # CONTINUE / REPLAN / BRANCH → fall through; next plan() sees updated history.

    async def _park_escalation(self, step: ProposedStep, record: Record, action: Action) -> None:
        """Park the Campaign until a human resolves the escalation."""
        esc = Escalation(
            campaign_id=self.campaign.id,
            record_id=record.id,
            reason=action.reason,
            context={
                "operation": record.operation,
                "failure_mode": record.failure_mode,
                "gate_result": record.gate_result,
                "outputs": record.outputs,
                **action.payload,
            },
        )
        event: asyncio.Event = asyncio.Event()
        self._escalations[esc.id] = (event, None)

        self.lab.events.publish(
            Event(
                kind="campaign.escalation_required",
                payload={
                    "campaign_id": self.campaign.id,
                    "escalation_id": esc.id,
                    "record_id": record.id,
                    "reason": action.reason,
                },
            )
        )

        # Persist the escalation as a Record so it's in the audit trail.
        esc_record = record.model_copy(
            update={
                "id": esc.id,
                "record_status": "paused",
                "decision": {"escalation_reason": action.reason, "escalation_id": esc.id},
                "tags": ["escalation"],
            }
        )
        with suppress(Exception):
            await self.lab.ledger.append(esc_record)

        # Block until resolved.
        await event.wait()

        _, resolution = self._escalations[esc.id]
        if resolution is None:
            return

        # Persist the resolution.
        await self.lab.annotate(
            Annotation(
                target_record_id=record.id,
                kind="claim",
                body={
                    "escalation_resolved": True,
                    "action": resolution.action,
                    "reason": resolution.reason,
                    "resolved_by": resolution.resolved_by,
                },
                author=resolution.resolved_by,
            )
        )

        self.lab.events.publish(
            Event(
                kind="campaign.escalation_resolved",
                payload={
                    "campaign_id": self.campaign.id,
                    "escalation_id": esc.id,
                    "action": resolution.action,
                },
            )
        )

        # Apply the resolution.
        if resolution.action == "stop":
            self._stopped = ("stopped", resolution.reason)

        elif resolution.action == "retry":
            inputs = {**step.inputs, **resolution.retry_inputs}
            retry = step.model_copy(
                update={
                    "id": f"prop-{uuid4().hex[:12]}",
                    "inputs": inputs,
                    "decision": {
                        **step.decision,
                        "retry_of": record.id,
                        "escalation_resolution": resolution.reason,
                    },
                }
            )
            await self._dispatch_batch([retry])

        elif resolution.action == "add_step" and resolution.extra_step is not None:
            await self._dispatch_batch([resolution.extra_step])

        # "continue" → fall through to next plan() cycle.

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _is_done(self) -> bool:
        if self._accepted is not None or self._stopped is not None:
            return True
        if self.campaign.budget is not None and self._steps_run >= self.campaign.budget:
            self._stopped = ("budget_exhausted", f"reached budget of {self.campaign.budget}")
            return True
        return False

    def _remaining_budget(self) -> int | None:
        if self.campaign.budget is None:
            return None
        return max(0, self.campaign.budget - self._steps_run)

    def _status_text(self) -> str:
        if self._accepted is not None:
            return "accepted"
        if self._stopped is not None:
            return self._stopped[0]
        return "running"

    def _summary(self) -> CampaignSummary:
        records = list(self.lab.ledger.iter_records(campaign_id=self.campaign.id))
        best = self._best_from_history(records)
        if self._accepted is not None:
            return CampaignSummary(
                campaign_id=self.campaign.id,
                status="accepted",
                reason="acceptance criteria satisfied",
                steps_run=self._steps_run,
                accepted_record_id=self._accepted.id,
                best_record_id=self._accepted.id,
                best_outputs=self._accepted.outputs,
                records=records,
            )
        status, reason = self._stopped or ("budget_exhausted", "")
        return CampaignSummary(
            campaign_id=self.campaign.id,
            status=status,
            reason=reason,
            steps_run=self._steps_run,
            accepted_record_id=None,
            best_record_id=best.id if best else None,
            best_outputs=best.outputs if best else None,
            records=records,
        )

    def _best_from_history(self, records: list[Record]) -> Record | None:
        obj = self.campaign.objective
        completed = [r for r in records if r.record_status == "completed" and obj.key in r.outputs]
        if not completed:
            return None
        try:
            if obj.direction == "maximise":
                return max(completed, key=lambda r: float(r.outputs[obj.key]))
            return min(completed, key=lambda r: float(r.outputs[obj.key]))
        except (TypeError, ValueError):
            return None


def _find_workflow_steps(workflow: WorkflowTemplate, operation: str) -> list[str]:
    """Return step_ids in the workflow that correspond to the given operation."""
    return [step.step_id for step in workflow.steps if step.operation == operation]


def _find_workflow_result(
    result: WorkflowResult,
    step_ids: Sequence[str],
) -> StepResult | None:
    """Return the final StepResult for one of the planner-targeted workflow steps."""
    wanted = set(step_ids)
    for step in reversed(result.steps):
        if step.step_id in wanted:
            return step
    return None


__all__ = ["Campaign", "CampaignRunner", "CampaignSummary"]
