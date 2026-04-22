"""Unit tests for WorkflowChainOptimizer (the add_demo Optuna planner).

Tests the plan/react cycle without running a real Campaign:
  - plan() proposes add_two steps with Optuna-sampled x
  - react() after add_two → ADD_STEP for add_three
  - react() after add_three → CONTINUE
  - plan() reads add_three.result into Optuna (tell)
  - budget exhaustion stops proposals
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autolab.models import ActionType, Objective, ProposedStep, Record
from autolab.planners.base import DecisionContext, PlanContext

from examples.add_demo.planner import WorkflowChainOptimizer


def _make_context(history=None, remaining_budget=20):
    return PlanContext(
        campaign_id="camp-test",
        objective=Objective(key="result", direction="maximise"),
        history=history or [],
        resources=[],
        acceptance=None,
        remaining_budget=remaining_budget,
        metadata={},
    )


def _make_record(operation, status, outputs=None, decision=None):
    return Record(
        lab_id="lab-test",
        session_id="sess-test",
        campaign_id="camp-test",
        operation=operation,
        record_status=status,
        inputs={},
        outputs=outputs or {},
        decision=decision or {},
        module="test.v1",
    )


def _make_decision_ctx(record, remaining_budget=10):
    from autolab.acceptance import GateVerdict
    return DecisionContext(
        campaign_id="camp-test",
        record=record,
        gate=GateVerdict(result="pass", reason="no criteria"),
        history=[record],
        allowed_actions=list(ActionType),
        remaining_budget=remaining_budget,
    )


# ---------------------------------------------------------------------------
# plan()
# ---------------------------------------------------------------------------

class TestWorkflowChainOptimizerPlan:
    def test_plan_proposes_add_two(self):
        planner = WorkflowChainOptimizer(x_low=0.0, x_high=10.0)
        proposals = planner.plan(_make_context())
        assert len(proposals) == 1
        assert proposals[0].operation == "add_two"
        assert "x" in proposals[0].inputs
        assert 0.0 <= proposals[0].inputs["x"] <= 10.0

    def test_plan_x_stays_in_range(self):
        planner = WorkflowChainOptimizer(x_low=2.0, x_high=4.0)
        ctx = _make_context()
        for _ in range(5):
            props = planner.plan(ctx)
            if props:
                assert 2.0 <= props[0].inputs["x"] <= 4.0

    def test_plan_includes_trial_number(self):
        planner = WorkflowChainOptimizer()
        proposals = planner.plan(_make_context())
        assert isinstance(proposals[0].decision.get("trial_number"), int)

    def test_plan_stops_when_budget_is_one(self):
        # 1 op left is not enough for a 2-step trial
        planner = WorkflowChainOptimizer()
        proposals = planner.plan(_make_context(remaining_budget=1))
        assert proposals == []

    def test_plan_stops_at_zero_budget(self):
        planner = WorkflowChainOptimizer()
        proposals = planner.plan(_make_context(remaining_budget=0))
        assert proposals == []

    def test_plan_accepts_two_remaining(self):
        planner = WorkflowChainOptimizer()
        proposals = planner.plan(_make_context(remaining_budget=2))
        assert len(proposals) == 1  # exactly one trial fits


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------

class TestWorkflowChainOptimizerReact:
    def test_react_after_add_two_returns_add_step(self):
        planner = WorkflowChainOptimizer()
        planner.plan(_make_context())  # register trial 0 in _pending

        rec = _make_record(
            "add_two", "completed",
            outputs={"result": 7.0},
            decision={"planner": "add_demo_optuna", "trial_number": 0},
        )
        action = planner.react(_make_decision_ctx(rec))
        assert action.type is ActionType.ADD_STEP
        step = action.payload["step"]
        assert isinstance(step, ProposedStep)
        assert step.operation == "add_three"
        assert step.inputs["x"] == 7.0

    @pytest.mark.parametrize("result_value", [0.0, 5.0, 9.5, 12.0])
    def test_react_chains_exact_result(self, result_value):
        """add_three must receive precisely what add_two returned."""
        planner = WorkflowChainOptimizer()
        planner.plan(_make_context())
        rec = _make_record("add_two", "completed",
                           outputs={"result": result_value},
                           decision={"trial_number": 0})
        action = planner.react(_make_decision_ctx(rec))
        assert action.payload["step"].inputs["x"] == result_value

    def test_react_after_add_three_returns_continue(self):
        planner = WorkflowChainOptimizer()
        planner.plan(_make_context())
        rec = _make_record("add_three", "completed",
                           outputs={"result": 10.0},
                           decision={"trial_number": 0})
        action = planner.react(_make_decision_ctx(rec))
        assert action.type is ActionType.CONTINUE

    def test_react_after_failed_add_two_skips_add_three(self):
        planner = WorkflowChainOptimizer()
        planner.plan(_make_context())
        rec = _make_record("add_two", "failed", decision={"trial_number": 0})
        action = planner.react(_make_decision_ctx(rec))
        assert action.type is ActionType.CONTINUE

    def test_add_three_trial_number_preserved(self):
        """add_three step inherits the trial_number from add_two."""
        planner = WorkflowChainOptimizer()
        props = planner.plan(_make_context())
        tn = props[0].decision["trial_number"]

        rec = _make_record("add_two", "completed",
                           outputs={"result": 5.0},
                           decision={"trial_number": tn})
        action = planner.react(_make_decision_ctx(rec))
        assert action.payload["step"].decision["trial_number"] == tn


# ---------------------------------------------------------------------------
# Optuna tell() integration
# ---------------------------------------------------------------------------

class TestWorkflowChainOptimizerTell:
    def test_completed_add_three_told_to_optuna(self):
        planner = WorkflowChainOptimizer()
        proposals = planner.plan(_make_context())
        tn = proposals[0].decision["trial_number"]

        rec = _make_record("add_three", "completed",
                           outputs={"result": 10.0},
                           decision={"planner": "add_demo_optuna", "trial_number": tn})
        planner.plan(_make_context(history=[rec]))
        assert tn in planner._told

    def test_told_trials_not_double_counted(self):
        planner = WorkflowChainOptimizer()
        props = planner.plan(_make_context())
        tn = props[0].decision["trial_number"]

        rec = _make_record("add_three", "completed",
                           outputs={"result": 10.0},
                           decision={"trial_number": tn})
        planner.plan(_make_context(history=[rec]))
        count = len(planner._told)
        planner.plan(_make_context(history=[rec, rec]))  # same record twice
        assert len(planner._told) == count  # no change

    def test_add_two_record_not_told(self):
        """Only add_three records feed Optuna's tell()."""
        planner = WorkflowChainOptimizer()
        props = planner.plan(_make_context())
        tn = props[0].decision["trial_number"]

        # Only an add_two record — should NOT be told.
        rec = _make_record("add_two", "completed",
                           outputs={"result": 7.0},
                           decision={"trial_number": tn})
        planner.plan(_make_context(history=[rec]))
        assert tn not in planner._told


# ---------------------------------------------------------------------------
# Bootstrap integration (uses pytest tmp_path to avoid Windows lock issues)
# ---------------------------------------------------------------------------

class TestBootstrapRegisters:
    def test_bootstrap_registers_planner(self, tmp_path):
        """Bootstrap must register 'add_demo_optuna' in the global registry."""
        from autolab.lab import Lab
        from autolab.planners.registry import list_planners
        from examples.add_demo.bootstrap import bootstrap

        lab = Lab(root=tmp_path / "lab")
        bootstrap(lab)
        assert "add_demo_optuna" in list_planners()

    def test_bootstrap_registers_resource(self, tmp_path):
        from autolab.lab import Lab
        from examples.add_demo.bootstrap import bootstrap

        lab = Lab(root=tmp_path / "lab")
        bootstrap(lab)
        assert any(r.name == "wsl-local" for r in lab.resources.list())

    def test_bootstrap_registers_capabilities(self, tmp_path):
        from autolab.lab import Lab
        from examples.add_demo.bootstrap import bootstrap

        lab = Lab(root=tmp_path / "lab")
        bootstrap(lab)
        assert lab.tools.has("add_two")
        assert lab.tools.has("add_three")

    def test_bootstrap_registers_workflow(self, tmp_path):
        from autolab.lab import Lab
        from examples.add_demo.bootstrap import bootstrap

        lab = Lab(root=tmp_path / "lab")
        bootstrap(lab)
        assert "add_two_then_three" in lab._workflows
        wf = lab._workflows["add_two_then_three"]
        step_ids = [s.step_id for s in wf.steps]
        assert "add_two" in step_ids
        assert "add_three" in step_ids

    def test_bootstrap_workflow_has_input_mapping(self, tmp_path):
        """add_three step must wire add_two.result → x."""
        from autolab.lab import Lab
        from examples.add_demo.bootstrap import bootstrap

        lab = Lab(root=tmp_path / "lab")
        bootstrap(lab)
        wf = lab._workflows["add_two_then_three"]
        add_three = next(s for s in wf.steps if s.step_id == "add_three")
        assert add_three.input_mappings.get("x") == "add_two.result"

    def test_bootstrap_idempotent(self, tmp_path):
        """Calling bootstrap twice must not raise or duplicate registrations."""
        from autolab.lab import Lab
        from examples.add_demo.bootstrap import bootstrap

        lab = Lab(root=tmp_path / "lab")
        bootstrap(lab)
        bootstrap(lab)  # second call must be safe
        assert len([r for r in lab.resources.list() if r.name == "wsl-local"]) == 1
