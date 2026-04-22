"""Tests for the failure taxonomy: FailureMode + HeuristicPolicyProvider."""

from __future__ import annotations

from typing import Any

import pytest

from autolab import (
    AcceptanceCriteria,
    ActionType,
    Lab,
    OperationContext,
    OperationResult,
    Resource,
)
from autolab.acceptance import GateVerdict
from autolab.models import Record
from autolab.operations.base import Operation
from autolab.planners.base import DecisionContext, HeuristicPolicyProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(
    record: Record,
    *,
    gate_result: str = "fail",
    allowed: tuple = (
        ActionType.RETRY_STEP,
        ActionType.ESCALATE,
        ActionType.CONTINUE,
        ActionType.ACCEPT,
        ActionType.REPLAN,
    ),
    history: list[Record] | None = None,
) -> DecisionContext:
    return DecisionContext(
        campaign_id="camp-x",
        record=record,
        gate=GateVerdict(result=gate_result, reason="test"),
        history=history or [record],
        allowed_actions=allowed,
    )


def _rec(**overrides) -> Record:
    base: dict[str, Any] = dict(
        lab_id="lab-test",
        session_id="ses-test",
        operation="stub",
        record_status="failed",
    )
    base.update(overrides)
    return Record(**base)


# ---------------------------------------------------------------------------
# HeuristicPolicyProvider decision tree
# ---------------------------------------------------------------------------


class TestHeuristicPolicyProvider:
    policy = HeuristicPolicyProvider(max_retries=1)

    def test_equipment_failure_retries_first_time(self):
        rec = _rec(failure_mode="equipment_failure")
        action = self.policy.decide(_ctx(rec, history=[]))
        assert action.type is ActionType.RETRY_STEP
        assert "equipment_failure" in action.reason

    def test_equipment_failure_stops_retrying_after_max(self):
        # Two prior equipment failures — max_retries=1 exhausted.
        prior = _rec(failure_mode="equipment_failure")
        rec = _rec(failure_mode="equipment_failure")
        action = self.policy.decide(_ctx(rec, history=[prior, prior]))
        # Falls through to continue (no accept/replan gate involved).
        assert action.type in (ActionType.CONTINUE, ActionType.REPLAN)

    def test_measurement_rejection_retries(self):
        rec = _rec(failure_mode="measurement_rejection")
        action = self.policy.decide(_ctx(rec, history=[]))
        assert action.type is ActionType.RETRY_STEP
        assert "measurement_rejection" in action.reason

    def test_process_deviation_escalates(self):
        rec = _rec(failure_mode="process_deviation")
        action = self.policy.decide(_ctx(rec))
        assert action.type is ActionType.ESCALATE
        assert "process_deviation" in action.reason

    def test_synthesis_deviation_continues_not_retries(self):
        # Operation self-reported the product differs from target — keep exploring.
        rec = _rec(record_status="completed", failure_mode="synthesis_deviation")
        action = self.policy.decide(_ctx(rec, gate_result="fail", history=[rec]))
        assert action.type is ActionType.CONTINUE
        assert "synthesis_deviation" in action.reason

    def test_gate_pass_accepts(self):
        rec = _rec(record_status="completed", failure_mode=None)
        action = self.policy.decide(_ctx(rec, gate_result="pass"))
        assert action.type is ActionType.ACCEPT

    def test_gate_fail_replans(self):
        rec = _rec(record_status="completed", failure_mode=None)
        action = self.policy.decide(_ctx(rec, gate_result="fail"))
        assert action.type is ActionType.REPLAN


# ---------------------------------------------------------------------------
# Orchestrator stamps failure_mode on Records
# ---------------------------------------------------------------------------


class _EquipmentFailureOp(Operation):
    capability = "raise_op"
    resource_kind = "computer"
    module = "raise_op.v1"

    async def run(self, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
        raise RuntimeError("simulated equipment crash")


class _ProcessDeviationOp(Operation):
    capability = "process_deviation_op"
    resource_kind = "computer"
    module = "proc_dev.v1"

    async def run(self, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
        return OperationResult(
            status="failed",
            error="temperature controller lost setpoint",
            failure_mode="process_deviation",
        )


class _OffTargetOp(Operation):
    capability = "off_target_op"
    resource_kind = "computer"
    module = "off_target.v1"

    async def run(self, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
        return OperationResult(status="completed", outputs={"phase": "Sm2Co17"})


_RAISE_DECL = {
    "name": "raise_op",
    "capability": "raise_op",
    "version": "0.1.0",
    "module": "raise_op.v1",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.unit.test_failure_taxonomy:_EquipmentFailureOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}
_PROC_DEV_DECL = {
    "name": "process_deviation_op",
    "capability": "process_deviation_op",
    "version": "0.1.0",
    "module": "proc_dev.v1",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.unit.test_failure_taxonomy:_ProcessDeviationOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}
_OFF_TARGET_DECL = {
    "name": "off_target_op",
    "capability": "off_target_op",
    "version": "0.1.0",
    "module": "off_target.v1",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.unit.test_failure_taxonomy:_OffTargetOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}


@pytest.mark.asyncio
async def test_orchestrator_stamps_equipment_failure(tmp_path):
    with Lab(tmp_path, lab_id="lab-test") as lab:
        lab.register_resource(Resource(name="pc", kind="computer"))
        lab.register_tool_dict(_RAISE_DECL)
        from autolab.models import ProposedStep
        from autolab.orchestrator import CampaignRun

        session = lab.new_session()
        run = CampaignRun(lab_id="lab-test", campaign_id="camp-x", session=session)
        step = ProposedStep(operation="raise_op", inputs={})
        rec, gate = await lab.orchestrator.run_step(step, run)

        assert rec.record_status == "failed"
        assert rec.failure_mode == "equipment_failure"
        assert gate.result == "fail"


@pytest.mark.asyncio
async def test_orchestrator_stamps_process_deviation(tmp_path):
    with Lab(tmp_path, lab_id="lab-test") as lab:
        lab.register_resource(Resource(name="pc", kind="computer"))
        lab.register_tool_dict(_PROC_DEV_DECL)
        from autolab.models import ProposedStep
        from autolab.orchestrator import CampaignRun

        session = lab.new_session()
        run = CampaignRun(lab_id="lab-test", campaign_id="camp-x", session=session)
        step = ProposedStep(operation="process_deviation_op", inputs={})
        rec, _ = await lab.orchestrator.run_step(step, run)

        assert rec.record_status == "failed"
        assert rec.failure_mode == "process_deviation"


@pytest.mark.asyncio
async def test_orchestrator_gate_fails_when_outputs_miss_target(tmp_path):
    """A completed Operation whose outputs miss the acceptance rules
    gets a ``fail`` gate verdict — but remains ``record_status=completed``.
    The Planner decides what to do (typically REPLAN)."""
    with Lab(tmp_path, lab_id="lab-test") as lab:
        lab.register_resource(Resource(name="pc", kind="computer"))
        lab.register_tool_dict(_OFF_TARGET_DECL)
        from autolab.models import ProposedStep
        from autolab.orchestrator import CampaignRun

        session = lab.new_session()
        run = CampaignRun(lab_id="lab-test", campaign_id="camp-x", session=session)
        criteria = AcceptanceCriteria(rules={"phase": {"==": "SmCo5"}})
        step = ProposedStep(operation="off_target_op", inputs={})
        rec, gate = await lab.orchestrator.run_step(step, run, acceptance=criteria)

        assert rec.record_status == "completed"
        assert gate.result == "fail"
