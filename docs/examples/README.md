# Example workflows

Documented end-to-end workflows that run on top of the framework. Each example is a registered set of Operations + Tool YAMLs, plus a narrative README explaining what it does and why. All examples live in [`examples/`](../../examples/) at the repo root.

## Implemented

- [**superellipse_sensor**](../../examples/superellipse_sensor/README.md) - Optimise the small-signal sensitivity of a superellipse-shaped sensor element. Single computer Resource, Bayesian-optimisation Planner, tool declared via YAML. Demonstrates: YAML capability declaration, surrogate-never-silently-substituted, acceptance criteria.

- [**mammos_sensor**](../../examples/mammos_sensor/README.md) - End-to-end multiscale hard-magnet pipeline: MLIP structure relaxation -> 0 K intrinsic parameters -> finite-temperature Kuzmin fit -> finite-element micromagnetics hysteresis -> sensor figure-of-merit. Demonstrates: VM Resource (WSL / SSH / local), 6-step WorkflowTemplate with input wiring, Bayesian and Optuna planners, Python-first Operation registration, failure taxonomy. Boot with `AUTOLAB_BOOTSTRAP=mammos pixi run serve`.

- **sensor_shape_opt** - Minimal MaMMoS campaign demo for geometry optimisation. Registers a VM Resource, `mammos.sensor_material_at_T`, `mammos.sensor_shape_fom`, and a 2-step `WorkflowTemplate` where material outputs wire into the FOM step. `pixi run sensor-demo` creates a queued Optuna campaign; each trial runs the full material -> FOM DAG and reports the FOM Record back to Optuna.

## Stub / in-progress

None currently listed.

The framework does not depend on any example. Swapping the example is an adapter-and-YAML change, not a framework-code change.
