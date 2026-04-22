"""Bootstrap the add_demo lab: two simple Operations + a chained workflow.

Run with:
    AUTOLAB_BOOTSTRAP=examples.add_demo.bootstrap:bootstrap pixi run serve
  or
    AUTOLAB_BOOTSTRAP=add_demo pixi run serve   (after wiring in app.py)

The demo registers:
  - Resource: ``wsl-local``  (local backend — no WSL or SSH needed; swap
    backend="ssh_exec" and host="..." to run for real on WSL/SSH)
  - Capability: ``add_two``  (AddTwo Operation — returns x + 2)
  - Capability: ``add_three`` (AddThree Operation — returns x + 3)
  - Workflow: ``add_two_then_three``  (add_two → add_three, wired so the
    output of add_two feeds as the input of add_three)

Then you can create a Campaign with the Optuna planner:
    {
        "name": "find_max",
        "objective": {"key": "result", "direction": "maximise"},
        "budget": 30,
        "planner": "optuna",
        "planner_config": {
            "operation": "add_two",
            "search_space": {"x": {"type": "float", "low": 0, "high": 10}}
        }
    }

With x in [0, 10], add_two returns x+2 (max 12), then add_three returns
x+2+3 = x+5 (max 15). Optuna should converge on x≈10 quickly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autolab.lab import Lab


def bootstrap(lab: "Lab") -> None:
    from autolab.models import Resource, WorkflowStep, WorkflowTemplate

    from examples.add_demo.operations import AddThree, AddTwo

    # --- Resource --------------------------------------------------------
    # "local" backend = subprocess on the current machine. On Windows with
    # WSL, swap backend="ssh_exec" + host="localhost" (or your WSL SSH
    # alias) to actually run inside the WSL environment.
    if not any(r.name == "wsl-local" for r in lab.resources.list()):
        lab.register_resource(
            Resource(
                name="wsl-local",
                kind="computer",
                backend="local",
                description="Local machine (swap to ssh_exec + host=localhost for real WSL).",
                tags={"cores": 8, "note": "add_demo test resource"},
            )
        )

    # --- Capabilities ----------------------------------------------------
    if not lab.tools.has("add_two"):
        lab.register_operation(AddTwo)
    if not lab.tools.has("add_three"):
        lab.register_operation(AddThree)

    # --- Workflow --------------------------------------------------------
    # Topology: add_two(x=initial) → add_three(x=add_two.result)
    # The input_mapping wires the ``result`` output of add_two into the
    # ``x`` input of add_three so the chain is: result = (initial+2)+3 = initial+5.
    if "add_two_then_three" not in lab._workflows:
        workflow = WorkflowTemplate(
            name="add_two_then_three",
            description="Chain: add_two → add_three. Output result = input + 5.",
            steps=[
                WorkflowStep(
                    step_id="add_two",
                    operation="add_two",
                    depends_on=[],
                    inputs={},          # x comes from campaign inputs
                ),
                WorkflowStep(
                    step_id="add_three",
                    operation="add_three",
                    depends_on=["add_two"],
                    inputs={},
                    input_mappings={"x": "add_two.result"},
                ),
            ],
        )
        lab.register_workflow(workflow)
