# sensor_shape_opt — Claude-vs-BO shape optimisation

Reimplements the [MaMMoS sensor demonstrator](https://mammos-project.github.io/mammos/demonstrator/sensor.html)
as an autolab Campaign, with **Claude Opus 4.7 vision** replacing
Bayesian optimisation as the PolicyProvider. The hero demo beat is
running both side-by-side: Claude converges in fewer iterations by
*seeing when the scalar objective is lying* (pinched loops, noisy
fits, unphysical tails) — BO can't, because BO only sees the scalar.

## What the workflow does

Optimise the diagonals `(sx, sy)` of a diamond-shaped Ni80Fe20 sensor
element to maximise the size of the linear region (`Hmax`) in its M-H
loop at 300 K.

```
ms_temperature_lookup  ────►  T, Ms arrays            (once per material)
        │
        ▼
   kuzmin_properties  ──────►  A(T), Tc, Ms(T)         (once per material/T)
        │
        ▼                         ┌──── PolicyProvider picks (sx, sy)
        └── loop:                 │
            sensor_simulate   ◄───┤     (ubermag + OOMMF hysteresis, ~5s)
                │                 │
                ▼                 │
            find_linear_segment ──┤     (mammos-analysis extraction)
                │                 │
                ▼                 │
            sensor_interpret ─────┤     (Claim: Hmax estimate, loop_quality,
                │                       confidence, suggested next point)
                ▼                 │
            react()   ◄───────────┘     Action: add_step(sx', sy') or accept/stop
```

Each `sensor_interpret` Claim integrates **both**:

1. The numerical scalars from `mammos-analysis.find_linear_segment` —
   `Hmax`, `Mr`, `gradient`, linear-segment bounds, margin flags.
2. The rendered hysteresis loop PNG itself — Claude checks for
   pinching, noise, unphysical tails. This is how the Claim's
   `loop_quality` field gets filled, and why Claude can see when BO
   would be fooled.

## Status

Scaffolded per
[docs/superpowers/specs/2026-04-22-onboarding-and-remote-execution-design.md](../../docs/superpowers/specs/2026-04-22-onboarding-and-remote-execution-design.md).
The pack's adapter code and Capability YAMLs are the subsystem-4 build;
this directory contains the `pack.yaml` metadata and this README as
the landing spec. The existing `examples/mammos_sensor/` pack remains
available as the multiscale chain demo.

## Planned capabilities

| Capability | Wraps | Notes |
|---|---|---|
| `ms_temperature_lookup` | `mammos_spindynamics.db.get_spontaneous_magnetization` | Cheap DB lookup per material. |
| `kuzmin_properties` | `mammos_analysis.kuzmin_properties` | One call per campaign. |
| `sensor_simulate` | `ubermag` + OOMMF | Diamond geometry → hysteresis loop. ~5 s / call. |
| `find_linear_segment` | `mammos_analysis.hysteresis.find_linear_segment` | Scalar extraction. |
| `sensor_interpret` | Claude Opus 4.7 vision | Interpretation Capability — returns a Claim Record. |

## Planned PolicyProviders

Two interchangeable, selected in the Campaign's Config tab:

- **`ClaudeVisionPolicy`** — reads the last hysteresis PNG + scalar
  history, returns `Action(add_step, {sx, sy})` with a `reason`
  string persisted to the Record's `decision` field.
- **`BOPolicy`** — wraps `bayesian-optimization.BayesianOptimization`
  with the same `(sx, sy) → Hmax` objective. Provided for the
  comparative demo.

Stop condition in both cases: `Hmax ≥ 500_000 A/m` (acceptance gate)
or budget exceeded.

## Installing

Once implemented, the pack is installable via the Setup Assistant or
via CLI:

```bash
autolab register tool examples/sensor_shape_opt/capabilities/*.yaml
```

The Assistant will also detect this pack at `examples/sensor_shape_opt/`
during its "Step 3 — Capability authoring" phase and offer to install
it alongside or instead of authoring from scratch.
