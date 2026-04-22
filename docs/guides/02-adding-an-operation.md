# Adding an Operation

An `Operation` is the atomic unit of work — one step the Orchestrator
runs, surrounded by the provenance contract. Operations never write
Records themselves.

autolab supports two registration paths. **Prefer the Python-first one**
unless you are wrapping a tool that genuinely has no Python adapter.

## Python-first (recommended)

Subclass `Operation`, declare a few class attributes, implement
`async def run`, and register the class.

```python
from pydantic import BaseModel, Field

from autolab import Lab
from autolab.models import OperationResult
from autolab.operations.base import Operation


class TubeFurnaceSinter(Operation):
    capability    = "sinter"          # capability-named, not library-named
    resource_kind = "tube_furnace"
    requires      = {"max_temp_k": {">=": 1300}}
    module        = "sinter.v1.0"     # stamped into every Record
    produces_sample = True
    destructive     = True
    typical_duration = 7200            # seconds — used for Gantt ETAs

    class Inputs(BaseModel):
        temp_k:   float = Field(..., ge=600, le=1400)
        time_min: float = Field(..., ge=10, le=480)
        atmosphere: str = "Ar"

    class Outputs(BaseModel):
        grain_size_nm: float
        densification: float

    async def run(self, inputs: dict) -> OperationResult:
        # Run the instrument. Return a structured result.
        grain = await _hardware_sinter(**inputs)
        return OperationResult(
            outputs={"grain_size_nm": grain, "densification": 0.98},
        )


lab = Lab("./.autolab-runs/my-lab")
lab.register_operation(TubeFurnaceSinter)
```

### What the framework derives for you

- `declaration_hash` — SHA-256 of the canonical schema (capability,
  version, requires, inputs schema, outputs schema, module). Changes
  the moment you edit any of those attributes; stamped into every
  Record.
- Duration estimates — `typical_duration` is the fallback for ETA
  projections until the `EstimationEngine` has enough historical samples.

### Rules

- `capability` is a noun, scientist-shaped — `magnetometry`,
  `pxrd_interpret`, `slurm_dft`. Not a library name. One-way door.
- `run()` must be idempotent given the same inputs. Randomness goes
  through a seed in the `Session` snapshot.
- Do not write to the Ledger from inside `run()`. Return an
  `OperationResult`; the Orchestrator wraps the record for you.
- Raise a plain exception on an instrument fault — the Orchestrator
  classifies it as `equipment_failure` and the `HeuristicPolicyProvider`
  will retry.

### Self-declared failure modes

If your Operation ran but the result is unreliable (bad measurement, off-
target synthesis), set `failure_mode` on the result:

```python
return OperationResult(
    status="failed",
    failure_mode="measurement_rejection",
    error="weak signal",
)
```

See [docs/design/autolab-ideas-foundation.md](../design/autolab-ideas-foundation.md)
for the full failure taxonomy.

## YAML / external-adapter path

For CLI tools or proprietary binaries you don't want to wrap in a
Python class, write a YAML declaration:

```yaml
# my_tool.yaml
name: pxrd
capability: pxrd
version: "0.1.0"
module: pxrd.v1
resource: xrd_diffractometer
requires: {max_two_theta_deg: {">=": 140}}
inputs:
  sample_id: {kind: string}
  scan_minutes: {kind: scalar}
outputs:
  pattern_csv: {kind: pointer}
  peak_list: {kind: scalar}
adapter: my_package.adapters:RunPxrd
produces_sample: false
destructive: false
typical_duration_s: 1200
```

The `adapter` value is `module:attribute` — it must resolve to an
`Operation` subclass. Register via:

```bash
curl -X POST http://localhost:8000/tools/register-yaml \
  -H 'content-type: application/json' \
  --data-binary @my_tool.yaml   # JSON body; the server also accepts YAML-shaped JSON.
```

or in Python: `lab.register_tool("my_tool.yaml")`.

## Seeing what's registered

```bash
curl http://localhost:8000/tools | jq
```

The Console's *Duration estimates* panel lists every registered tool
with its declared and measured durations.

## Anti-patterns

- **Library-named capabilities.** Don't call a capability
  `ubermag_hysteresis`; call it `hysteresis` and let the `module`
  string carry `ubermag.v0.1`.
- **Silent surrogate substitution.** If your adapter falls back to a
  cheaper surrogate, tag the `module` string accordingly
  (e.g. `hysteresis-surrogate.v0.1`). The Ledger should tell the
  scientist which backend actually ran.
- **Mutating `inputs` inside `run()`.** The same dict goes into the
  Record's `inputs` field — if you mutate it, the hash no longer matches
  what the scientist requested.
