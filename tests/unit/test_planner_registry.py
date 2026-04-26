"""Unit tests for the planner registry."""

from __future__ import annotations

import pytest

from autolab.agents.claude import ClaudePlanner, ClaudeResponse
from autolab.models import Objective
from autolab.planners import list_planners, register_planner, unregister_planner
from autolab.planners.base import PlanContext, Planner
from autolab.planners.bo import BOPlanner
from autolab.planners.optuna import OptunaPlanner
from autolab.planners.registry import build


class _FakeClaudeTransport:
    def __init__(self, text: str) -> None:
        self.text = text
        self.user_prompt = ""

    def call(
        self,
        system: str,
        user: str,
        *,
        images: list[bytes] | None = None,
    ) -> ClaudeResponse:
        self.user_prompt = user
        return ClaudeResponse(
            text=self.text,
            model="fake-claude",
            prompt_hash="hash",
            offline=False,
        )


class TestBuiltinRegistry:
    def test_bo_and_optuna_registered(self):
        names = list_planners()
        assert "bo" in names
        assert "optuna" in names

    def test_build_bo_from_config(self):
        # "bo" is now an alias for Optuna (GP sampler) — we removed the
        # hand-rolled GP in favour of Optuna's built-in samplers.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # suppress ExperimentalWarning for GPSampler
            planner = build(
                "bo",
                {
                    "operation": "stub",
                    "search_space": {
                        "x": {"type": "float", "low": 0.0, "high": 1.0},
                    },
                    "seed": 1,
                },
            )
        assert isinstance(planner, OptunaPlanner)
        assert planner.name == "optuna"  # wrapped planner keeps its own name

    def test_build_optuna_from_config(self):
        planner = build(
            "optuna",
            {
                "operation": "stub",
                "search_space": {
                    "x": {"type": "float", "low": 0.0, "high": 1.0},
                },
                "sampler": "random",
                "seed": 0,
            },
        )
        assert isinstance(planner, OptunaPlanner)
        assert planner.name == "optuna"

    def test_unknown_name_raises_keyerror(self):
        with pytest.raises(KeyError):
            build("not_a_real_planner", {})

    def test_claude_planner_uses_configured_search_space(self):
        transport = _FakeClaudeTransport(
            """
            {
              "proposals": [
                {
                  "operation": "mammos.sensor_material_at_T",
                  "inputs": {"sx_nm": 90, "sy_nm": 30},
                  "decision": "try a wider x axis"
                }
              ]
            }
            """
        )
        planner = ClaudePlanner(
            transport=transport,
            operation="mammos.sensor_shape_fom",
            search_space={
                "sx_nm": {"type": "float", "low": 5.0, "high": 70.0},
                "sy_nm": {"type": "float", "low": 5.0, "high": 70.0},
            },
        )

        proposals = planner.plan(
            PlanContext(
                campaign_id="camp-test",
                objective=Objective(key="Hmax_A_per_m", direction="maximise"),
                history=[],
                resources=[],
                remaining_budget=12,
            )
        )

        assert "Search space bounds" in transport.user_prompt
        assert proposals[0].operation == "mammos.sensor_shape_fom"
        assert proposals[0].inputs == {"sx_nm": 70.0, "sy_nm": 30.0}
        assert proposals[0].decision["method"] == "llm"


class TestCustomRegistration:
    def test_register_and_build_custom(self):
        class _DummyPlanner(Planner):
            name = "dummy"

            def plan(self, context):  # type: ignore[override]
                return []

        try:
            register_planner("dummy", lambda cfg: _DummyPlanner())
            planner = build("dummy", {})
            assert isinstance(planner, _DummyPlanner)
        finally:
            unregister_planner("dummy")

    def test_double_register_without_overwrite_raises(self):
        try:
            register_planner("dupe", lambda cfg: BOPlanner.__new__(BOPlanner))
            with pytest.raises(ValueError):
                register_planner("dupe", lambda cfg: BOPlanner.__new__(BOPlanner))
        finally:
            unregister_planner("dupe")
