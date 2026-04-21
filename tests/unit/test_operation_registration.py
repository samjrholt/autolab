"""Tests for Python-first Operation class registration."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from autolab import Lab, OperationContext, OperationResult, Resource
from autolab.operations.base import Operation
from autolab.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Sample Operation classes for testing
# ---------------------------------------------------------------------------


class MinimalOp(Operation):
    """Operation with only required class attributes."""

    capability = "minimal"
    resource_kind = "computer"
    module = "minimal.v0"

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        return OperationResult(status="completed", outputs={"done": True})


class TypedOp(Operation):
    """Operation with Inputs/Outputs models and typical_duration."""

    capability = "typed_op"
    resource_kind = "computer"
    module = "typed_op.v1"
    produces_sample = True
    typical_duration = 300  # seconds

    class Inputs(BaseModel):
        x: float = Field(..., ge=0.0, le=1.0, description="Input x")
        n: int = Field(default=1, description="Repetitions")

    class Outputs(BaseModel):
        score: float
        label: str

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        return OperationResult(
            status="completed",
            outputs={"score": float(inputs["x"]) ** 2, "label": "ok"},
        )


# ---------------------------------------------------------------------------
# Unit tests for ToolRegistry.register_class
# ---------------------------------------------------------------------------


class TestRegisterClass:
    def test_declares_capability_from_class(self):
        registry = ToolRegistry()
        decl = registry.register_class(MinimalOp)
        assert decl.capability == "minimal"
        assert decl.resource_kind == "computer"
        assert decl.module == "minimal.v0"

    def test_declaration_hash_is_deterministic(self):
        r1, r2 = ToolRegistry(), ToolRegistry()
        h1 = r1.register_class(MinimalOp).declaration_hash
        h2 = r2.register_class(MinimalOp).declaration_hash
        assert h1 == h2

    def test_typical_duration_extracted(self):
        registry = ToolRegistry()
        decl = registry.register_class(TypedOp)
        assert decl.typical_duration_s == 300

    def test_inputs_schema_extracted(self):
        registry = ToolRegistry()
        decl = registry.register_class(TypedOp)
        assert "x" in decl.inputs
        assert "n" in decl.inputs

    def test_double_register_raises(self):
        registry = ToolRegistry()
        registry.register_class(MinimalOp)
        with pytest.raises(ValueError, match="already registered"):
            registry.register_class(MinimalOp)

    def test_adapter_resolution_returns_class_directly(self):
        registry = ToolRegistry()
        registry.register_class(MinimalOp)
        cls = registry.adapter("minimal")
        assert cls is MinimalOp


# ---------------------------------------------------------------------------
# Integration: Lab.register_operation + run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_operation_and_run_campaign(tmp_path):
    with Lab(tmp_path, lab_id="lab-test") as lab:
        lab.register_resource(Resource(name="pc", kind="computer"))
        decl = lab.register_operation(TypedOp)

        assert decl.declaration_hash
        assert decl.typical_duration_s == 300

        from autolab import AcceptanceCriteria, Campaign, Objective
        from autolab.planners.bo import BOConfig, BOPlanner

        campaign = Campaign(
            name="typed-op-test",
            objective=Objective(key="score", direction="maximise"),
            acceptance=AcceptanceCriteria(rules={"score": {">=": 0.8}}),
            budget=10,
        )
        planner = BOPlanner(
            BOConfig(
                operation="typed_op",
                parameter_space={"x": {"type": "float", "low": 0.0, "high": 1.0}},
                initial_random=3,
                seed=1,
            )
        )
        summary = await lab.run_campaign(campaign, planner)
        assert summary.steps_run > 0
        # Declaration hash stamped on every record.
        runs = [r for r in summary.records if r.operation == "typed_op"]
        assert all(r.tool_declaration_hash == decl.declaration_hash for r in runs)
