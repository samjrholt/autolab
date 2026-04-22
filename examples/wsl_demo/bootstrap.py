"""Bootstrap the wsl_demo lab.

Run with:
    $env:AUTOLAB_BOOTSTRAP="wsl_demo"; pixi run serve

Prerequisites (already set up by the repo):
    - WSL Ubuntu running
    - ~/autolab-wsl pixi project with numpy/scipy/matplotlib installed
    - ~/.pixi/bin/pixi available in WSL
    (Run `PYTHONPATH=. pixi run python examples/wsl_demo/write_scripts.py`
    once to create the WSL environment if starting fresh.)

What gets registered
---------------------
Resource:  wsl-ubuntu  (kind=computer, 16 CPUs)
Capability: wsl_info        - gather WSL system info
Capability: wsl_numpy_eval  - evaluate numpy expressions with x

Workflow 1: wsl_health_check
  Step: wsl_info  --  verifies WSL + pixi + packages are working

Workflow 2: wsl_compute_chain
  Step 1: wsl_numpy_eval(x=input, expression="x**2")        -> result = x^2
  Step 2: wsl_numpy_eval(x=step1.result, expression="np.sqrt(x)") -> result = x
  (Chain round-trips: sqrt(x^2) = x. Tests input_mapping wiring end-to-end.)

Workflow 3: wsl_wave_eval
  Step: wsl_numpy_eval(x=input, expression="np.sin(x) * np.cos(x/2)")
  Use with an Optuna campaign to find peak in [0, 6].
  Optimal near x=1.15, peak value ~0.77.

Campaign for wsl_wave_eval
---------------------------
  Name:      find_wave_peak
  Objective: result, maximise
  Planner:   optuna
  Config:    {"operation": "wsl_numpy_eval",
              "search_space": {"x": {"type": "float", "low": 0.0, "high": 6.0}},
              "sampler": "tpe", "batch_size": 1,
              "fixed_inputs": {"expression": "np.sin(x) * np.cos(x/2)"}}
  Budget:    20
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autolab.lab import Lab


def bootstrap(lab: "Lab") -> None:
    from autolab.models import Resource, WorkflowStep, WorkflowTemplate
    from autolab.planners.registry import register_planner

    from examples.wsl_demo.operations import WslInfo, WslNumpyEval
    from examples.wsl_demo.wsl import wsl_available

    if not wsl_available():
        raise RuntimeError(
            "WSL is not available (wsl.exe not found or Ubuntu not running). "
            "Start WSL with: wsl --distribution Ubuntu"
        )

    # --- Resource -------------------------------------------------------
    if not any(r.name == "wsl-ubuntu" for r in lab.resources.list()):
        lab.register_resource(
            Resource(
                name="wsl-ubuntu",
                kind="computer",
                description="Ubuntu 22.04 WSL2 (16 CPUs, numpy/scipy via pixi).",
                capabilities={"cpus": 16, "wsl": True, "numpy": True, "scipy": True},
            )
        )

    # --- Capabilities ---------------------------------------------------
    if not lab.tools.has("wsl_info"):
        lab.register_operation(WslInfo)
    if not lab.tools.has("wsl_numpy_eval"):
        lab.register_operation(WslNumpyEval)

    # --- Workflow 1: health check ----------------------------------------
    if "wsl_health_check" not in lab._workflows:
        lab.register_workflow(
            WorkflowTemplate(
                name="wsl_health_check",
                description="Verify WSL + pixi env are working. Returns numpy/scipy versions.",
                steps=[
                    WorkflowStep(step_id="info", operation="wsl_info"),
                ],
            )
        )

    # --- Workflow 2: compute chain (tests input_mapping) ----------------
    if "wsl_compute_chain" not in lab._workflows:
        lab.register_workflow(
            WorkflowTemplate(
                name="wsl_compute_chain",
                description="x -> wsl_numpy_eval(x^2) -> wsl_numpy_eval(sqrt) = x. Tests WSL chain.",
                steps=[
                    WorkflowStep(
                        step_id="square",
                        operation="wsl_numpy_eval",
                        inputs={"expression": "x**2"},
                    ),
                    WorkflowStep(
                        step_id="root",
                        operation="wsl_numpy_eval",
                        depends_on=["square"],
                        inputs={"expression": "np.sqrt(x)"},
                        input_mappings={"x": "square.result"},
                    ),
                ],
            )
        )

    # --- Workflow 3: wave function eval ---------------------------------
    if "wsl_wave_eval" not in lab._workflows:
        lab.register_workflow(
            WorkflowTemplate(
                name="wsl_wave_eval",
                description="Evaluate sin(x)*cos(x/2) in WSL. Use with Optuna to find peak in [0,6].",
                steps=[
                    WorkflowStep(
                        step_id="wave",
                        operation="wsl_numpy_eval",
                        inputs={"expression": "np.sin(x) * np.cos(x/2)"},
                    ),
                ],
            )
        )
