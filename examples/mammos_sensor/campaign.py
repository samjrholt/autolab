"""Campaign + Planner factory for the MaMMoS sensor demonstrator.

Two campaign shapes are provided:

- :func:`build_single_run_campaign` — evaluate the full workflow once
  for a specific geometry / composition. Useful for "print me the
  sensor performance of these parameters" queries.

- :func:`build_bo_campaign` + :func:`build_bo_planner` — Bayesian
  optimisation over the free-layer geometry (a, b, n, thickness) to
  maximise the low-field sensitivity while keeping a decent linear
  range. This is the headline "close the loop" demo.

The Campaign's ``objective.key`` is the top-level output on the
workflow's *final* step (``sensor_fom``), so the Orchestrator can find
it without any special wiring.
"""

from __future__ import annotations

from typing import Any

from autolab import AcceptanceCriteria, Campaign, Objective
from autolab.planners.bo import BOConfig, BOPlanner
from autolab.planners.optuna import OptunaConfig, OptunaPlanner


# ---------------------------------------------------------------------------
# Campaign specs
# ---------------------------------------------------------------------------


def build_single_run_campaign(
    *,
    name: str = "mammos-sensor-single-run",
    description: str | None = "Single evaluation of the MaMMoS sensor chain.",
) -> Campaign:
    """A campaign with budget=1 — runs the workflow once and stops."""
    return Campaign(
        name=name,
        description=description,
        objective=Objective(key="sensitivity_per_T", direction="maximise", unit="1/T"),
        acceptance=None,
        budget=1,
    )


def build_bo_campaign(
    *,
    name: str = "mammos-sensor-bo",
    sensitivity_target: float = 1.5,
    min_linear_range_T: float = 5e-3,
    budget: int = 16,
) -> Campaign:
    """Bayesian optimisation campaign over the sensor free-layer geometry.

    Objective: maximise the low-field sensitivity ``(dM/dH)/Ms`` at ``H=0``.
    Acceptance gate: require a sensitivity ≥ target AND a linear range of
    at least ``min_linear_range_T`` so we don't just optimise sensitivity
    into a spike.
    """
    return Campaign(
        name=name,
        description=(
            "Optimise the MaMMoS sensor free-layer geometry (a, b, n, thickness) "
            "for maximum small-signal sensitivity with a practical linear range."
        ),
        objective=Objective(key="sensitivity_per_T", direction="maximise", unit="1/T"),
        acceptance=AcceptanceCriteria(
            rules={
                "sensitivity_per_T": {">=": sensitivity_target},
                "linear_range_T": {">=": min_linear_range_T},
            }
        ),
        budget=budget,
        parallelism=1,
    )


# ---------------------------------------------------------------------------
# Planners
# ---------------------------------------------------------------------------

# Free parameters the BO / Optuna sampler can tune.
GEOMETRY_SEARCH_SPACE: dict[str, dict[str, Any]] = {
    "a_nm": {"type": "float", "low": 80.0, "high": 240.0},
    "b_nm": {"type": "float", "low": 60.0, "high": 200.0},
    "n": {"type": "float", "low": 2.0, "high": 6.0},
    "thickness_nm": {"type": "float", "low": 3.0, "high": 15.0},
}


def build_bo_planner(*, seed: int | None = 42) -> BOPlanner:
    """In-house GP-EI Bayesian optimiser over the geometry space.

    The Planner proposes ``ProposedStep(operation="mammos.workflow.sensor", inputs=...)``
    trials; the run script translates each into a full workflow
    execution via ``lab.run_workflow(...)``.
    """
    return BOPlanner(
        BOConfig(
            operation="mammos.workflow.sensor",
            parameter_space=GEOMETRY_SEARCH_SPACE,
            initial_random=4,
            candidate_pool=1024,
            length_scale=0.3,
            seed=seed,
        )
    )


def build_optuna_planner(*, sampler: str = "tpe", seed: int | None = 42) -> OptunaPlanner:
    """Optuna-backed TPE/CMA-ES planner over the same geometry space."""
    return OptunaPlanner(
        OptunaConfig(
            operation="mammos.workflow.sensor",
            search_space=GEOMETRY_SEARCH_SPACE,
            sampler=sampler,
            seed=seed,
        )
    )


__all__ = [
    "GEOMETRY_SEARCH_SPACE",
    "build_bo_campaign",
    "build_bo_planner",
    "build_optuna_planner",
    "build_single_run_campaign",
]
