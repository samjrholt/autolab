# mammos_sensor — MaMMoS sensor demonstrator on autolab

Reimplements the [MaMMoS sensor demonstrator](https://mammos-project.github.io/mammos/demonstrator/sensor.html)
as a set of reusable [`autolab.Operation`](../../src/autolab/operations/base.py)
subclasses running on a **virtual machine** resource, composed into a
[`WorkflowTemplate`](../../src/autolab/models.py) with full hashed
provenance on every step.

## Why this example

This is the flagship end-to-end demonstrator: composition → relaxed
structure → 0-K magnetic parameters → finite-temperature parameters →
sensor mesh → micromagnetic hysteresis → sensor figures of merit. It
exercises every framework seam at once:

| Feature | Where it shows |
|---|---|
| VM as a Resource | [`vm.py`](vm.py) + [`run.py`](run.py) ``_register_vm_resource`` |
| Python-first Operation registration | `lab.register_operation(cls)` for all six ops |
| Reusable WorkflowTemplate with input wiring | [`workflow.py`](workflow.py) |
| Input-mapping between steps | ``input_mappings={"Ms_A_per_m": "finite_t.Ms_T_A_per_m"}`` etc. |
| Failure taxonomy | VM unreachable → `equipment_failure`; script crash → `process_deviation` |
| Surrogate-never-silently-substituted | `outputs["backend"]` stamped on every Record |
| Hashed append-only ledger | `lab.verify_ledger()` at the end |
| BO / Optuna campaign loop | [`campaign.py`](campaign.py) |

## The workflow

```text
composition ──► [StructureRelax] ──► relaxed structure (Sample)
                      │
                      ▼
              [IntrinsicMagnetics0K] ──► Ms₀, K1₀, Aex₀
                      │
                      ▼
       [FiniteTemperatureMagnetics] ──► Ms(T), K1(T), Aex(T), Tc
                      │
                      ▼                    ┌── geometry (a, b, n, t)
                      │                    ▼
                      └──► [MicromagneticHysteresis] ◄── [SensorMesh]
                                  │
                                  ▼
                        [SensorFigureOfMerit] ──► sensitivity, linear range, Hc, Mr/Ms
```

Each step is its **own** Operation class with typed `Inputs` / `Outputs`
Pydantic models — the declaration hash that lands in every Record is
derived from those schemas (not hand-authored YAML), so any change to
a step's interface is a provenance-visible event.

## Reusability — this is the point

The material-parameter steps (`StructureRelax`, `IntrinsicMagnetics0K`,
`FiniteTemperatureMagnetics`) know **nothing about sensors**. They
produce `(Ms, K1, A_ex)` for any candidate magnetic composition. The
sensor-specific steps (`SensorMesh`, `MicromagneticHysteresis`,
`SensorFigureOfMerit`) consume that triple and know nothing about
how it was produced.

Swap `StructureRelax` for a database lookup and the sensor chain keeps
working. Swap `IntrinsicMagnetics0K` for a full DFT calculation instead
of MLIP + `mammos-ai` and the downstream steps are unchanged. The
contract **is** the interface.

## VM as a Resource

The VM is declared to the Lab as a first-class `Resource`:

```python
lab.register_resource(Resource(
    name="vm-primary",
    kind="vm",
    capabilities={
        "reachable": True,
        "python_version": "3.12.3",
        "has_full_mammos_chain": False,   # set by probe_vm()
    },
    description="MaMMoS execution VM: wsl.exe -d Ubuntu-22.04 -- python3",
    asset_id="ubuntu-22.04-wsl",
    typical_operation_durations={
        "mammos.relax_structure": 180,
        "mammos.micromagnetic_hysteresis": 900,
        # …
    },
))
```

Every MaMMoS operation declares `resource_kind = "vm"`, so the
Orchestrator acquires the VM before running the step and releases it
when the step completes. The `typical_operation_durations` values flow
into the scheduler's Gantt ETA so the Console can show realistic
wait-time estimates.

### Running on WSL

On Windows, the default executor uses WSL's default distro:

```bash
pixi run python -m examples.mammos_sensor.run --mode single
```

Override the distro:

```bash
AUTOLAB_VM_DISTRO=Ubuntu-22.04 AUTOLAB_VM_PYTHON=python3.12 \
    pixi run python -m examples.mammos_sensor.run
```

### Running on a remote host (SSH)

```bash
AUTOLAB_VM_KIND=ssh AUTOLAB_VM_SSH_HOST=sam@materials-box.local \
    pixi run python -m examples.mammos_sensor.run
```

### Running fully locally (no WSL)

```bash
AUTOLAB_VM_KIND=local pixi run python -m examples.mammos_sensor.run
```

### Force the surrogate path (for tests / determinism)

```bash
AUTOLAB_MAMMOS_FORCE_SURROGATE=1 pixi run python -m examples.mammos_sensor.run
```

## Backend switching — surrogates never silently substituted

Each operation tries the **highest-fidelity** backend available inside
the VM, then falls back down a chain. Every Record carries
`outputs.backend` naming exactly which backend ran — this is how the
framework invariant *"surrogates are never silently substituted"* is
enforced.

| Step | Real backend (tried first) | Intermediate | Surrogate (fallback) |
|---|---|---|---|
| StructureRelax | `mammos-dft` (not used in demo) | `mace-torch` MLIP | Literature `a`, `c` |
| IntrinsicMagnetics0K | `mammos-dft` | `mammos-ai` pre-trained | Literature Ms₀, K1₀, Aex₀ |
| FiniteTemperatureMagnetics | `mammos-spindynamics` | — | Closed-form Kuzmin |
| SensorMesh | — | `ubermag` / `discretisedfield` | Closed-form area only |
| MicromagneticHysteresis | `mammos-mumag` (FEM) | **`ubermag` + OOMMF** | Stoner–Wohlfarth |
| SensorFigureOfMerit | — (pure analytic) | — | — |

The `DatasetBuilder` export carries `outputs.backend` as a column, and
the run script prints `backend=ubermag` or `backend=surrogate` for
every step at the end of the run.

### Why the ubermag intermediate matters

Full MaMMoS is hard to install (VASP, UppASD, finite-element mesher).
**ubermag + OOMMF is FOSS and pip-installable**, and it will actually
solve the micromagnetic problem — the real thing, not a surrogate. On a
fresh WSL install you can get real hysteresis-loop simulation in ~10
minutes (see install guide below).

## Recommended setup: pixi env inside WSL

The cleanest way to get real backends is a dedicated **pixi project
inside WSL** that autolab activates per call. Autolab has an
`AUTOLAB_VM_PIXI_PROJECT` env var for exactly this — when set, every
VM command is run as ``bash -c 'export PATH=$HOME/.pixi/bin:$PATH && cd <proj> && pixi run python -'``
so the env's bin directory (and therefore OOMMF) ends up on `PATH`.

### One-time WSL setup

```bash
# Inside WSL:
curl -fsSL https://pixi.sh/install.sh | bash
export PATH="$HOME/.pixi/bin:$PATH"

mkdir -p ~/autolab-mammos && cd ~/autolab-mammos
pixi init --channel conda-forge .

# ubermag from conda-forge — brings OOMMF binary automatically.
pixi add "python=3.11.*" pip ubermag

# mammos requires pandas<2.3 (its conda-forge peers pin pandas>=2 so
# lock both before installing the mammos pypi packages).
pixi add "pandas<2.3" "packaging<25"
pixi add --pypi mammos-entity mammos-mumag mammos-spindynamics mammos-ai ase

# (Optional) Install MACE for real MLIP-based StructureRelax — ~2 GB.
# pixi add --pypi mace-torch
```

### Running autolab against this env

From the autolab repo on Windows:

```bash
# Windows Git Bash / PowerShell
AUTOLAB_VM_PIXI_PROJECT=/home/sam/autolab-mammos \
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" \
pixi run python -m examples.mammos_sensor.run --mode single
```

(`MSYS_NO_PATHCONV=1` stops Git Bash from rewriting the Linux path.)

Expected first block:

```text
VM: wsl.exe -d <default> -- python3 (pixi@/home/sam/autolab-mammos)  python=3.11.15
Backend availability:
  mace / mace_torch            [--] NOT INSTALLED                   StructureRelax -> real MLIP
  mammos_ai                    [OK] 0.2.0                           IntrinsicMagnetics0K -> pre-trained DFT surrogate
  mammos_spindynamics          [OK] 0.4.0                           FiniteTemperatureMagnetics -> UppASD + Kuzmin fit
  ubermag (df+mm+oommfc)       [OK] 2025.6                          SensorMesh + MicromagneticHysteresis -> ubermag/OOMMF
  mammos_mumag                 [OK] 0.11.0                          MicromagneticHysteresis -> finite-element (preferred)
  OOMMF (binary or pip)        [OK] /home/sam/autolab-mammos/.pixi/envs/default/bin/oommf  required by ubermag to run OOMMF
```

And the workflow summary should show:

```text
  mesh           completed   backend=ubermag     ...
  hysteresis     completed   backend=ubermag     Hc=21624A/m  Mr=1.32e+06
  fom            completed   backend=analytic    sensitivity=1.494/T  ...
```

That `backend=ubermag` on the hysteresis step is the real OOMMF micromagnetic
simulation — expect ~1-3 minutes per workflow run compared to the
~2 seconds for an all-surrogate run.

## Installing real backends in WSL

When you run `pixi run python -m examples.mammos_sensor.run`, the first
thing printed is the per-backend availability table. If it looks like:

```text
Backend availability:
  mace / mace_torch             ✗ NOT INSTALLED                     StructureRelax → real MLIP
  mammos_ai                     ✗ NOT INSTALLED                     IntrinsicMagnetics0K → pre-trained DFT surrogate
  mammos_spindynamics           ✗ NOT INSTALLED                     FiniteTemperatureMagnetics → UppASD + Kuzmin fit
  ubermag (df+mm+oommfc)        ✗ NOT INSTALLED                     SensorMesh + MicromagneticHysteresis → ubermag/OOMMF
  mammos_mumag                  ✗ NOT INSTALLED                     MicromagneticHysteresis → finite-element (preferred)
  OOMMF binary on PATH          ✗ NOT INSTALLED                     required by ubermag to run OOMMF
```

— everything's running on surrogates. Install the backends you want
inside your WSL distro:

### Minimum for a **real** micromagnetic simulation (recommended start)

```bash
# inside WSL (Ubuntu / Debian):
sudo apt-get update
sudo apt-get install -y tcl tk python3-pip
python3 -m pip install --user ubermag discretisedfield micromagneticmodel oommfc oommf
```

After installation:

```bash
pixi run python -m examples.mammos_sensor.run
# → hysteresis: completed  backend=ubermag
```

The `oommf` pip package ships a pre-built OOMMF binary and puts it on
`PATH` — that's the simplest way to get it working inside WSL. If you
prefer the official distribution, compile from
https://math.nist.gov/oommf/ and point `OOMMFTCL` at `oommf.tcl`.

### MLIP structure relaxation (MACE)

```bash
python3 -m pip install --user mace-torch ase
```

Heavy (~2 GB of torch + CUDA-or-CPU). Speeds up `StructureRelax` from
literature-lookup to a real 50-step BFGS geometry relaxation.

### Full MaMMoS stack

```bash
python3 -m pip install --user mammos-entity mammos-mumag mammos-spindynamics mammos-ai
```

Produces the highest-fidelity path: UppASD-based finite-temperature
magnetics + finite-element micromagnetic hysteresis on an unstructured
mesh. Use this once you have a working MaMMoS install — the
demonstrator will pick it up automatically on the next run.

### Confirming what's running

```bash
pixi run python -m examples.mammos_sensor.run --mode single
```

Read the first block of output (backend availability table) and the
end-of-run summary — each step's `backend=` tells you exactly which
stack answered.

## Running

### One-shot evaluation of a default geometry

```bash
pixi run python -m examples.mammos_sensor.run --mode single
```

Runs the full chain once. Prints a per-step summary with backend, status,
and the characteristic outputs (lattice constants, Ms(T), area, Hc,
sensitivity). Cleanup is automatic; the ledger persists under
`.autolab-runs/mammos-sensor/ledger/`.

### BO optimisation over sensor geometry

```bash
pixi run python -m examples.mammos_sensor.run --mode bo --budget 8
```

Each trial is a full workflow instance with `(a, b, n, thickness)`
chosen by GP-EI Bayesian optimisation. Stops early when the acceptance
gate (sensitivity ≥ 1.5/T AND linear range ≥ 5 mT) passes.

### Optuna loop

```bash
pixi run python -m examples.mammos_sensor.run --mode optuna --sampler tpe
```

Same shape, TPE / CMA-ES / GP / random sampler inside Optuna.

## Files

| File | What it is |
|---|---|
| [`vm.py`](vm.py) | WSL / local / SSH VM executor with capability probe |
| [`operations/material.py`](operations/material.py) | Relax / 0K / finite-T operations |
| [`operations/sensor.py`](operations/sensor.py) | Mesh / hysteresis / FOM operations |
| [`workflow.py`](workflow.py) | `MAMMOS_SENSOR_WORKFLOW` template |
| [`campaign.py`](campaign.py) | Campaign specs + Planner factories |
| [`run.py`](run.py) | Lab boot script with three modes |

## Reading the ledger

After a run:

```python
from autolab import Lab
from autolab.dataset import DatasetBuilder

lab = Lab(".autolab-runs/mammos-sensor", lab_id="lab-mammos-sensor")
df = DatasetBuilder(lab.ledger).only_completed().to_dataframe()
# Every step of every trial is one row.
# Columns include inputs.*, outputs.*, features.*, decision.*,
# resource_name, resource_asset_id, tool_declaration_hash, checksum.
```

The ledger is append-only, hashed per Record (SHA-256), and dual-written
to SQLite + JSONL under the lab root. `lab.verify_ledger()` recomputes
every checksum and returns a list of any tampered Records (empty list = OK).
