# Examples

Each subdirectory is a standalone example that registers Resources,
Tools, and a Campaign against a fresh `Lab`. Examples live outside the
framework (`examples/`, not `src/autolab/`) so the framework code does
not depend on any one demo pack.

## Running

From the repo root:

```bash
pixi run python -m examples.superellipse_sensor.run
```

A working `pyproject.toml`-installed environment with the `autolab`
package on `PYTHONPATH` is enough. Examples that need extra deps
(ubermag, OOMMF, etc.) say so in their own README.

For examples exposed as Lab packs, the preferred manual flow is:

```bash
pixi run clean
pixi run serve-prod
```

In a second terminal:

```bash
pixi run apply-bootstrap -- <pack-name>
```

That exercises the same runtime registration path the UI uses, rather than
hiding registration inside process startup.

## Available examples

- [`superellipse_sensor/`](superellipse_sensor/) - optimise the
  small-signal sensitivity of a superellipse-shaped sensor element.
  Single computer Resource. Bayesian-optimisation Planner. Uses
  ubermag/OOMMF if available and otherwise falls back to a labelled
  closed-form surrogate.

- [`mammos_sensor/`](mammos_sensor/) - end-to-end multiscale hard-magnet
  pipeline: MLIP structure relaxation -> 0 K intrinsic parameters ->
  finite-temperature Kuzmin fit -> finite-element micromagnetics
  hysteresis -> sensor figure-of-merit. Demonstrates a VM Resource
  (WSL / SSH / local), a 6-step `WorkflowTemplate` with input wiring,
  Bayesian and Optuna planners, surrogate labelling, and failure
  taxonomy. Boot with `AUTOLAB_BOOTSTRAP=mammos pixi run serve` to
  register all six Operations and the workflow against the running Lab.

- `sensor_shape_opt` bootstrap - minimal MaMMoS geometry-optimisation
  campaign. It registers only the VM Resource, material Operation, FOM
  Operation, and 2-step workflow needed for shape optimisation. Run
  `pixi run sensor-demo` against a running Lab to create a queued Optuna
  campaign where each trial executes the full material -> FOM DAG.

- [`wsl_ssh_demo/`](wsl_ssh_demo/) - two tiny Operations executed on a
  WSL2 host over `ssh wsl2`: `add_two`, `cube`, the workflow
  `add_two_then_cube`, and planner `wsl_ssh_add_cube_optuna`. Apply with
  `pixi run apply-bootstrap -- wsl_ssh_demo`.
  Precondition: `ssh wsl2` must work with key-based auth and the scripts
  must exist under `/home/sam/autolab-wsl/scripts/`.
