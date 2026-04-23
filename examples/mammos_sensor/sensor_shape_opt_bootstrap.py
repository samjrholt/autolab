"""Minimal bootstrap for the sensor shape-optimisation demo.

Registers exactly what the ``sensor_shape_opt`` workflow needs and
nothing else:

- one ``vm`` :class:`~autolab.Resource` (``vm-primary``), probed at apply
  time against the WSL pixi env (``~/autolab-mammos`` by default);
- two :class:`~autolab.Operation` classes — :class:`SensorMaterialAtT`
  and :class:`SensorShapeFOM`;
- one :class:`~autolab.WorkflowTemplate` — :data:`SENSOR_SHAPE_OPT_WORKFLOW`.

This is the bootstrap the pixi task ``pixi run sensor-demo`` applies. It
is deliberately narrower than the ``mammos`` bootstrap (which registers
the full 6-step material chain) — demos should not pollute the Lab with
capabilities they don't use.

Idempotent: re-applying against a Lab that already has the entities is
a no-op.
"""

from __future__ import annotations

from typing import Any

from autolab.lab import Lab
from autolab.models import Resource

from examples.mammos_sensor.operations.sensor_demo import (
    SensorMaterialAtT,
    SensorShapeFOM,
)
from examples.mammos_sensor.vm import VMExecutor, probe_vm
from examples.mammos_sensor.workflow import SENSOR_SHAPE_OPT_WORKFLOW


def bootstrap(lab: Lab) -> None:
    # --- Resource: VM (idempotent) -----------------------------------------
    vm = VMExecutor()
    existing = {r.name for r in lab.resources.list()}
    if "vm-primary" not in existing:
        probe = probe_vm(vm)
        lab.register_resource(
            Resource(
                name="vm-primary",
                kind="vm",
                capabilities={
                    "reachable": probe.get("reachable", False),
                    "python_version": probe.get("python_version"),
                    "has_ubermag_chain": probe.get("has_ubermag_chain", False),
                    "has_full_mammos_chain": probe.get("has_full_mammos_chain", False),
                    "mammos_spindynamics": probe.get("mammos_spindynamics"),
                    "mammos_analysis": probe.get("mammos_analysis"),
                    "ubermag": probe.get("ubermag"),
                    "oommf_binary": probe.get("oommf_binary"),
                },
                description=f"MaMMoS execution VM: {vm.description}",
                asset_id=probe.get("hostname") or "vm-primary",
                typical_operation_durations={
                    "mammos.sensor_material_at_T": 10,
                    "mammos.sensor_shape_fom": 120,
                },
            )
        )

    # --- Operations (idempotent via lab.tools.has) --------------------------
    if not lab.tools.has("mammos.sensor_material_at_T"):
        lab.register_operation(SensorMaterialAtT)
    if not lab.tools.has("mammos.sensor_shape_fom"):
        lab.register_operation(SensorShapeFOM)

    # --- Pre-hook: attach the VMExecutor to every Operation context --------
    # Only register once; hooks list is additive.
    if not getattr(lab, "_sensor_shape_opt_hook_attached", False):
        async def _attach_vm(ctx: Any, _state: Any) -> None:
            ctx.metadata.setdefault("vm_executor", vm)
        lab.orchestrator.add_pre_hook(_attach_vm)
        lab._sensor_shape_opt_hook_attached = True  # type: ignore[attr-defined]

    # --- Workflow (idempotent) ---------------------------------------------
    if SENSOR_SHAPE_OPT_WORKFLOW.name not in lab._workflows:
        lab.register_workflow(SENSOR_SHAPE_OPT_WORKFLOW)
