"""Bayesian-optimisation Planner — a tiny in-house GP + Expected Improvement loop.

Why hand-rolled? scikit-optimize and BoTorch are heavy and opinionated;
the framework should not depend on either. The optimiser here is
intentionally small (~100 lines of numpy) and good enough for the
hackathon's "first BO works end-to-end" milestone. Swap it for
scikit-optimize / BoTorch by writing a sibling Planner — same interface.

Search space format::

    parameter_space = {
        "Ms":      {"type": "float", "low": 0.5e6, "high": 1.6e6},
        "K1":      {"type": "float", "low": 0.0,   "high": 5e5},
        "a":       {"type": "float", "low": 50.0,  "high": 300.0},
        ...
    }

Objective is read from the typed :class:`~autolab.Objective` on the
``PlanContext`` — no more dict fishing::

    Objective(key="sensitivity", direction="maximise")

Each ProposedStep returned by `plan()` carries one set of parameter
values as `inputs`. The Planner reads completed Records from history,
fits a small GP, and proposes the next batch by maximising expected
improvement over a random sample of candidates.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from autolab.models import ProposedStep
from autolab.planners.base import PlanContext, Planner, PolicyProvider


@dataclass
class BOConfig:
    operation: str  # capability name to schedule
    parameter_space: dict[str, dict[str, Any]]
    initial_random: int = 5
    batch_size: int = 1
    candidate_pool: int = 1024
    length_scale: float = 0.3
    noise: float = 1e-6
    seed: int | None = 42
    fixed_inputs: dict[str, Any] | None = None  # parameters not under optimisation


class BOPlanner(Planner):
    """GP-EI Bayesian optimiser. One ProposedStep per batch entry."""

    name = "bo"

    def __init__(self, config: BOConfig, policy: PolicyProvider | None = None) -> None:
        super().__init__(policy=policy)
        self.config = config
        self._rng = random.Random(config.seed)
        self._np_rng = np.random.default_rng(config.seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, context: PlanContext) -> list[ProposedStep]:
        objective = context.objective
        key = objective.key
        direction = objective.direction

        completed = [
            r
            for r in context.history
            if r.record_status == "completed"
            and r.operation == self.config.operation
            and key in r.outputs
        ]

        # Cold start — pick random points until we have enough observations.
        if len(completed) < self.config.initial_random:
            n = min(self.config.batch_size, self.config.initial_random - len(completed))
            return [self._propose_step(self._sample_random()) for _ in range(n)]

        X, y = self._build_dataset(completed, key=key, direction=direction)
        candidates = np.array(
            [self._encode(self._sample_random()) for _ in range(self.config.candidate_pool)]
        )
        ei = self._expected_improvement(X, y, candidates)
        # Pick the top-N by EI, decoding back into parameter dicts.
        top_idx = np.argsort(-ei)[: self.config.batch_size]
        return [self._propose_step(self._decode(candidates[i])) for i in top_idx]

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def _sample_random(self) -> dict[str, float]:
        params: dict[str, float] = {}
        for name, spec in self.config.parameter_space.items():
            low = float(spec["low"])
            high = float(spec["high"])
            if spec.get("type", "float") == "int":
                params[name] = float(self._rng.randint(int(low), int(high)))
            else:
                params[name] = self._rng.uniform(low, high)
        return params

    def _propose_step(self, params: dict[str, float]) -> ProposedStep:
        inputs: dict[str, Any] = dict(self.config.fixed_inputs or {})
        inputs.update(params)
        return ProposedStep(
            operation=self.config.operation,
            inputs=inputs,
            decision={
                "planner": self.name,
                "method": "gp-ei",
                "parameter_space": list(self.config.parameter_space.keys()),
            },
        )

    # ------------------------------------------------------------------
    # GP-EI — minimal, isotropic squared-exponential kernel
    # ------------------------------------------------------------------

    def _encode(self, params: dict[str, float]) -> np.ndarray:
        bounds = [(float(s["low"]), float(s["high"])) for s in self.config.parameter_space.values()]
        names = list(self.config.parameter_space.keys())
        return np.array(
            [
                (params[n] - lo) / (hi - lo) if hi > lo else 0.0
                for n, (lo, hi) in zip(names, bounds, strict=True)
            ]
        )

    def _decode(self, x: np.ndarray) -> dict[str, float]:
        out: dict[str, float] = {}
        for value, (name, spec) in zip(x, self.config.parameter_space.items(), strict=True):
            low = float(spec["low"])
            high = float(spec["high"])
            v = low + float(value) * (high - low)
            if spec.get("type", "float") == "int":
                v = float(int(round(v)))
            out[name] = v
        return out

    def _build_dataset(
        self, completed: Sequence[Any], *, key: str, direction: str
    ) -> tuple[np.ndarray, np.ndarray]:
        names = list(self.config.parameter_space.keys())
        X_rows: list[np.ndarray] = []
        y_rows: list[float] = []
        for r in completed:
            try:
                params = {n: float(r.inputs[n]) for n in names}
            except (KeyError, TypeError, ValueError):
                continue
            X_rows.append(self._encode(params))
            value = float(r.outputs[key])
            y_rows.append(value if direction == "maximise" else -value)
        if not X_rows:
            return np.zeros((0, len(names))), np.zeros((0,))
        return np.vstack(X_rows), np.array(y_rows)

    def _kernel(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        diff = A[:, None, :] - B[None, :, :]
        sq = np.sum(diff * diff, axis=-1)
        return np.exp(-0.5 * sq / (self.config.length_scale**2))

    def _expected_improvement(
        self, X: np.ndarray, y: np.ndarray, candidates: np.ndarray
    ) -> np.ndarray:
        n = X.shape[0]
        K = self._kernel(X, X) + self.config.noise * np.eye(n)
        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            # Tiny ridge bump if numerically singular.
            L = np.linalg.cholesky(K + 1e-4 * np.eye(n))
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))
        K_s = self._kernel(X, candidates)
        mu = K_s.T @ alpha
        v = np.linalg.solve(L, K_s)
        var = 1.0 - np.sum(v * v, axis=0)
        var = np.clip(var, 1e-12, None)
        sigma = np.sqrt(var)

        f_best = float(np.max(y))
        z = (mu - f_best) / sigma
        ei = (mu - f_best) * _std_normal_cdf(z) + sigma * _std_normal_pdf(z)
        ei[sigma <= 1e-9] = 0.0
        return ei


def _std_normal_cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))


def _std_normal_pdf(z: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


__all__ = ["BOConfig", "BOPlanner"]
