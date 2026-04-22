"""Optuna planner that chains add_two -> cube, maximising the final result.

Same react()-based chain pattern as examples/add_demo/planner.py:
  plan()  proposes add_two(x = trial.x), x in [0, 10]
  react() after add_two completes, emits ADD_STEP with cube(x = add_two.result)
  after cube completes, plan() tell()s Optuna with cube.result
"""

from __future__ import annotations

from typing import Any

import optuna

from autolab.models import Action, ActionType, ProposedStep
from autolab.planners.base import DecisionContext, PlanContext, Planner

optuna.logging.set_verbosity(optuna.logging.WARNING)


class WslAddCubeOptimizer(Planner):
    """Maximise cube(add_two(x)) = (x + 2)**3 over x in [x_low, x_high]."""

    name = "wsl_ssh_add_cube_optuna"

    def __init__(self, x_low: float = 0.0, x_high: float = 10.0) -> None:
        super().__init__(policy=None)
        self._study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
        )
        self._x_low = x_low
        self._x_high = x_high
        self._pending: dict[int, Any] = {}
        self._told: set[int] = set()

    def plan(self, context: PlanContext) -> list[ProposedStep]:
        for rec in context.history:
            tn = (rec.decision or {}).get("trial_number")
            if not isinstance(tn, int) or tn in self._told:
                continue
            if rec.operation != "cube":
                continue
            trial = self._pending.pop(tn, None)
            if trial is None:
                continue
            if rec.record_status == "completed" and "result" in (rec.outputs or {}):
                self._study.tell(trial, float(rec.outputs["result"]))
            else:
                self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
            self._told.add(tn)

        remaining = context.remaining_budget
        if remaining is not None and remaining <= 1:
            return []

        trial = self._study.ask()
        x = trial.suggest_float("x", self._x_low, self._x_high)
        self._pending[trial.number] = trial
        return [
            ProposedStep(
                operation="add_two",
                inputs={"x": x},
                decision={
                    "planner": self.name,
                    "trial_number": trial.number,
                    "x_proposed": x,
                },
            )
        ]

    def react(self, ctx: DecisionContext) -> Action:
        rec = ctx.record
        tn = (rec.decision or {}).get("trial_number")

        if rec.operation == "add_two" and rec.record_status == "completed":
            x_next = float((rec.outputs or {}).get("result", 0.0))
            return Action(
                type=ActionType.ADD_STEP,
                reason=f"chain cube after add_two (x={x_next:.3f})",
                payload={
                    "step": ProposedStep(
                        operation="cube",
                        inputs={"x": x_next},
                        decision={"planner": self.name, "trial_number": tn},
                    )
                },
            )

        if rec.operation == "add_two" and rec.record_status != "completed":
            if isinstance(tn, int) and tn in self._pending:
                trial = self._pending.pop(tn)
                self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
                self._told.add(tn)
            return Action(type=ActionType.CONTINUE, reason="add_two failed, skipping cube")

        return Action(type=ActionType.CONTINUE, reason="step complete")
