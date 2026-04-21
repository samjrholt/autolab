"""End-to-end smoke test: a synthetic Operation + BO Planner against a real Lab.

The test deliberately avoids the magnetism example so it has zero
dependency on ubermag. It uses the same framework surface (Lab,
ToolRegistry, Orchestrator, BOPlanner) but with a closed-form objective.
"""

from __future__ import annotations

from typing import Any

import pytest

from autolab import (
    AcceptanceCriteria,
    Campaign,
    Feature,
    FeatureView,
    Lab,
    Objective,
    OperationContext,
    OperationResult,
    Resource,
)
from autolab.operations.base import Operation
from autolab.planners.bo import BOConfig, BOPlanner


class _QuadraticOp(Operation):
    """Maximises a 2-D quadratic with a known optimum at (x,y)=(0.4, 0.6)."""

    capability = "quadratic"
    resource_kind = "computer"
    requires = {"cores_gte": 1}
    produces_sample = True
    module = "quadratic.v1"

    async def run(self, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
        x = float(inputs["x"])
        y = float(inputs["y"])
        score = 1.0 - (x - 0.4) ** 2 - (y - 0.6) ** 2
        outputs = {"x": x, "y": y, "score": score}
        return OperationResult(
            status="completed",
            outputs=outputs,
            features=FeatureView(fields={"score": Feature(kind="scalar", value=score)}),
        )


_TOOL_DECL = {
    "name": "quadratic",
    "capability": "quadratic",
    "version": "0.1.0",
    "module": "quadratic.v1",
    "resource": "computer",
    "requires": {"cores_gte": 1},
    "adapter": "tests.integration.test_campaign_end_to_end:_QuadraticOp",
    "produces_sample": True,
    "destructive": False,
    "inputs": {
        "x": {"kind": "scalar"},
        "y": {"kind": "scalar"},
    },
    "outputs": {"score": {"kind": "scalar"}},
}


@pytest.mark.asyncio
async def test_bo_campaign_finds_quadratic_optimum(tmp_path):
    with Lab(tmp_path / "lab", lab_id="lab-test") as lab:
        lab.register_resource(
            Resource(name="this-machine", kind="computer", capabilities={"cores_gte": 4})
        )
        decl = lab.register_tool_dict(_TOOL_DECL)
        assert decl.declaration_hash

        campaign = Campaign(
            name="bo-quadratic",
            objective=Objective(key="score", direction="maximise"),
            acceptance=AcceptanceCriteria(rules={"score": {">=": 0.95}}),
            budget=24,
            parallelism=1,
        )
        planner = BOPlanner(
            BOConfig(
                operation="quadratic",
                parameter_space={
                    "x": {"type": "float", "low": 0.0, "high": 1.0},
                    "y": {"type": "float", "low": 0.0, "high": 1.0},
                },
                initial_random=4,
                candidate_pool=512,
                seed=7,
            )
        )

        summary = await lab.run_campaign(campaign, planner)

        assert summary.steps_run > 0
        assert summary.records, "ledger should hold at least one record"
        if summary.status == "accepted":
            assert summary.best_outputs is not None
            assert summary.best_outputs["score"] >= 0.95
        else:
            assert summary.best_outputs is None or summary.best_outputs["score"] > 0.5

        bad = lab.verify_ledger()
        assert bad == [], f"ledger checksum verification failed: {bad}"

        runs = [r for r in summary.records if r.operation == "quadratic"]
        assert runs and all(r.tool_declaration_hash == decl.declaration_hash for r in runs)
