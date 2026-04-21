"""Planners and PolicyProviders — the decision layer.

A :class:`~autolab.Planner` implements ``plan(context)`` (batch
proposals) and ``react(context)`` (mid-experiment adaptation). The
Planner delegates the actual Action decision to a
:class:`~autolab.PolicyProvider` (heuristic, LLM, human), which is
interchangeable. Heuristics can pre-filter before an LLM call to bound
cost and latency.

Built-in planners
-----------------

- :class:`~autolab.planners.bo.BOPlanner` — in-house GP-EI, numpy-only.
  Zero extra deps, good for small / demo problems.
- :class:`~autolab.planners.optuna.OptunaPlanner` — Optuna ask/tell
  (TPE default; CMA-ES, GP, random also available). The recommended
  default for real problems because it handles int/categorical and
  conditional search spaces.

Both are registered in :mod:`autolab.planners.registry` so they can be
constructed from a config dict / JSON submission.
"""

from __future__ import annotations

from autolab.planners.base import (
    DecisionContext,
    HeuristicPolicyProvider,
    PlanContext,
    Planner,
    PolicyProvider,
)
from autolab.planners.registry import (
    build,
    list_planners,
    register_planner,
    unregister_planner,
)

__all__ = [
    "DecisionContext",
    "HeuristicPolicyProvider",
    "PlanContext",
    "Planner",
    "PolicyProvider",
    "build",
    "list_planners",
    "register_planner",
    "unregister_planner",
]
