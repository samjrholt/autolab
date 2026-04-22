"""WorkflowChainOptimizer — Optuna-backed planner that chains add_two → add_three.

The key mechanism: after add_two completes, react() returns ADD_STEP to immediately
run add_three with add_two's result as its input. Optuna then reads add_three's
output (the final result) to decide the next x to try.

This is the correct pattern for "optimize over a 2-step workflow":
  plan()   → proposes add_two(x=trial.x)
  react()  → after add_two, adds add_three(x=add_two.result)
           → after add_three, continues (plan() will propose next trial)
  Optuna   → reads add_three.result for tell()
"""
from __future__ import annotations

from typing import Any
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

from autolab.models import Action, ActionType, ProposedStep
from autolab.planners.base import DecisionContext, PlanContext, Planner


class WorkflowChainOptimizer(Planner):
    """Optuna-backed optimizer that chains add_two → add_three per trial.

    One trial = one add_two run + one add_three run.
    Optuna reads add_three.result as the objective value.
    """

    name = "add_demo_optuna"

    def __init__(self, x_low: float = 0.0, x_high: float = 10.0, budget: int = 20) -> None:
        super().__init__(policy=None)
        self._study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
        )
        self._x_low = x_low
        self._x_high = x_high
        self._pending: dict[int, Any] = {}   # trial_number → trial object
        self._told: set[int] = set()         # trial numbers already told
        self._budget = budget

    # ------------------------------------------------------------------
    # plan() — called at the start of each campaign loop tick
    # ------------------------------------------------------------------

    def plan(self, context: PlanContext) -> list[ProposedStep]:
        # Tell Optuna about any completed add_three runs since last plan().
        for rec in context.history:
            tn = (rec.decision or {}).get("trial_number")
            if not isinstance(tn, int) or tn in self._told:
                continue
            if rec.operation != "add_three":
                continue
            trial = self._pending.pop(tn, None)
            if trial is None:
                continue
            if rec.record_status == "completed" and "result" in (rec.outputs or {}):
                self._study.tell(trial, float(rec.outputs["result"]))
            else:
                self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
            self._told.add(tn)

        # Stop once budget is exhausted (counting both steps per trial).
        remaining = context.remaining_budget
        if remaining is not None and remaining <= 1:
            return []

        # Ask Optuna for the next x.
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

    # ------------------------------------------------------------------
    # react() — called after each step completes
    # ------------------------------------------------------------------

    def react(self, ctx: DecisionContext) -> Action:
        rec = ctx.record
        tn = (rec.decision or {}).get("trial_number")

        if rec.operation == "add_two" and rec.record_status == "completed":
            # Chain: add_three(x = add_two.result)
            x_next = float((rec.outputs or {}).get("result", 0.0))
            return Action(
                type=ActionType.ADD_STEP,
                reason=f"chain add_three after add_two (x={x_next:.3f})",
                payload={
                    "step": ProposedStep(
                        operation="add_three",
                        inputs={"x": x_next},
                        decision={
                            "planner": self.name,
                            "trial_number": tn,
                        },
                    )
                },
            )

        if rec.operation == "add_two" and rec.record_status != "completed":
            # Failed add_two — tell Optuna this trial failed, continue.
            if isinstance(tn, int) and tn in self._pending:
                trial = self._pending.pop(tn)
                self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
                self._told.add(tn)
            return Action(type=ActionType.CONTINUE, reason="add_two failed, skipping add_three")

        # add_three completed (or failed — plan() will handle): continue.
        return Action(type=ActionType.CONTINUE, reason="step complete")
