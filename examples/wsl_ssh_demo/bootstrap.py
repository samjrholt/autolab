"""Bootstrap for wsl_ssh_demo.

Registered entities
-------------------
Resource   : wsl  (kind=computer, accessed via ``ssh wsl2``)
Capability : add_two  (x -> x + 2, script on WSL)
Capability : cube     (x -> x ** 3, script on WSL)
Workflow   : add_two_then_cube
Planner    : wsl_ssh_add_cube_optuna  (Optuna TPE, maximise, x in [0, 10])

From the UI: start a campaign against the ``add_two_then_cube`` workflow
with planner ``wsl_ssh_add_cube_optuna`` and objective key ``result``,
direction ``maximise``. Optimal x = 10 -> result = 1728.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autolab.lab import Lab


def bootstrap(lab: "Lab") -> None:
    from autolab.models import Resource, WorkflowStep, WorkflowTemplate
    from autolab.planners.registry import register_planner

    from examples.wsl_ssh_demo.operations import WslAddTwo, WslCube
    from examples.wsl_ssh_demo.planner import WslAddCubeOptimizer
    from examples.wsl_ssh_demo.ssh import ssh_available

    if not ssh_available():
        raise RuntimeError(
            "ssh wsl2 is not reachable. Ensure ~/.ssh/config has a 'wsl2' host "
            "alias with key-based auth (no password)."
        )

    try:
        register_planner(
            "wsl_ssh_add_cube_optuna",
            lambda _cfg: WslAddCubeOptimizer(x_low=0.0, x_high=10.0),
        )
    except ValueError:
        pass  # already registered (server reload)

    if not any(r.name == "wsl" for r in lab.resources.list()):
        lab.register_resource(
            Resource(
                name="wsl",
                kind="computer",
                description="WSL2 Ubuntu reached over SSH (host alias 'wsl2') using key-based auth.",
                capabilities={
                    "backend": "ssh",
                    "ssh_host": "wsl2",
                    "remote_root": "/home/sam/autolab-wsl",
                    "scripts_dir": "/home/sam/autolab-wsl/scripts",
                    "auth": "keyless",
                    "python3": True,
                },
                typical_operation_durations={"add_two": 1, "cube": 1},
            )
        )

    if not lab.tools.has("add_two"):
        lab.register_operation(WslAddTwo)
    if not lab.tools.has("cube"):
        lab.register_operation(WslCube)

    if "add_two_then_cube" not in lab._workflows:
        lab.register_workflow(
            WorkflowTemplate(
                name="add_two_then_cube",
                description="Chain: add_two -> cube. result = (input_x + 2)**3.",
                steps=[
                    WorkflowStep(step_id="add_two", operation="add_two"),
                    WorkflowStep(
                        step_id="cube",
                        operation="cube",
                        depends_on=["add_two"],
                        input_mappings={"x": "add_two.result"},
                    ),
                ],
            )
        )
