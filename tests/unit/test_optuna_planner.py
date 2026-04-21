"""Unit tests for the Optuna-backed Planner."""

from __future__ import annotations

from datetime import UTC, datetime

from autolab import Objective, Record, Resource
from autolab.planners.base import PlanContext
from autolab.planners.optuna import OptunaConfig, OptunaPlanner


def _plan_ctx(history: list[Record], budget: int | None = 8) -> PlanContext:
    return PlanContext(
        campaign_id="camp-x",
        objective=Objective(key="score", direction="maximise"),
        history=history,
        resources=[Resource(name="pc-1", kind="computer")],
        remaining_budget=budget,
    )


def _make_record(*, trial_number: int, score: float, status: str = "completed") -> Record:
    return Record(
        lab_id="lab-test",
        session_id="ses-test",
        operation="stub",
        record_status=status,
        outputs={"score": score},
        decision={"planner": "optuna", "trial_number": trial_number},
        finalised_at=datetime.now(UTC),
    )


class TestOptunaPlanner:
    def test_first_batch_is_ask_only(self):
        planner = OptunaPlanner(
            OptunaConfig(
                operation="stub",
                search_space={
                    "x": {"type": "float", "low": 0.0, "high": 1.0},
                },
                batch_size=2,
                sampler="random",
                seed=0,
            )
        )
        proposals = planner.plan(_plan_ctx(history=[]))
        assert len(proposals) == 2
        for p in proposals:
            assert p.operation == "stub"
            assert "x" in p.inputs
            assert p.decision["planner"] == "optuna"
            assert isinstance(p.decision["trial_number"], int)

    def test_history_feeds_back_into_study(self):
        planner = OptunaPlanner(
            OptunaConfig(
                operation="stub",
                search_space={
                    "x": {"type": "float", "low": 0.0, "high": 1.0},
                },
                batch_size=1,
                sampler="random",
                seed=0,
            )
        )
        first = planner.plan(_plan_ctx(history=[]))
        trial_number = first[0].decision["trial_number"]

        history = [_make_record(trial_number=trial_number, score=0.9)]
        # Second plan() should tell() the completed trial and ask() a new one.
        second = planner.plan(_plan_ctx(history=history))
        assert second and second[0].decision["trial_number"] != trial_number
        assert trial_number in planner._told

    def test_respects_remaining_budget(self):
        planner = OptunaPlanner(
            OptunaConfig(
                operation="stub",
                search_space={
                    "x": {"type": "float", "low": 0.0, "high": 1.0},
                },
                batch_size=5,
                sampler="random",
                seed=0,
            )
        )
        proposals = planner.plan(_plan_ctx(history=[], budget=2))
        assert len(proposals) == 2

    def test_int_and_categorical_supported(self):
        planner = OptunaPlanner(
            OptunaConfig(
                operation="stub",
                search_space={
                    "n": {"type": "int", "low": 1, "high": 4},
                    "choice": {"type": "categorical", "choices": ["a", "b"]},
                },
                sampler="random",
                seed=0,
            )
        )
        proposals = planner.plan(_plan_ctx(history=[]))
        params = proposals[0].inputs
        assert isinstance(params["n"], int)
        assert params["choice"] in {"a", "b"}

    def test_callable_search_space(self):
        def sample(trial):
            a = trial.suggest_float("a", 0.0, 1.0)
            # b constrained ≤ a
            b = trial.suggest_float("b", 0.0, a if a > 0 else 1e-6)
            return {"a": a, "b": b}

        planner = OptunaPlanner(
            OptunaConfig(
                operation="stub",
                search_space=sample,
                sampler="random",
                seed=1,
            )
        )
        proposals = planner.plan(_plan_ctx(history=[]))
        inputs = proposals[0].inputs
        assert inputs["b"] <= inputs["a"] + 1e-9
