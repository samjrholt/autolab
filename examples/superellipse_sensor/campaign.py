"""Python factory for the superellipse-sensor campaign.

The previous incarnation of this file was ``campaign.yaml``; we moved to
a Python factory because:

- Campaigns are immutable Pydantic models (see
  [src/autolab/campaign.py](../../src/autolab/campaign.py)) — authoring
  them in YAML means re-parsing into the same model shape with none of
  the IDE / type-checker help.
- BO / Optuna search spaces are code-shaped — bounds can depend on
  each other (``b <= a``), bounds can be derived from physical
  constants, and the natural place for that is Python.
- If someone *wants* a declarative wire format, they can round-trip
  ``Campaign`` via ``model_dump_json`` / ``model_validate_json``. That
  is the declarative surface, not hand-written YAML.

The factory exposes :func:`build_campaign` and :func:`build_planner` so
:mod:`examples.superellipse_sensor.run` (and any other harness) can boot
the demo without hand-wiring numbers.
"""

from __future__ import annotations

from typing import Any

from autolab import AcceptanceCriteria, Campaign, Objective
from autolab.planners.bo import BOConfig, BOPlanner
from autolab.planners.optuna import OptunaConfig, OptunaPlanner


# Material defaults — values typical of an FeCo-like soft magnetic alloy.
# These pin parameters the search is *not* optimising over.
FIXED_INPUTS: dict[str, Any] = {
    "A_ex": 1.3e-11,   # J/m
    "thickness": 5.0,  # nm
    "H_max": 8.0e4,    # A/m  (~100 mT)
    "cell_size": 3.0,  # nm — only used by the ubermag backend
    "n_steps": 41,
}


# Parameter space — uniform floats except where otherwise noted.
PARAMETER_SPACE: dict[str, dict[str, Any]] = {
    "Ms": {"type": "float", "low": 6.0e5, "high": 1.6e6},  # A/m
    "K1": {"type": "float", "low": 0.0, "high": 1.0e4},    # J/m^3 — soft regime
    "a":  {"type": "float", "low": 80.0, "high": 240.0},   # nm
    "b":  {"type": "float", "low": 60.0, "high": 200.0},   # nm
    "n":  {"type": "float", "low": 2.0, "high": 6.0},
}


def build_campaign() -> Campaign:
    """The demo's user-facing search.

    Objective: maximise small-signal sensitivity at ``H=0`` while
    keeping the linear range respectable.
    """
    return Campaign(
        name="superellipse-sensor-search",
        description=(
            "Maximise small-signal sensitivity (|dM/dH|/Ms at H=0) of a "
            "superellipse sensor element while keeping the loop reasonably square."
        ),
        objective=Objective(key="sensitivity", direction="maximise", unit="1/T"),
        acceptance=AcceptanceCriteria(
            rules={
                "sensitivity": {">=": 1.5},     # 1/T at H=0
                "linear_range": {">=": 0.005},  # 5 mT linear half-width
            }
        ),
        budget=16,
        parallelism=1,
    )


def build_bo_planner(*, seed: int | None = 42) -> BOPlanner:
    """In-house GP-EI Bayesian optimiser — no extra deps."""
    return BOPlanner(
        BOConfig(
            operation="superellipse_hysteresis",
            parameter_space=PARAMETER_SPACE,
            initial_random=4,
            candidate_pool=1024,
            length_scale=0.3,
            seed=seed,
            fixed_inputs=FIXED_INPUTS,
        )
    )


def build_optuna_planner(
    *, sampler: str = "tpe", seed: int | None = 42
) -> OptunaPlanner:
    """Optuna-backed planner — recommended for real problems."""
    return OptunaPlanner(
        OptunaConfig(
            operation="superellipse_hysteresis",
            search_space=PARAMETER_SPACE,
            sampler=sampler,
            seed=seed,
            fixed_inputs=FIXED_INPUTS,
        )
    )


# Alias — default planner is Optuna/TPE.
build_planner = build_optuna_planner


__all__ = [
    "FIXED_INPUTS",
    "PARAMETER_SPACE",
    "build_bo_planner",
    "build_campaign",
    "build_optuna_planner",
    "build_planner",
]
