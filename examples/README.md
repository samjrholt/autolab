# Examples

Each subdirectory is a standalone example that registers Resources +
Tools + a Campaign against a fresh `Lab`. **Examples live outside the
framework** (`examples/`, not `src/autolab/`) — the `autolab` package
must not import any of them. The whole point is that swapping the
example never touches a line of framework code.

## Running

From the repo root:

```bash
pixi run python -m examples.superellipse_sensor.run
```

A working `pyproject.toml`-installed environment with the `autolab`
package on `PYTHONPATH` is enough. Examples that need extra deps
(ubermag, OOMMF, etc.) say so in their own README.

## Available examples

- [`superellipse_sensor/`](superellipse_sensor/) — optimise the
  small-signal sensitivity of a superellipse-shaped sensor element.
  Single computer Resource. Bayesian-optimisation Planner. Uses
  ubermag/OOMMF if available; falls back to a labelled closed-form
  surrogate otherwise (the Record's outputs always carry the executing
  module string, per the "surrogates are never silently substituted"
  invariant).
