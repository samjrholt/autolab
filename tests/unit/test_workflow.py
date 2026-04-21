"""Tests for WorkflowTemplate, WorkflowStep, and WorkflowEngine DAG execution."""

from __future__ import annotations

from typing import Any

import pytest

from autolab import (
    Lab,
    OperationContext,
    OperationResult,
    Resource,
    WorkflowStep,
    WorkflowTemplate,
)
from autolab.operations.base import Operation
from autolab.orchestrator import CampaignRun
from autolab.workflow import _topological_sort

# ---------------------------------------------------------------------------
# Operations for DAG tests
# ---------------------------------------------------------------------------


class _EchoOp(Operation):
    """Returns its inputs as outputs — useful for tracing dependency wiring."""

    capability = "echo"
    resource_kind = "computer"
    module = "echo.v0"

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        return OperationResult(status="completed", outputs=dict(inputs))


class _FailOp(Operation):
    capability = "fail_op"
    resource_kind = "computer"
    module = "fail_op.v0"

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        raise RuntimeError("fail_op always fails")


_ECHO_DECL = {
    "name": "echo",
    "capability": "echo",
    "version": "0.1.0",
    "module": "echo.v0",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.unit.test_workflow:_EchoOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}
_FAIL_DECL = {
    "name": "fail_op",
    "capability": "fail_op",
    "version": "0.1.0",
    "module": "fail_op.v0",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.unit.test_workflow:_FailOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_linear_chain(self):
        steps = [
            WorkflowStep(step_id="a", operation="op"),
            WorkflowStep(step_id="b", operation="op", depends_on=["a"]),
            WorkflowStep(step_id="c", operation="op", depends_on=["b"]),
        ]
        batches = _topological_sort(steps)
        assert [sorted(b) for b in batches] == [["a"], ["b"], ["c"]]

    def test_parallel_branches(self):
        steps = [
            WorkflowStep(step_id="root", operation="op"),
            WorkflowStep(step_id="left", operation="op", depends_on=["root"]),
            WorkflowStep(step_id="right", operation="op", depends_on=["root"]),
            WorkflowStep(step_id="merge", operation="op", depends_on=["left", "right"]),
        ]
        batches = _topological_sort(steps)
        assert batches[0] == ["root"]
        assert sorted(batches[1]) == ["left", "right"]
        assert batches[2] == ["merge"]

    def test_cycle_raises(self):
        steps = [
            WorkflowStep(step_id="a", operation="op", depends_on=["b"]),
            WorkflowStep(step_id="b", operation="op", depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="cycle"):
            _topological_sort(steps)


# ---------------------------------------------------------------------------
# WorkflowEngine integration
# ---------------------------------------------------------------------------


def _lab(tmp_path, with_fail: bool = False) -> Lab:
    lab = Lab(tmp_path, lab_id="lab-wf")
    lab.register_resource(Resource(name="pc-1", kind="computer"))
    lab.register_tool_dict(_ECHO_DECL)
    if with_fail:
        lab.register_tool_dict(_FAIL_DECL)
    return lab


@pytest.mark.asyncio
async def test_linear_workflow_executes_all_steps(tmp_path):
    lab = _lab(tmp_path)
    template = WorkflowTemplate(
        name="linear",
        steps=[
            WorkflowStep(step_id="a", operation="echo", inputs={"x": 1}),
            WorkflowStep(step_id="b", operation="echo", depends_on=["a"], inputs={"y": 2}),
            WorkflowStep(step_id="c", operation="echo", depends_on=["b"], inputs={"z": 3}),
        ],
    )
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-wf", session=session)
    result = await lab._workflow_engine.run(template, run)

    assert result.completed
    assert [s.step_id for s in result.steps] == ["a", "b", "c"]
    assert all(s.record.record_status == "completed" for s in result.steps)
    lab.close()


@pytest.mark.asyncio
async def test_input_mappings_wire_upstream_outputs(tmp_path):
    """Step b should receive step a's output value via input_mappings."""
    lab = _lab(tmp_path)
    template = WorkflowTemplate(
        name="wired",
        steps=[
            WorkflowStep(step_id="a", operation="echo", inputs={"value": 42}),
            WorkflowStep(
                step_id="b",
                operation="echo",
                depends_on=["a"],
                input_mappings={"inherited": "a.value"},
            ),
        ],
    )
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-wire", session=session)
    result = await lab._workflow_engine.run(template, run)

    b_rec = result.get("b").record
    assert b_rec.outputs["inherited"] == 42
    lab.close()


@pytest.mark.asyncio
async def test_failed_step_skips_dependants(tmp_path):
    lab = _lab(tmp_path, with_fail=True)
    template = WorkflowTemplate(
        name="fail-chain",
        steps=[
            WorkflowStep(step_id="ok", operation="echo", inputs={"x": 1}),
            WorkflowStep(step_id="fail", operation="fail_op", depends_on=["ok"]),
            WorkflowStep(step_id="skip", operation="echo", depends_on=["fail"], inputs={"x": 2}),
        ],
    )
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-fail", session=session)
    result = await lab._workflow_engine.run(template, run)

    assert not result.completed
    assert "skip" in result.skipped_step_ids
    fail_sr = result.get("fail")
    assert fail_sr.record.record_status == "failed"
    lab.close()


@pytest.mark.asyncio
async def test_parallel_branches_run_concurrently(tmp_path):
    """Both left and right branches should appear in results; no ordering assumed."""
    lab = _lab(tmp_path)
    lab.register_resource(Resource(name="pc-2", kind="computer"))  # 2nd resource for parallelism
    template = WorkflowTemplate(
        name="parallel",
        steps=[
            WorkflowStep(step_id="root", operation="echo", inputs={"x": 0}),
            WorkflowStep(step_id="left", operation="echo", depends_on=["root"], inputs={"x": 1}),
            WorkflowStep(step_id="right", operation="echo", depends_on=["root"], inputs={"x": 2}),
            WorkflowStep(step_id="merge", operation="echo", depends_on=["left", "right"]),
        ],
    )
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-par", session=session)
    result = await lab._workflow_engine.run(template, run)

    step_ids = {s.step_id for s in result.steps}
    assert step_ids == {"root", "left", "right", "merge"}
    assert result.completed
    lab.close()


@pytest.mark.asyncio
async def test_register_and_run_workflow_via_lab(tmp_path):
    lab = _lab(tmp_path)
    template = WorkflowTemplate(
        name="simple",
        steps=[WorkflowStep(step_id="a", operation="echo", inputs={"n": 7})],
    )
    lab.register_workflow(template)
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-reg", session=session)
    result = await lab.run_workflow("simple", run)
    assert result.completed
    assert result.records[0].outputs["n"] == 7
    lab.close()
