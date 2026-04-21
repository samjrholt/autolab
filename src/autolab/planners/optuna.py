"""Optuna-backed Planner.

Wraps Optuna's ask/tell sampler behind the :class:`~autolab.Planner`
interface so a Campaign can drive a TPE / CMA-ES / GP / random search
without the framework depending on Optuna's loop semantics.

Why a wrapper (not "Optuna is the planner"):

- The Planner interface already knows how to talk to the ledger
  (``plan()`` reads history, ``react()`` decides what to do after each
  Record). Optuna only knows hyperparameter sampling.
- Ask/tell is a clean one-way adapter: on every ``plan()`` we replay
  completed Records into ``study.tell()`` (cheap — results are cached by
  trial number) and then ``study.ask()`` the next batch.
- A ``ProposedStep`` tagged ``decision.trial_number=N`` is how we link a
  Record back to the Optuna trial. The tag survives restarts, so a
  crash-resumed Campaign picks up where the ledger left off.

Search-space formats
--------------------

Two forms are accepted:

1. **Bounds dict** (simple, works for most cases)::

       parameter_space = {
           "Ms": {"type": "float", "low": 6e5, "high": 1.6e6},
           "n":  {"type": "float", "low": 2.0, "high": 6.0},
           "k":  {"type": "int",   "low": 1,   "high": 8},
           "cat": {"type": "categorical", "choices": ["A", "B", "C"]},
           "lr": {"type": "float", "low": 1e-4, "high": 1.0, "log": True},
       }

2. **Callable** ``(trial) -> dict`` for constrained / conditional spaces::

       def sample(trial):
           a = trial.suggest_float("a", 50.0, 300.0)
           b = trial.suggest_float("b", 50.0, a)  # b cannot exceed a
           return {"a": a, "b": b}

Samplers
--------

``sampler`` can be ``"tpe"`` (default), ``"cmaes"``, ``"gp"``,
``"random"``, or an Optuna ``BaseSampler`` instance. Unknown strings
raise ``ValueError`` at construction time.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from autolab.models import ProposedStep
from autolab.planners.base import PlanContext, Planner, PolicyProvider

if TYPE_CHECKING:  # pragma: no cover
    import optuna as _optuna


SamplerSpec = str | Any  # str name, or an optuna BaseSampler instance
SearchSpace = dict[str, dict[str, Any]] | Callable[[Any], dict[str, Any]]


@dataclass
class OptunaConfig:
    """Configuration bundle for :class:`OptunaPlanner`."""

    operation: str
    search_space: SearchSpace
    batch_size: int = 1
    sampler: SamplerSpec = "tpe"
    seed: int | None = 42
    fixed_inputs: dict[str, Any] = field(default_factory=dict)


def _build_sampler(sampler: SamplerSpec, seed: int | None) -> _optuna.samplers.BaseSampler:
    import optuna

    if not isinstance(sampler, str):
        return sampler  # already an instance
    name = sampler.lower()
    if name == "tpe":
        return optuna.samplers.TPESampler(seed=seed)
    if name == "cmaes":
        return optuna.samplers.CmaEsSampler(seed=seed)
    if name == "random":
        return optuna.samplers.RandomSampler(seed=seed)
    if name in {"gp", "gaussian_process"}:
        try:
            return optuna.samplers.GPSampler(seed=seed)
        except AttributeError as exc:  # older optuna
            raise ValueError("'gp' sampler requires optuna>=3.6 (has GPSampler)") from exc
    raise ValueError(f"unknown Optuna sampler {sampler!r}")


def _dict_to_search_fn(
    space: dict[str, dict[str, Any]],
) -> Callable[[Any], dict[str, Any]]:
    """Turn a bounds dict into a ``(trial) -> dict`` callable."""

    def sample(trial: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, spec in space.items():
            kind = spec.get("type", "float")
            if kind == "float":
                out[name] = trial.suggest_float(
                    name,
                    float(spec["low"]),
                    float(spec["high"]),
                    log=bool(spec.get("log", False)),
                )
            elif kind == "int":
                out[name] = trial.suggest_int(name, int(spec["low"]), int(spec["high"]))
            elif kind == "categorical":
                out[name] = trial.suggest_categorical(name, list(spec["choices"]))
            else:
                raise ValueError(f"unknown parameter type {kind!r} for {name!r}")
        return out

    return sample


class OptunaPlanner(Planner):
    """Optuna ask/tell wrapped as an autolab Planner.

    Each ``plan()`` call:

    1. Replays all completed Records for this campaign+operation into
       Optuna via ``study.tell()`` (skipping trials already told).
    2. Asks the sampler for ``batch_size`` fresh trials via
       ``study.ask()`` and emits one :class:`ProposedStep` per trial,
       tagging ``decision.trial_number`` so we can re-link.

    ``react()`` falls through to the ``PolicyProvider`` — Optuna does not
    make reactive decisions, it only proposes.
    """

    name = "optuna"

    def __init__(
        self,
        config: OptunaConfig,
        policy: PolicyProvider | None = None,
    ) -> None:
        super().__init__(policy=policy)
        self.config = config
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        self._optuna = optuna

        if callable(config.search_space):
            self._search_fn = config.search_space
        else:
            self._search_fn = _dict_to_search_fn(config.search_space)

        self._study = optuna.create_study(
            direction="maximize",  # we normalise direction below
            sampler=_build_sampler(config.sampler, config.seed),
        )
        self._told: set[int] = set()
        # Cache the active trials returned by ask() between plan() and tell() cycles.
        self._pending: dict[int, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, context: PlanContext) -> list[ProposedStep]:
        objective = context.objective
        self._tell_completed(context, objective.key, objective.direction)

        proposals: list[ProposedStep] = []
        remaining = context.remaining_budget
        n = self.config.batch_size
        if remaining is not None:
            n = min(n, remaining)
        for _ in range(max(0, n)):
            trial = self._study.ask()
            params = self._search_fn(trial)
            self._pending[trial.number] = trial
            proposals.append(self._propose_step(trial.number, params))
        return proposals

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tell_completed(self, context: PlanContext, key: str, direction: str) -> None:
        sign = 1.0 if direction == "maximise" else -1.0
        for rec in context.history:
            tn = rec.decision.get("trial_number") if rec.decision else None
            if not isinstance(tn, int) or tn in self._told:
                continue
            planner = rec.decision.get("planner") if rec.decision else None
            if planner and planner != self.name:
                continue
            trial = self._pending.pop(tn, None)
            if trial is None:
                # Record references a trial from a different process — skip.
                continue
            if rec.record_status == "completed" and key in rec.outputs:
                try:
                    value = float(rec.outputs[key])
                except (TypeError, ValueError):
                    self._study.tell(trial, state=self._optuna.trial.TrialState.FAIL)
                else:
                    self._study.tell(trial, sign * value)
            elif rec.record_status in {"failed", "soft_fail"}:
                self._study.tell(trial, state=self._optuna.trial.TrialState.FAIL)
            else:
                # Record isn't completed yet — leave pending.
                self._pending[tn] = trial
                continue
            self._told.add(tn)

    def _propose_step(self, trial_number: int, params: dict[str, Any]) -> ProposedStep:
        inputs: dict[str, Any] = dict(self.config.fixed_inputs)
        inputs.update(params)
        return ProposedStep(
            operation=self.config.operation,
            inputs=inputs,
            decision={
                "planner": self.name,
                "method": "optuna",
                "trial_number": trial_number,
                "sampler": (
                    self.config.sampler
                    if isinstance(self.config.sampler, str)
                    else type(self.config.sampler).__name__
                ),
            },
        )


__all__ = ["OptunaConfig", "OptunaPlanner"]
