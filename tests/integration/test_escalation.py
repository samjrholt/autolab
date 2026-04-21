"""Integration tests for escalation parking and resolution."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from autolab import (
    AcceptanceCriteria,
    Action,
    ActionType,
    Campaign,
    DecisionContext,
    EscalationResolution,
    Lab,
    Objective,
    OperationContext,
    OperationResult,
    PolicyProvider,
    ProposedStep,
    Resource,
)
from autolab.operations.base import Operation
from autolab.planners.base import PlanContext, Planner

# ---------------------------------------------------------------------------
# Operations and planners
# ---------------------------------------------------------------------------


class _BadOp(Operation):
    """Fails with process_deviation to trigger escalation."""

    capability = "bad_op"
    resource_kind = "computer"
    module = "bad_op.v0"

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        return OperationResult(
            status="failed",
            error="process went wrong",
            failure_mode="process_deviation",
        )


class _GoodOp(Operation):
    """Succeeds with score=1.0."""

    capability = "good_op"
    resource_kind = "computer"
    module = "good_op.v0"

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        return OperationResult(status="completed", outputs={"score": 1.0})


_BAD_DECL = {
    "name": "bad_op",
    "capability": "bad_op",
    "version": "0.1.0",
    "module": "bad_op.v0",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.integration.test_escalation:_BadOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}
_GOOD_DECL = {
    "name": "good_op",
    "capability": "good_op",
    "version": "0.1.0",
    "module": "good_op.v0",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.integration.test_escalation:_GoodOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}


class _EscalateThenContinuePolicy(PolicyProvider):
    """Escalates the first bad_op failure, then continues after resolution."""

    def __init__(self) -> None:
        self._escalated = False

    def decide(self, ctx: DecisionContext) -> Action:
        if (
            not self._escalated
            and ctx.record.record_status == "failed"
            and ctx.failure_mode == "process_deviation"
            and ActionType.ESCALATE in set(ctx.allowed_actions)
        ):
            self._escalated = True
            return Action(type=ActionType.ESCALATE, reason="process deviation, escalate")
        return Action(type=ActionType.CONTINUE, reason="after escalation, continue")


class _OneBadThenGood(Planner):
    name = "one_bad_then_good"

    def __init__(self) -> None:
        super().__init__(policy=_EscalateThenContinuePolicy())
        self._proposals = [
            ProposedStep(operation="bad_op", inputs={}),
            ProposedStep(operation="good_op", inputs={}),
        ]

    def plan(self, ctx: PlanContext) -> list[ProposedStep]:
        if not self._proposals:
            return []
        return [self._proposals.pop(0)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalation_parks_and_resumes_on_continue(tmp_path):
    """Campaign parks on escalation, resumes with 'continue', finishes normally."""
    with Lab(tmp_path, lab_id="lab-esc") as lab:
        lab.register_resource(Resource(name="pc", kind="computer"))
        lab.register_tool_dict(_BAD_DECL)
        lab.register_tool_dict(_GOOD_DECL)

        campaign = Campaign(
            name="esc-test",
            objective=Objective(key="score"),
            acceptance=AcceptanceCriteria(rules={"score": {">=": 1.0}}),
            budget=4,
        )
        planner = _OneBadThenGood()

        escalation_event: asyncio.Event = asyncio.Event()

        async def watch_and_resolve() -> None:
            # Wait until the campaign has a pending escalation.
            for _ in range(200):
                await asyncio.sleep(0.01)
                pending = lab.pending_escalations(campaign.id)
                if pending:
                    esc = pending[0]
                    lab.resolve_escalation(
                        campaign.id,
                        esc.id,
                        EscalationResolution(
                            escalation_id=esc.id,
                            action="continue",
                            reason="operator checked, continue",
                        ),
                    )
                    escalation_event.set()
                    return

        watcher = asyncio.create_task(watch_and_resolve())
        summary = await lab.run_campaign(campaign, planner)
        await watcher

        assert escalation_event.is_set(), "escalation was never fired"
        # The good_op should have run after escalation resolved.
        ops = [r.operation for r in summary.records]
        assert "good_op" in ops


@pytest.mark.asyncio
async def test_escalation_stop_terminates_campaign(tmp_path):
    """Resolving escalation with 'stop' terminates the campaign."""
    with Lab(tmp_path, lab_id="lab-esc-stop") as lab:
        lab.register_resource(Resource(name="pc", kind="computer"))
        lab.register_tool_dict(_BAD_DECL)
        lab.register_tool_dict(_GOOD_DECL)

        campaign = Campaign(
            name="stop-on-escalation",
            objective=Objective(key="score"),
            budget=10,
        )
        planner = _OneBadThenGood()

        async def resolve_stop() -> None:
            for _ in range(200):
                await asyncio.sleep(0.01)
                pending = lab.pending_escalations(campaign.id)
                if pending:
                    esc = pending[0]
                    lab.resolve_escalation(
                        campaign.id,
                        esc.id,
                        EscalationResolution(
                            escalation_id=esc.id,
                            action="stop",
                            reason="operator decided to stop",
                        ),
                    )
                    return

        asyncio.create_task(resolve_stop())
        summary = await lab.run_campaign(campaign, planner)

        assert summary.status == "stopped"
