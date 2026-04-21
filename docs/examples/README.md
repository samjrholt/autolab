# Example workflows

Documented end-to-end workflows that run on top of the framework. Each example is a registered set of Operations + Tool YAMLs + optional Skills, plus a narrative document explaining what it does and why.

Planned entries:

- `mammos-hard-magnet.md` — a multiscale hard-magnet pipeline. MLIP structure relaxation → `mammos-dft` intrinsic parameters → `mammos-spindynamics` finite-temperature (Kuzmin) → `mammos-mumag` finite-element hysteresis → coercivity Hc. See [docs/design/scenarios.md §8](../design/scenarios.md) for the framework pressure test and [CLAUDE.md "First cool example workflow"](../../CLAUDE.md) for the motivation.

The framework does not depend on any example. Swapping the example is an adapter-and-YAML change, not a framework-code change.
