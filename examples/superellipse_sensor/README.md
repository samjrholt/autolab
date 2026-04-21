# superellipse_sensor

Optimise the small-signal sensitivity of a superellipse-shaped magnetic
sensor element using Bayesian optimisation, on a Lab with one Resource:
this computer.

## What this demonstrates

- **The framework is problem-agnostic.** `autolab` doesn't know what a
  hysteresis loop or a superellipse is. This example lives outside
  `src/autolab/` and registers itself by file path + import string.
- **Tool-as-YAML.** [`tool.yaml`](tool.yaml) declares the
  `superellipse_hysteresis` capability; its SHA-256 lands in every Record
  the Tool produces. Updating the YAML is a provenance-visible event.
- **Campaigns are Pydantic, not YAML.** [`campaign.py`](campaign.py)
  builds a typed [`Campaign`](../../src/autolab/campaign.py) with an
  [`Objective`](../../src/autolab/models.py), an
  [`AcceptanceCriteria`](../../src/autolab/models.py), and a budget —
  authored in code so the IDE and type checker help you.
- **Adapter-as-Operation.** [`adapter.py`](adapter.py) implements the
  Operation. Two backends — full ubermag/OOMMF when available, a
  labelled surrogate when not — each reports its own `module` string
  inside the Record's outputs. **Surrogates are never silently
  substituted.**
- **Two Planners, one interface.** The factory exposes both
  `build_optuna_planner()` (TPE / CMA-ES / GP / random via Optuna) and
  `build_bo_planner()` (in-house GP-EI, zero extra deps). Swap freely.
- **Closed Action vocabulary.** The default `HeuristicPolicyProvider`
  emits `accept` when the AcceptanceCriteria pass and `continue` while
  the search is still running.

## Running

```bash
# From repo root.
pixi run python -m examples.superellipse_sensor.run             # Optuna/TPE (default)
pixi run python -m examples.superellipse_sensor.run --planner bo
pixi run python -m examples.superellipse_sensor.run --sampler cmaes
```

ubermag is optional. If `discretisedfield`, `micromagneticmodel`, and
`oommfc` import cleanly, the adapter runs the real micromagnetic solver
and tags Records with `ubermag-superellipse.v0.1`. Otherwise it falls
back to a Stoner–Wohlfarth-style surrogate tagged
`superellipse-surrogate.v0.1`. The Lab ledger records which one ran for
every step.

## Files

| File | What it is |
|---|---|
| [`tool.yaml`](tool.yaml) | Capability declaration; hashed into every Record. |
| [`adapter.py`](adapter.py) | The `SuperellipseHysteresis` Operation (ubermag + surrogate paths). |
| [`geometry.py`](geometry.py) | Superellipse helpers (point-in-shape predicate, area). |
| [`campaign.py`](campaign.py) | Pydantic `Campaign` + Planner factories (Optuna, BO). |
| [`run.py`](run.py) | Boots the Lab, registers everything, runs the campaign. |
