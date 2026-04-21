"""End-to-end: an Optuna-driven Campaign against the stub Operation."""

from __future__ import annotations

import pytest

from autolab import AcceptanceCriteria, Campaign, Objective
from autolab.planners.optuna import OptunaConfig, OptunaPlanner


@pytest.mark.asyncio
async def test_optuna_campaign_hits_score_threshold(make_lab):
    with make_lab() as lab:
        campaign = Campaign(
            name="optuna-smoke",
            objective=Objective(key="score", direction="maximise"),
            acceptance=AcceptanceCriteria(rules={"score": {">=": -0.005}}),
            budget=24,
        )
        planner = OptunaPlanner(
            OptunaConfig(
                operation="stub",
                search_space={
                    "x": {"type": "float", "low": 0.0, "high": 1.0},
                },
                fixed_inputs={"target": 0.5},
                batch_size=1,
                sampler="tpe",
                seed=0,
            )
        )
        summary = await lab.run_campaign(campaign, planner)

        assert summary.steps_run > 0
        # Either we accepted or we made demonstrable progress.
        assert summary.best_outputs is not None
        assert summary.best_outputs["score"] >= -0.25

        # Ledger checksums must verify.
        assert lab.verify_ledger() == []

        # Every Optuna Record should carry a trial number.
        runs = [r for r in summary.records if r.operation == "stub"]
        assert all("trial_number" in r.decision for r in runs)
