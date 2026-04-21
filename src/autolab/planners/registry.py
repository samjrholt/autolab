"""Planner registry — look up a Planner by name and build it from a config dict.

The registry is how the HTTP surface (``POST /campaigns``) materialises a
Planner from JSON: the client sends ``{"planner": "optuna", "config":
{...}}`` and the server asks the registry for the matching factory. It's
also a convenient indirection for demos and tests — ``build("bo", cfg)``
is shorter than importing :class:`~autolab.planners.bo.BOPlanner` by hand.

A factory takes a ``dict`` config and returns a ready Planner. The
built-in factories wrap their respective ``*Config`` dataclasses so the
input is plain JSON.

Registering your own Planner::

    from autolab.planners.registry import register_planner

    register_planner("my_sampler", lambda cfg: MySampler(**cfg))

Unknown names raise :class:`KeyError`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from autolab.planners.base import Planner

PlannerFactory = Callable[[Mapping[str, Any]], Planner]


_REGISTRY: dict[str, PlannerFactory] = {}


def register_planner(name: str, factory: PlannerFactory, *, overwrite: bool = False) -> None:
    """Add a Planner factory. ``overwrite=False`` raises on collision."""
    if not overwrite and name in _REGISTRY:
        raise ValueError(f"planner {name!r} already registered")
    _REGISTRY[name] = factory


def unregister_planner(name: str) -> None:
    _REGISTRY.pop(name, None)


def list_planners() -> list[str]:
    return sorted(_REGISTRY)


def build(name: str, config: Mapping[str, Any]) -> Planner:
    """Return a new Planner instance from a registered factory."""
    if name not in _REGISTRY:
        raise KeyError(f"no planner registered for {name!r} — known: {list_planners()!r}")
    return _REGISTRY[name](config)


# ---------------------------------------------------------------------------
# Built-in factories
# ---------------------------------------------------------------------------


def _bo_factory(config: Mapping[str, Any]) -> Planner:
    from autolab.planners.bo import BOConfig, BOPlanner

    return BOPlanner(BOConfig(**config))


def _optuna_factory(config: Mapping[str, Any]) -> Planner:
    from autolab.planners.optuna import OptunaConfig, OptunaPlanner

    return OptunaPlanner(OptunaConfig(**config))


register_planner("bo", _bo_factory)
register_planner("optuna", _optuna_factory)


__all__ = [
    "PlannerFactory",
    "build",
    "list_planners",
    "register_planner",
    "unregister_planner",
]
