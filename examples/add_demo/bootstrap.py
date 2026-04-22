"""Bootstrap the add_demo lab.

Boot with:
    $env:AUTOLAB_BOOTSTRAP="add_demo"; pixi run serve

What gets registered:
  - Resource: wsl-local (local backend, kind=computer)
  - Capability: add_two  (x → x + 2)
  - Capability: add_three (x → x + 3)
  - Workflow:   add_two_then_three
      Step 1: add_two  — receives x from campaign inputs
      Step 2: add_three — receives add_two.result via input_mapping

Then open http://localhost:8000 → Campaigns → New campaign.
Use the pre-filled "add_demo" template:
  - Planner: add_demo_optuna
  - Objective key: result, direction: maximise
  - Budget: 24  (= 12 trials × 2 steps each)
  - No planner_config needed (built into the planner)

With x in [0, 10]:
  add_two(x) = x + 2
  add_three(x+2) = x + 5
  Optimal x = 10 → result = 15.
Optuna (TPE) converges in ~5-8 trials.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autolab.lab import Lab


def bootstrap(lab: "Lab") -> None:
    from autolab.models import Resource, WorkflowStep, WorkflowTemplate
    from autolab.planners.registry import register_planner

    from examples.add_demo.operations import AddThree, AddTwo
    from examples.add_demo.planner import WorkflowChainOptimizer

    # --- Planner ---------------------------------------------------------
    # Register "add_demo_optuna" so the campaign form can reference it.
    try:
        register_planner(
            "add_demo_optuna",
            lambda _cfg: WorkflowChainOptimizer(x_low=0.0, x_high=10.0),
        )
    except ValueError:
        pass  # already registered (server reload)

    # --- Resource --------------------------------------------------------
    if not any(r.name == "wsl-local" for r in lab.resources.list()):
        lab.register_resource(
            Resource(
                name="wsl-local",
                kind="computer",
                description="Local machine (swap to ssh_exec for real WSL/SSH).",
                capabilities={"cores": 8},
            )
        )

    # --- Capabilities ----------------------------------------------------
    if not lab.tools.has("add_two"):
        lab.register_operation(AddTwo)
    if not lab.tools.has("add_three"):
        lab.register_operation(AddThree)

    # --- Workflow --------------------------------------------------------
    # Chain: add_two(x=campaign_input) → add_three(x=add_two.result)
    # input_mappings wire add_two's output into add_three's input.
    # Final result = x + 2 + 3 = x + 5.
    if "add_two_then_three" not in lab._workflows:
        lab.register_workflow(
            WorkflowTemplate(
                name="add_two_then_three",
                description="Chain: add_two → add_three. result = input_x + 5.",
                steps=[
                    WorkflowStep(
                        step_id="add_two",
                        operation="add_two",
                    ),
                    WorkflowStep(
                        step_id="add_three",
                        operation="add_three",
                        depends_on=["add_two"],
                        input_mappings={"x": "add_two.result"},
                    ),
                ],
            )
        )
