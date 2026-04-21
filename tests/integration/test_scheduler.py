"""Integration tests for CampaignScheduler — multi-campaign priority queue."""

from __future__ import annotations

from typing import Any

import pytest

from autolab import (
    Campaign,
    CampaignScheduler,
    Lab,
    Objective,
    OperationContext,
    OperationResult,
    Resource,
)
from autolab.models import ProposedStep
from autolab.operations.base import Operation
from autolab.planners.base import PlanContext, Planner


class _ScoreOp(Operation):
    """Returns score = inputs['x']."""

    capability = "score_op"
    resource_kind = "computer"
    module = "score_op.v0"

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        x = float(inputs.get("x", 0.0))
        return OperationResult(status="completed", outputs={"score": x})


_SCORE_DECL = {
    "name": "score_op",
    "capability": "score_op",
    "version": "0.1.0",
    "module": "score_op.v0",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.integration.test_scheduler:_ScoreOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {"x": {"kind": "scalar"}},
    "outputs": {"score": {"kind": "scalar"}},
}


class _FixedPlanner(Planner):
    """Returns a fixed list of steps and then stops."""

    name = "fixed"

    def __init__(self, xs: list[float]) -> None:
        super().__init__()
        self._xs = list(xs)

    def plan(self, ctx: PlanContext) -> list[ProposedStep]:
        if not self._xs:
            return []
        x = self._xs.pop(0)
        return [ProposedStep(operation="score_op", inputs={"x": x})]


def _lab(tmp_path) -> Lab:
    lab = Lab(tmp_path, lab_id="lab-sched")
    lab.register_resource(Resource(name="pc-1", kind="computer"))
    lab.register_tool_dict(_SCORE_DECL)
    return lab


@pytest.mark.asyncio
async def test_scheduler_runs_two_campaigns_to_completion(tmp_path):
    with _lab(tmp_path) as lab:
        scheduler = CampaignScheduler(lab)

        camp_a = Campaign(
            name="campaign-a",
            objective=Objective(key="score"),
            budget=3,
        )
        camp_b = Campaign(
            name="campaign-b",
            objective=Objective(key="score"),
            budget=3,
        )
        await scheduler.submit(camp_a, _FixedPlanner([0.1, 0.2, 0.3]), priority=10)
        await scheduler.submit(camp_b, _FixedPlanner([0.4, 0.5, 0.6]), priority=20)

        await scheduler.run()

        statuses = {s["name"]: s["status"] for s in scheduler.status()}
        assert statuses["campaign-a"] == "completed"
        assert statuses["campaign-b"] == "completed"


class _SlowInfinitePlanner(Planner):
    """Proposes steps indefinitely with a tiny async pause to yield the event loop."""

    name = "slow_infinite"

    def plan(self, ctx: PlanContext) -> list[ProposedStep]:
        return [ProposedStep(operation="score_op", inputs={"x": 0.1})]


@pytest.mark.asyncio
async def test_scheduler_cancel_stops_campaign(tmp_path):
    import asyncio

    with _lab(tmp_path) as lab:
        # Two resources so the campaign can start immediately.
        lab.register_resource(Resource(name="pc-2", kind="computer"))
        scheduler = CampaignScheduler(lab)

        camp = Campaign(
            name="to-cancel",
            objective=Objective(key="score"),
            budget=None,  # infinite budget — will only stop via cancel
        )
        await scheduler.submit(camp, _SlowInfinitePlanner(), priority=10)

        async def cancel_after() -> None:
            # Wait until the campaign is definitely running (at least one step).
            for _ in range(500):
                await asyncio.sleep(0.01)
                statuses = {s["name"]: s["status"] for s in scheduler.status()}
                if statuses.get("to-cancel") == "running":
                    break
            await scheduler.cancel(camp.id)

        asyncio.create_task(cancel_after())
        await scheduler.run()

        s = next(x for x in scheduler.status() if x["name"] == "to-cancel")
        assert s["status"] == "cancelled"


@pytest.mark.asyncio
async def test_scheduler_pause_and_resume(tmp_path):
    import asyncio

    with _lab(tmp_path) as lab:
        lab.register_resource(Resource(name="pc-2", kind="computer"))
        scheduler = CampaignScheduler(lab)

        camp = Campaign(name="pausable", objective=Objective(key="score"), budget=4)
        await scheduler.submit(camp, _FixedPlanner([0.1, 0.2, 0.3, 0.4]), priority=5)

        async def pause_then_resume() -> None:
            await asyncio.sleep(0.02)
            await scheduler.pause(camp.id)
            await asyncio.sleep(0.05)
            await scheduler.resume(camp.id)

        asyncio.create_task(pause_then_resume())
        await scheduler.run()

        s = next(x for x in scheduler.status() if x["name"] == "pausable")
        assert s["status"] == "completed"


@pytest.mark.asyncio
async def test_scheduler_status_sorted_by_priority(tmp_path):
    with _lab(tmp_path) as lab:
        scheduler = CampaignScheduler(lab)
        for priority, name in [(30, "low"), (10, "high"), (20, "mid")]:
            c = Campaign(name=name, objective=Objective(key="score"), budget=1)
            await scheduler.submit(c, _FixedPlanner([0.5]), priority=priority)

        await scheduler.run()
        priorities = [s["priority"] for s in scheduler.status()]
        assert priorities == sorted(priorities)
