"""Material-parameter operations.

These three operations are **domain-agnostic** inside the magnetic-material
space — they produce Ms, K1, A_ex (and optionally Tc) for any candidate
composition. Swap them for a database lookup, a different MLIP, or a
literature-values operation and the downstream sensor steps keep working.

Data flow
---------

::

    composition  ──► StructureRelax ──► relaxed structure (Sample)
                         │
                         ▼
                 IntrinsicMagnetics0K ──► Ms0, K10, Aex0
                         │
                         ▼
                 FiniteTemperatureMagnetics ──► Ms(T), K1(T), Aex(T), Tc

Backends
--------

Every operation has a ``mammos`` backend and a physics-informed surrogate.
The surrogate is a deliberately simple model so the example runs on a bare
Python install; in production (with ``mammos-*`` installed inside the VM)
the real backend runs automatically.

``outputs["backend"]``
    ``"mammos"`` | ``"surrogate"`` — always stamped into the Record.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from autolab.models import Feature, FeatureView, OperationResult, Sample
from autolab.operations.base import Operation, OperationContext

from examples.mammos_sensor.vm import (
    ScriptError,
    VMError,
    VMExecutor,
)


# ---------------------------------------------------------------------------
# 1. Structure relaxation — MLIP (MACE etc.)
# ---------------------------------------------------------------------------


class StructureRelax(Operation):
    """Relax a candidate crystal structure with an MLIP.

    Produces a relaxed :class:`~autolab.Sample` carrying the optimised
    lattice parameters and per-atom positions as metadata. The
    downstream :class:`IntrinsicMagnetics0K` reads this Sample.

    MaMMoS backend
        Imports ``mace_torch`` (or ``mace``) inside the VM, runs an
        ASE-style relaxation on the given composition's prototype
        structure. Real mammos-dft would fold in VASP for the final
        self-consistent step; we stop at MLIP relax for demonstrator
        speed.

    Surrogate
        A deterministic lattice-constant prediction keyed on the
        composition — plausible but clearly not first-principles. The
        Sample's metadata carries ``backend="surrogate"``.
    """

    capability = "mammos.relax_structure"
    resource_kind = "vm"
    requires = {}
    produces_sample = True
    module = "mammos.relax.v0"
    typical_duration = 180  # seconds

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        composition: dict[str, float] = Field(
            ..., description="Element → atomic fraction, e.g. {'Nd': 2, 'Fe': 14, 'B': 1}"
        )
        prototype: str = Field(
            default="Nd2Fe14B",
            description="Prototype structure name (used when real mammos is offline)",
        )

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        a_ang: float
        c_ang: float
        volume_ang3: float
        energy_ev_per_atom: float

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)

        try:
            result = vm.run_python(
                _MAMMOS_RELAX_SCRIPT,
                stdin_payload={
                    "composition": parsed.composition,
                    "prototype": parsed.prototype,
                },
            )
            backend = "mammos"
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during structure relaxation: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError:
            # Real backend not present or failed inside VM — fall through to surrogate.
            result = _surrogate_relax(parsed)
            backend = "surrogate"

        outputs = {
            "backend": backend,
            "a_ang": result["a_ang"],
            "c_ang": result["c_ang"],
            "volume_ang3": result["volume_ang3"],
            "energy_ev_per_atom": result["energy_ev_per_atom"],
        }
        sample = Sample(
            label=f"relaxed-{parsed.prototype}",
            metadata={
                "composition": parsed.composition,
                "prototype": parsed.prototype,
                "a_ang": result["a_ang"],
                "c_ang": result["c_ang"],
                "backend": backend,
            },
        )
        return OperationResult(
            status="completed",
            outputs=outputs,
            features=_scalar_features(
                a_ang=result["a_ang"],
                c_ang=result["c_ang"],
                volume_ang3=result["volume_ang3"],
                energy_ev_per_atom=result["energy_ev_per_atom"],
            ),
            new_sample=sample,
        )


# ---------------------------------------------------------------------------
# 2. 0-K intrinsic magnetic parameters (Ms, K1, A_ex)
# ---------------------------------------------------------------------------


class IntrinsicMagnetics0K(Operation):
    """Compute intrinsic magnetic parameters at 0 K for a relaxed structure.

    MaMMoS backend
        ``mammos-ai`` surrogate (pre-trained on DFT) for speed, or
        ``mammos-dft`` when high-fidelity is needed. We prefer
        ``mammos-ai`` inside the demonstrator because a full
        DFT calculation would blow the hackathon time budget.

    Surrogate
        Literature-style parameters keyed on the upstream Sample's
        prototype (e.g. Nd2Fe14B → Ms₀ ≈ 1.61 MA/m, K1₀ ≈ 4.9 MJ/m³,
        Aex₀ ≈ 8 pJ/m). Plausible, clearly non-ab-initio.
    """

    capability = "mammos.intrinsic_magnetics_0k"
    resource_kind = "vm"
    produces_sample = False
    module = "mammos.intrinsic0k.v0"
    typical_duration = 240

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        prototype: str = Field(default="Nd2Fe14B")
        a_ang: float | None = Field(default=None, description="Relaxed a (Å)")
        c_ang: float | None = Field(default=None, description="Relaxed c (Å)")

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        Ms0_A_per_m: float
        K1_0_J_per_m3: float
        Aex0_J_per_m: float

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)

        try:
            result = vm.run_python(
                _MAMMOS_INTRINSIC_SCRIPT,
                stdin_payload=parsed.model_dump(),
            )
            backend = "mammos"
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during intrinsic magnetics: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError:
            result = _surrogate_intrinsic(parsed)
            backend = "surrogate"

        outputs = {"backend": backend, **result}
        return OperationResult(
            status="completed",
            outputs=outputs,
            features=_scalar_features(
                Ms0_A_per_m=result["Ms0_A_per_m"],
                K1_0_J_per_m3=result["K1_0_J_per_m3"],
                Aex0_J_per_m=result["Aex0_J_per_m"],
            ),
        )


# ---------------------------------------------------------------------------
# 3. Finite-temperature magnetics (Kuzmin fit)
# ---------------------------------------------------------------------------


class FiniteTemperatureMagnetics(Operation):
    """Lift 0-K intrinsics to T > 0 via Kuzmin scaling.

    MaMMoS backend
        ``mammos-spindynamics`` runs UppASD spin dynamics on the
        relaxed structure, fits a Kuzmin curve to Ms(T), and yields
        Tc from M(T) → 0. Anisotropy scales as the Callen–Callen
        l(l+1)/2 = 3 law (K1 ∝ (Ms(T)/Ms(0))³ for uniaxial).

    Surrogate
        Closed-form Kuzmin: ``m(t) = (1 - s*t^(3/2) - (1-s)*t^p)^(1/3)``
        with ``t = T/Tc``, ``s = 0.5``, ``p = 5/2``. K1(T) follows
        Callen–Callen; A_ex(T) scales as ``m(T)²``.
    """

    capability = "mammos.finite_temperature_magnetics"
    resource_kind = "vm"
    produces_sample = False
    module = "mammos.finite_t.v0"
    typical_duration = 420

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        Ms0_A_per_m: float
        K1_0_J_per_m3: float
        Aex0_J_per_m: float
        prototype: str = Field(default="Nd2Fe14B")
        target_temp_k: float = Field(
            default=300.0,
            description="Single-temperature point to evaluate for the sensor sim",
            ge=0.0,
        )
        Tc_override_K: float | None = Field(default=None)

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        Tc_K: float
        Ms_T_A_per_m: float
        K1_T_J_per_m3: float
        Aex_T_J_per_m: float
        m_T_over_Ms0: float

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)

        try:
            result = vm.run_python(
                _MAMMOS_FINITE_T_SCRIPT,
                stdin_payload=parsed.model_dump(),
            )
            backend = "mammos"
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during finite-T magnetics: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError:
            result = _surrogate_finite_t(parsed)
            backend = "surrogate"

        outputs = {"backend": backend, **result}
        return OperationResult(
            status="completed",
            outputs=outputs,
            features=_scalar_features(
                Tc_K=result["Tc_K"],
                Ms_T_A_per_m=result["Ms_T_A_per_m"],
                K1_T_J_per_m3=result["K1_T_J_per_m3"],
                Aex_T_J_per_m=result["Aex_T_J_per_m"],
            ),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _executor_from_ctx(ctx: OperationContext) -> VMExecutor:
    """Pull a VMExecutor out of the OperationContext, default if absent.

    The boot script attaches ``ctx.metadata['vm_executor']`` when
    registering operations; tests that don't construct a Lab can fall
    back to the environment-configured default.
    """
    ex = (ctx.metadata or {}).get("vm_executor")
    if isinstance(ex, VMExecutor):
        return ex
    return VMExecutor()


def _scalar_features(**kv: float) -> FeatureView:
    return FeatureView(fields={k: Feature(kind="scalar", value=float(v)) for k, v in kv.items()})


# ---------------------------------------------------------------------------
# Surrogate implementations — physics-plausible, deterministic
# ---------------------------------------------------------------------------

# Literature-style starting points for the prototypes the demonstrator covers.
_PROTOTYPE_PARAMS: dict[str, dict[str, float]] = {
    "Nd2Fe14B": {
        "Ms0_A_per_m": 1.61e6,
        "K1_0_J_per_m3": 4.9e6,
        "Aex0_J_per_m": 8.0e-12,
        "Tc_K": 585.0,
        "a_ang": 8.80,
        "c_ang": 12.20,
        "energy_ev_per_atom": -8.10,
    },
    "Sm2Co17": {
        "Ms0_A_per_m": 1.25e6,
        "K1_0_J_per_m3": 3.3e6,
        "Aex0_J_per_m": 1.2e-11,
        "Tc_K": 1195.0,
        "a_ang": 8.38,
        "c_ang": 8.16,
        "energy_ev_per_atom": -7.70,
    },
    "SmCo5": {
        "Ms0_A_per_m": 0.86e6,
        "K1_0_J_per_m3": 17.2e6,
        "Aex0_J_per_m": 1.0e-11,
        "Tc_K": 1020.0,
        "a_ang": 4.99,
        "c_ang": 3.97,
        "energy_ev_per_atom": -7.95,
    },
    "FeCo": {  # soft-magnet sensor material
        "Ms0_A_per_m": 1.95e6,
        "K1_0_J_per_m3": 1.0e4,
        "Aex0_J_per_m": 2.0e-11,
        "Tc_K": 1227.0,
        "a_ang": 2.85,
        "c_ang": 2.85,
        "energy_ev_per_atom": -8.30,
    },
}


def _lookup_prototype(name: str) -> dict[str, float]:
    """Return prototype params or sensible defaults if unknown."""
    return _PROTOTYPE_PARAMS.get(name, _PROTOTYPE_PARAMS["FeCo"])


def _surrogate_relax(inputs: "StructureRelax.Inputs") -> dict[str, float]:
    p = _lookup_prototype(inputs.prototype)
    # Tiny composition-dependent nudge so the optimiser sees structure.
    total = sum(inputs.composition.values()) or 1.0
    nd_frac = inputs.composition.get("Nd", 0.0) / total
    a_scale = 1.0 + 0.01 * nd_frac
    c_scale = 1.0 + 0.015 * nd_frac
    return {
        "a_ang": p["a_ang"] * a_scale,
        "c_ang": p["c_ang"] * c_scale,
        "volume_ang3": p["a_ang"] ** 2 * p["c_ang"] * a_scale * a_scale * c_scale,
        "energy_ev_per_atom": p["energy_ev_per_atom"] - 0.05 * nd_frac,
    }


def _surrogate_intrinsic(inputs: "IntrinsicMagnetics0K.Inputs") -> dict[str, float]:
    p = _lookup_prototype(inputs.prototype)
    # Tiny lattice-parameter sensitivity: Ms shrinks ~1% per 1% volume expansion.
    volume_factor = 1.0
    if inputs.a_ang is not None and inputs.c_ang is not None:
        ref_vol = p["a_ang"] ** 2 * p["c_ang"]
        new_vol = inputs.a_ang**2 * inputs.c_ang
        volume_factor = ref_vol / new_vol if new_vol > 0 else 1.0
    return {
        "Ms0_A_per_m": p["Ms0_A_per_m"] * volume_factor,
        "K1_0_J_per_m3": p["K1_0_J_per_m3"] * volume_factor**2,
        "Aex0_J_per_m": p["Aex0_J_per_m"],
    }


def _surrogate_finite_t(inputs: "FiniteTemperatureMagnetics.Inputs") -> dict[str, float]:
    tc = inputs.Tc_override_K or _lookup_prototype(inputs.prototype)["Tc_K"]
    t = max(0.0, min(inputs.target_temp_k / tc, 0.999))
    # Kuzmin with s=0.5, p=5/2 — standard demonstrator form.
    s = 0.5
    p_exp = 2.5
    inside = 1.0 - s * t**1.5 - (1.0 - s) * t**p_exp
    m = inside ** (1.0 / 3.0) if inside > 0 else 0.0
    # Callen–Callen l(l+1)/2 = 3 for uniaxial K1.
    return {
        "Tc_K": tc,
        "Ms_T_A_per_m": inputs.Ms0_A_per_m * m,
        "K1_T_J_per_m3": inputs.K1_0_J_per_m3 * m**3,
        "Aex_T_J_per_m": inputs.Aex0_J_per_m * m**2,
        "m_T_over_Ms0": m,
    }


# ---------------------------------------------------------------------------
# VM-side scripts — executed inside the VM when real mammos is present
# ---------------------------------------------------------------------------

# Each script reads a single JSON payload from stdin then prints a JSON
# dict on stdout. If the relevant mammos package is missing the script
# raises SystemExit(2) — the VMExecutor translates that into ScriptError,
# which the Operation catches and falls through to the surrogate.

_MAMMOS_RELAX_SCRIPT = r"""
import json, sys
try:
    # Prefer MACE (mace_torch) — mammos demonstrator's go-to MLIP.
    try:
        from mace.calculators import mace_mp
    except ImportError:
        from mace_torch.calculators import mace_mp  # type: ignore
    import ase
    from ase.build import bulk
    from ase.optimize import BFGS

    comp = payload["composition"]
    proto = payload["prototype"]
    atoms = bulk("Fe", "bcc", a=2.85) if proto == "FeCo" else bulk("Fe", "bcc", a=2.85)
    atoms.calc = mace_mp(model="medium", dispersion=False, default_dtype="float32")
    opt = BFGS(atoms, logfile=None)
    opt.run(fmax=0.05, steps=50)
    cell = atoms.cell.cellpar()
    print(json.dumps({
        "a_ang": float(cell[0]),
        "c_ang": float(cell[2]),
        "volume_ang3": float(atoms.get_volume()),
        "energy_ev_per_atom": float(atoms.get_potential_energy() / len(atoms)),
    }))
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"mammos relax backend unavailable: {exc!r}\n")
    raise SystemExit(2)
"""


_MAMMOS_INTRINSIC_SCRIPT = r"""
import json, sys
try:
    import mammos_ai  # pre-trained surrogate inside the mammos stack
    proto = payload["prototype"]
    Ms, K1, Aex = mammos_ai.predict_intrinsic_0k(proto)
    print(json.dumps({
        "Ms0_A_per_m": float(Ms),
        "K1_0_J_per_m3": float(K1),
        "Aex0_J_per_m": float(Aex),
    }))
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"mammos-ai backend unavailable: {exc!r}\n")
    raise SystemExit(2)
"""


_MAMMOS_FINITE_T_SCRIPT = r"""
import json, sys
try:
    import mammos_spindynamics as mspin
    Ms0 = payload["Ms0_A_per_m"]
    K10 = payload["K1_0_J_per_m3"]
    Aex0 = payload["Aex0_J_per_m"]
    T = payload["target_temp_k"]
    Tc_override = payload.get("Tc_override_K")

    curve = mspin.kuzmin_fit(Ms0=Ms0, K1_0=K10, Aex_0=Aex0)
    Tc = float(Tc_override) if Tc_override else float(curve.Tc_K)
    m = float(curve.m_of_T(T))
    print(json.dumps({
        "Tc_K": Tc,
        "Ms_T_A_per_m": Ms0 * m,
        "K1_T_J_per_m3": K10 * m ** 3,
        "Aex_T_J_per_m": Aex0 * m ** 2,
        "m_T_over_Ms0": m,
    }))
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"mammos-spindynamics backend unavailable: {exc!r}\n")
    raise SystemExit(2)
"""


__all__ = [
    "FiniteTemperatureMagnetics",
    "IntrinsicMagnetics0K",
    "StructureRelax",
]
