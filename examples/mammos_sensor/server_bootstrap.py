"""Bootstrap the full MaMMoS sensor demonstrator into the Lab service.

Set ``AUTOLAB_BOOTSTRAP=mammos`` before ``pixi run serve`` (or export
``AUTOLAB_BOOTSTRAP=examples.mammos_sensor.server_bootstrap:bootstrap``
to wire this module directly) to pre-register:

- a ``vm`` Resource representing the execution VM (probed at boot),
- all six MaMMoS Operation classes,
- the ``mammos_sensor`` :class:`~autolab.WorkflowTemplate`.

The Console's workflow launcher will then expose the chain as a
one-click run. The Orchestrator attaches the probed ``VMExecutor`` to
every Operation context via a pre-hook — surrogates run when the
real backends are absent and the Record's ``module`` says so.
"""

from __future__ import annotations

from typing import Any

from autolab.lab import Lab
from autolab.models import Resource

from examples.mammos_sensor.operations import ALL_OPERATIONS
from examples.mammos_sensor.vm import VMExecutor, probe_vm
from examples.mammos_sensor.workflow import (
    MAMMOS_SENSOR_WORKFLOW,
    SENSOR_SHAPE_OPT_WORKFLOW,
)


def bootstrap(lab: Lab) -> None:
    vm = VMExecutor()
    probe = probe_vm(vm)
    lab.register_resource(
        Resource(
            name="vm-primary",
            kind="vm",
            capabilities={
                "reachable": probe.get("reachable", False),
                "python_version": probe.get("python_version"),
                "has_full_mammos_chain": probe.get("has_full_mammos_chain", False),
                "has_ubermag_chain": probe.get("has_ubermag_chain", False),
                "has_mace": probe.get("has_mace", False),
                "mammos_mumag": probe.get("mammos_mumag"),
                "mammos_spindynamics": probe.get("mammos_spindynamics"),
                "mammos_ai": probe.get("mammos_ai"),
            },
            description=f"MaMMoS execution VM: {vm.description}",
            asset_id=probe.get("hostname") or "vm-primary",
            typical_operation_durations={
                "mammos.relax_structure": 180,
                "mammos.intrinsic_magnetics_0k": 240,
                "mammos.finite_temperature_magnetics": 420,
                "mammos.sensor_mesh": 30,
                "mammos.micromagnetic_hysteresis": 900,
                "mammos.sensor_fom": 5,
            },
        )
    )
    for cls in ALL_OPERATIONS:
        lab.register_operation(cls)

    async def _attach_vm(ctx: Any, _state: Any) -> None:
        ctx.metadata.setdefault("vm_executor", vm)

    lab.orchestrator.add_pre_hook(_attach_vm)
    # Primary MVP workflow: sensor shape-opt demo (2 steps, real ubermag+OOMMF).
    lab.register_workflow(SENSOR_SHAPE_OPT_WORKFLOW)
    # Full materials chain also available for the full multiscale story.
    lab.register_workflow(MAMMOS_SENSOR_WORKFLOW)
    print(
        f"[mammos bootstrap] VM reachable={probe.get('reachable', False)} "
        f"registered {len(ALL_OPERATIONS)} ops, workflows "
        f"{[SENSOR_SHAPE_OPT_WORKFLOW.name, MAMMOS_SENSOR_WORKFLOW.name]}"
    )
