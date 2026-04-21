"""MaMMoS sensor workflow template.

The full multiscale chain as a reusable :class:`~autolab.WorkflowTemplate`:

::

    relax ──► intrinsic_0k ──► finite_t ──► mesh
                                              │
                              ┌───────────────┘
                              ▼
                     hysteresis ──► fom

Each dependency edge carries an :attr:`~autolab.WorkflowStep.input_mappings`
declaration so the upstream step's outputs flow into the downstream
step's inputs without any orchestration code.

Why a workflow template (not just a Planner loop)?

    The multiscale chain is *deterministic* once the composition is fixed
    — there is no reactive replanning inside a single candidate's
    pipeline. The Planner's job is to pick the next candidate; the
    workflow's job is to run the candidate to completion. Keeping these
    concerns separate means the chain can be reused by any Planner.

Reusability

    Swap :class:`StructureRelax` for a "lookup-from-database" operation
    and the rest of the workflow keeps working: the contract is the
    ``Ms(T) / K1(T) / Aex(T)`` triple flowing into the mesh + hysteresis
    steps.
"""

from __future__ import annotations

from autolab.models import WorkflowStep, WorkflowTemplate


MAMMOS_SENSOR_WORKFLOW = WorkflowTemplate(
    name="mammos_sensor",
    description=(
        "MaMMoS multiscale sensor demonstrator — composition → relaxed "
        "structure → 0-K magnetics → finite-T magnetics → sensor mesh → "
        "micromagnetic hysteresis → sensor figures of merit."
    ),
    typical_duration_s=30 * 60,  # ~30 minutes end-to-end with real backends
    steps=[
        WorkflowStep(
            step_id="relax",
            operation="mammos.relax_structure",
            # Input values come from the Campaign via input_overrides.
            inputs={},
        ),
        WorkflowStep(
            step_id="intrinsic_0k",
            operation="mammos.intrinsic_magnetics_0k",
            depends_on=["relax"],
            input_mappings={
                "a_ang": "relax.a_ang",
                "c_ang": "relax.c_ang",
            },
        ),
        WorkflowStep(
            step_id="finite_t",
            operation="mammos.finite_temperature_magnetics",
            depends_on=["intrinsic_0k"],
            input_mappings={
                "Ms0_A_per_m": "intrinsic_0k.Ms0_A_per_m",
                "K1_0_J_per_m3": "intrinsic_0k.K1_0_J_per_m3",
                "Aex0_J_per_m": "intrinsic_0k.Aex0_J_per_m",
            },
        ),
        WorkflowStep(
            step_id="mesh",
            operation="mammos.sensor_mesh",
            # No depends_on: the mesh step runs in parallel with intrinsic_0k / finite_t
            # once the geometry parameters are known. This keeps the Gantt visibly
            # parallel during the demo.
            inputs={},
        ),
        WorkflowStep(
            step_id="hysteresis",
            operation="mammos.micromagnetic_hysteresis",
            depends_on=["finite_t", "mesh"],
            input_mappings={
                "Ms_A_per_m": "finite_t.Ms_T_A_per_m",
                "K1_J_per_m3": "finite_t.K1_T_J_per_m3",
                "Aex_J_per_m": "finite_t.Aex_T_J_per_m",
                "area_nm2": "mesh.area_nm2",
                "aspect_ratio": "mesh.aspect_ratio",
                "thickness_nm": "mesh.thickness_nm",
                "mesh_path": "mesh.mesh_path",
            },
        ),
        WorkflowStep(
            step_id="fom",
            operation="mammos.sensor_fom",
            depends_on=["hysteresis", "finite_t"],
            input_mappings={
                "H_A_per_m": "hysteresis.H_A_per_m",
                "M_A_per_m": "hysteresis.M_A_per_m",
                "Hc_A_per_m": "hysteresis.Hc_A_per_m",
                "Mr_A_per_m": "hysteresis.Mr_A_per_m",
                "Ms_A_per_m": "finite_t.Ms_T_A_per_m",
            },
        ),
    ],
)


def default_input_overrides(
    *,
    composition: dict[str, float] | None = None,
    prototype: str = "FeCo",
    a_nm: float = 120.0,
    b_nm: float = 80.0,
    n: float = 2.5,
    thickness_nm: float = 5.0,
    cell_size_nm: float = 3.0,
    target_temp_k: float = 300.0,
    H_max_A_per_m: float = 8.0e4,
    n_steps: int = 41,
) -> dict[str, dict[str, object]]:
    """Bundle step-level overrides for one workflow instance.

    Used by the Campaign to materialise each trial — the BO / Optuna
    planner varies ``a_nm``, ``b_nm``, ``n``, and ``thickness_nm``; the
    rest come from the material defaults.
    """
    comp = composition or {"Fe": 0.5, "Co": 0.5}
    return {
        "relax": {
            "composition": comp,
            "prototype": prototype,
        },
        "intrinsic_0k": {
            "prototype": prototype,
        },
        "finite_t": {
            "prototype": prototype,
            "target_temp_k": target_temp_k,
        },
        "mesh": {
            "a_nm": a_nm,
            "b_nm": b_nm,
            "n": n,
            "thickness_nm": thickness_nm,
            "cell_size_nm": cell_size_nm,
        },
        "hysteresis": {
            "H_max_A_per_m": H_max_A_per_m,
            "n_steps": n_steps,
        },
        "fom": {},
    }


__all__ = ["MAMMOS_SENSOR_WORKFLOW", "default_input_overrides"]
