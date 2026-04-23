"""Sensor-specific operations — geometry, micromagnetic loop, figures of merit.

These three operations close the MaMMoS sensor demonstrator chain:
material parameters (from upstream) → free-layer geometry → hysteresis
loop → sensor performance metrics.

Data flow
---------

::

    Ms(T), K1(T), Aex(T)
              │
              ▼
    SensorMesh (a, b, n, thickness) ──► meshed sensor element (Sample)
              │
              ▼
    MicromagneticHysteresis ──► H-M loop (array of (H, M) points)
              │
              ▼
    SensorFigureOfMerit ──► sensitivity, linear_range, Hc, Mr/Ms

The hysteresis operation expects the *temperature-dependent* parameters
— pass ``Ms(T)`` not ``Ms(0)`` from the upstream
:class:`~examples.mammos_sensor.operations.material.FiniteTemperatureMagnetics`
step, or literature values if the material chain was skipped.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from autolab.models import OperationResult, Sample
from autolab.operations.base import Operation, OperationContext

from examples.mammos_sensor._strict import strict_failure, strict_mode
from examples.mammos_sensor.operations.material import _executor_from_ctx
from examples.mammos_sensor.vm import ScriptError, VMError


# ---------------------------------------------------------------------------
# 4. Sensor mesh (superellipse free layer)
# ---------------------------------------------------------------------------


class SensorMesh(Operation):
    """Generate a superellipse free-layer mesh for the sensor element.

    Superellipse: ``|x/a|^n + |y/b|^n ≤ 1``. ``n=2`` is an ellipse,
    ``n→∞`` is a rectangle. The free parameter is the exponent ``n``;
    the sensor designer chooses ``(a, b, n, thickness)`` to tune the
    shape anisotropy contribution.

    MaMMoS backend
        ``discretisedfield`` / ``ubermag`` builds the mesh with the
        chosen cell size. The mesh is serialised to a file inside the
        VM and referenced by path in the Sample metadata so the
        downstream hysteresis step can load it.

    Surrogate
        Computes the closed-form area and enough scalar descriptors to
        feed the surrogate hysteresis model. No mesh file written.
    """

    capability = "mammos.sensor_mesh"
    resource_kind = "vm"
    produces_sample = True
    module = "mammos.sensor_mesh.v0"
    typical_duration = 30

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        a_nm: float = Field(..., gt=0, description="semi-axis along x (nm)")
        b_nm: float = Field(..., gt=0, description="semi-axis along y (nm)")
        n: float = Field(default=2.0, ge=1.5, le=8.0, description="superellipse exponent")
        thickness_nm: float = Field(default=5.0, gt=0, description="film thickness (nm)")
        cell_size_nm: float = Field(default=3.0, gt=0, description="micromagnetic cell edge (nm)")

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        area_nm2: float
        volume_nm3: float
        aspect_ratio: float
        thickness_nm: float
        mesh_path: str | None = None

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)

        try:
            result = vm.run_python(_MAMMOS_MESH_SCRIPT, stdin_payload=parsed.model_dump())
            backend = result.pop("backend_used", "ubermag")
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during mesh generation: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError as exc:
            if strict_mode():
                return strict_failure("SensorMesh", exc)
            result = _surrogate_mesh(parsed)
            backend = "surrogate"

        outputs = {"backend": backend, "thickness_nm": parsed.thickness_nm, **result}
        sample = Sample(
            label=f"sensor-element-{parsed.a_nm:.0f}x{parsed.b_nm:.0f}nm",
            metadata={
                "a_nm": parsed.a_nm,
                "b_nm": parsed.b_nm,
                "n": parsed.n,
                "thickness_nm": parsed.thickness_nm,
                "cell_size_nm": parsed.cell_size_nm,
                "area_nm2": result["area_nm2"],
                "volume_nm3": result["volume_nm3"],
                "mesh_path": result.get("mesh_path"),
                "backend": backend,
            },
        )
        return OperationResult(
            status="completed",
            outputs=outputs,
            new_sample=sample,
        )


# ---------------------------------------------------------------------------
# 5. Micromagnetic hysteresis loop
# ---------------------------------------------------------------------------


class MicromagneticHysteresis(Operation):
    """Compute the H-M hysteresis loop on the meshed sensor element.

    Takes the upstream meshed Sample plus finite-temperature material
    parameters (Ms, K1, A_ex) and sweeps an external field from
    ``-H_max`` to ``+H_max`` and back.

    MaMMoS backend
        ``mammos-mumag`` (finite-element) on the mesh produced by the
        upstream :class:`SensorMesh` step. Real simulation.

    Surrogate
        A Stoner–Wohlfarth-style model: the loop is parametrised by
        ``Ms``, the shape anisotropy derived from the aspect ratio, and
        ``K1``. Gives a physically sensible hysteresis curve including
        the asymmetry induced by non-unit aspect ratio.

    Output
    ------
    The loop is returned as two lists (``H_A_per_m``, ``M_A_per_m``) —
    one entry per field step across the full cycle.
    """

    capability = "mammos.micromagnetic_hysteresis"
    resource_kind = "vm"
    produces_sample = False
    module = "mammos.mumag.v0"
    typical_duration = 900

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        Ms_A_per_m: float
        K1_J_per_m3: float
        Aex_J_per_m: float
        area_nm2: float
        aspect_ratio: float = Field(..., gt=0, description="a/b of the superellipse")
        thickness_nm: float
        mesh_path: str | None = None
        H_max_A_per_m: float = Field(default=8.0e4, gt=0, description="field sweep amplitude (A/m)")
        n_steps: int = Field(default=41, ge=11, le=401, description="steps per branch")

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        H_A_per_m: list[float]
        M_A_per_m: list[float]
        Hc_A_per_m: float  # coercive field (max |H| where M crosses zero on down-sweep)
        Mr_A_per_m: float  # remanence
        H_sweep_max_A_per_m: float

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)

        try:
            result = vm.run_python(_MAMMOS_HYSTERESIS_SCRIPT, stdin_payload=parsed.model_dump())
            # The VM script reports which real backend ran (mammos_mumag or ubermag).
            backend = result.pop("backend_used", "mammos")
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during hysteresis simulation: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError as exc:
            if strict_mode():
                return strict_failure("MicromagneticHysteresis", exc)
            result = _surrogate_hysteresis(parsed)
            backend = "surrogate"

        outputs = {"backend": backend, **result}
        return OperationResult(status="completed", outputs=outputs)


# ---------------------------------------------------------------------------
# 6. Sensor figure of merit
# ---------------------------------------------------------------------------


class SensorFigureOfMerit(Operation):
    """Extract sensor performance metrics from a hysteresis loop.

    Reads the upstream H-M curve and computes:

    - ``sensitivity`` = ``(dM/dH) / Ms`` at ``H=0`` on the ascending branch
    - ``linear_range_T`` — half-width (in Tesla) over which the loop stays
      within ``linearity_tol`` fraction of its linear slope
    - ``Mr_over_Ms`` — remanence squareness
    - ``Hc_A_per_m`` — coercive field, carried through from upstream

    Pure post-processing — no VM call needed. Still runs on the VM
    resource for consistency; the "backend" is always ``"analytic"``.
    """

    capability = "mammos.sensor_fom"
    resource_kind = "vm"
    produces_sample = False
    module = "mammos.sensor_fom.v0"
    typical_duration = 5

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        H_A_per_m: list[float]
        M_A_per_m: list[float]
        Ms_A_per_m: float
        Hc_A_per_m: float | None = None
        Mr_A_per_m: float | None = None
        linearity_tol: float = Field(default=0.05, ge=0.0, le=0.5)

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        sensitivity_per_T: float
        linear_range_T: float
        Mr_over_Ms: float
        Hc_A_per_m: float
        Hc_mT: float

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        fom = _compute_fom(parsed)
        return OperationResult(
            status="completed",
            outputs={"backend": "analytic", **fom},
        )


# ---------------------------------------------------------------------------
# Surrogate implementations
# ---------------------------------------------------------------------------


def _surrogate_mesh(inputs: "SensorMesh.Inputs") -> dict[str, float | str | None]:
    # Closed-form superellipse area: 4ab Γ(1+1/n)² / Γ(1+2/n).
    g1 = math.gamma(1.0 + 1.0 / inputs.n)
    g2 = math.gamma(1.0 + 2.0 / inputs.n)
    area = 4.0 * inputs.a_nm * inputs.b_nm * (g1 * g1) / g2
    volume = area * inputs.thickness_nm
    aspect = inputs.a_nm / max(inputs.b_nm, 1e-9)
    return {
        "area_nm2": area,
        "volume_nm3": volume,
        "aspect_ratio": aspect,
        "mesh_path": None,
    }


def _surrogate_hysteresis(inputs: "MicromagneticHysteresis.Inputs") -> dict[str, Any]:
    """Stoner–Wohlfarth-style closed-form loop.

    Uses Ms + shape anisotropy (from aspect ratio) + K1 to construct a
    loop with a visible coercive field and a linear region around H=0.
    Plausible for sensor-scale soft magnets.
    """
    import numpy as np

    mu0 = 4 * math.pi * 1e-7

    # Shape anisotropy field — simple oblate-ellipsoid approximation.
    # Hk_shape = (Nx - Ny) * Ms  where demag factors depend on aspect ratio.
    r = max(inputs.aspect_ratio, 1e-6)
    nx = 1.0 / (1.0 + r)  # demag factor along short axis (~)
    ny = 1.0 - 1.0 / (1.0 + r)  # along long axis
    hk_shape = max(ny - nx, 0.0) * inputs.Ms_A_per_m
    hk_crystal = 2.0 * inputs.K1_J_per_m3 / max(inputs.Ms_A_per_m, 1.0)
    # Total switching field — clipped into a sane sensor range (≤ ~30 mT).
    hk = min(hk_shape + hk_crystal, inputs.H_max_A_per_m * 0.4)
    hc = hk * 0.15  # empirical coercivity-to-anisotropy scaling

    n = inputs.n_steps
    h_up = np.linspace(-inputs.H_max_A_per_m, inputs.H_max_A_per_m, n)
    h_dn = np.linspace(inputs.H_max_A_per_m, -inputs.H_max_A_per_m, n)

    def branch(h_series: np.ndarray, sign: float) -> np.ndarray:
        # Smooth tanh branch offset by ±hc; approaches ±Ms at saturation.
        return inputs.Ms_A_per_m * np.tanh((h_series - sign * hc) / max(hk, 1.0))

    m_up = branch(h_up, -1.0)  # ascending branch centred at -hc
    m_dn = branch(h_dn, +1.0)  # descending branch centred at +hc

    h = np.concatenate([h_up, h_dn])
    m = np.concatenate([m_up, m_dn])

    # Remanence = |M(H=0)| on the descending branch.
    idx0 = int(np.argmin(np.abs(h_dn)))
    mr = float(abs(m_dn[idx0]))

    return {
        "H_A_per_m": h.tolist(),
        "M_A_per_m": m.tolist(),
        "Hc_A_per_m": float(hc),
        "Mr_A_per_m": mr,
        "H_sweep_max_A_per_m": float(inputs.H_max_A_per_m),
    }


def _compute_fom(inputs: "SensorFigureOfMerit.Inputs") -> dict[str, float]:
    """Analytic extraction of sensor figures of merit from the H-M curve.

    Uses only the ascending branch (small-signal behaviour) when both
    branches are present. Finds ``dM/dH`` at ``H=0`` by local linear fit
    over the nearest ``k=5`` points.
    """
    import numpy as np

    mu0 = 4 * math.pi * 1e-7

    h = np.asarray(inputs.H_A_per_m, dtype=float)
    m = np.asarray(inputs.M_A_per_m, dtype=float)
    ms = float(inputs.Ms_A_per_m)
    if ms <= 0:
        raise ValueError("Ms must be positive to compute sensor FOM")

    n_half = len(h) // 2
    # Ascending branch is the first half (−H_max → +H_max).
    h_asc = h[:n_half]
    m_asc = m[:n_half]

    # Nearest points to H=0.
    order = np.argsort(np.abs(h_asc))
    k = min(5, len(order))
    idx = np.sort(order[:k])
    slope, _ = np.polyfit(h_asc[idx], m_asc[idx], 1)  # dM/dH in 1/(A/m * 1/m)

    # Sensitivity = (dM/dH)/Ms × μ0, so the output carries units of 1/T.
    sensitivity_per_T = float((slope / ms) / mu0)

    # Linear range: largest |μ0 H| where the straight line y = slope*h is within
    # linearity_tol of the measured curve.
    linear_half = 0.0
    for i in range(len(h_asc)):
        predicted = slope * h_asc[i]
        actual = m_asc[i]
        denom = max(abs(predicted), 1e-9)
        if abs(predicted - actual) / denom <= inputs.linearity_tol:
            linear_half = max(linear_half, abs(mu0 * h_asc[i]))
    # mr from loop if not given.
    mr = (
        float(inputs.Mr_A_per_m)
        if inputs.Mr_A_per_m is not None
        else float(abs(m[n_half]) if n_half < len(m) else 0.0)
    )
    hc = float(inputs.Hc_A_per_m) if inputs.Hc_A_per_m is not None else 0.0

    return {
        "sensitivity_per_T": sensitivity_per_T,
        "linear_range_T": float(linear_half),
        "Mr_over_Ms": float(mr / ms),
        "Hc_A_per_m": hc,
        "Hc_mT": float(hc * mu0 * 1e3),
    }


# ---------------------------------------------------------------------------
# VM-side scripts (real mammos)
# ---------------------------------------------------------------------------

_MAMMOS_MESH_SCRIPT = r"""
import json, sys, tempfile
try:
    import discretisedfield as df  # ubermag
    import math
    # Snap half-widths to the cell grid so the Region divides evenly.
    cell_nm = payload["cell_size_nm"]
    a_cells = max(2, math.ceil(payload["a_nm"] / cell_nm))
    b_cells = max(2, math.ceil(payload["b_nm"] / cell_nm))
    a_snap_nm = a_cells * cell_nm
    b_snap_nm = b_cells * cell_nm
    a = a_snap_nm * 1e-9
    b = b_snap_nm * 1e-9
    n = payload["n"]
    thickness = payload["thickness_nm"] * 1e-9
    cell = cell_nm * 1e-9

    region = df.Region(p1=(-a, -b, 0), p2=(a, b, thickness))
    mesh = df.Mesh(region=region, cell=(cell, cell, thickness))

    # Sanity: confirm the mesh was constructible (raises if region doesn't divide).
    _ = mesh.n  # numpy array; touching it confirms the mesh is valid

    g1 = math.gamma(1 + 1 / n)
    g2 = math.gamma(1 + 2 / n)
    area = 4 * payload["a_nm"] * payload["b_nm"] * (g1 * g1) / g2
    volume = area * payload["thickness_nm"]
    aspect = payload["a_nm"] / max(payload["b_nm"], 1e-9)
    print(json.dumps({
        "backend_used": "ubermag",
        "area_nm2": area,
        "volume_nm3": volume,
        "aspect_ratio": aspect,
        "mesh_path": None,   # hysteresis step rebuilds its own mesh from scratch
    }))
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"mammos mesh backend unavailable: {exc!r}\n")
    raise SystemExit(2)
"""


_MAMMOS_HYSTERESIS_SCRIPT = r"""
import json, sys, math

Ms = payload["Ms_A_per_m"]
K1 = payload["K1_J_per_m3"]
Aex = payload["Aex_J_per_m"]
H_max = payload["H_max_A_per_m"]
n_steps = int(payload["n_steps"])
a_nm = math.sqrt(payload["area_nm2"] * payload["aspect_ratio"] / 3.1415926)
b_nm = math.sqrt(payload["area_nm2"] / payload["aspect_ratio"] / 3.1415926)
thickness_nm = payload["thickness_nm"]

# -------- Try mammos-mumag (full MaMMoS stack, finite-element) ------------
try:
    import mammos_mumag as mmag  # type: ignore

    loop = mmag.run_hysteresis(
        mesh_path=payload.get("mesh_path"),
        Ms=Ms, K1=K1, A=Aex, H_max=H_max, n_steps=n_steps,
    )
    print(json.dumps({
        "backend_used": "mammos_mumag",
        "H_A_per_m": list(map(float, loop.H_A_per_m)),
        "M_A_per_m": list(map(float, loop.M_A_per_m)),
        "Hc_A_per_m": float(loop.Hc_A_per_m),
        "Mr_A_per_m": float(loop.Mr_A_per_m),
        "H_sweep_max_A_per_m": float(H_max),
    }))
    raise SystemExit(0)
except ImportError:
    pass
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"mammos_mumag failed: {exc!r}\n")

# -------- Try ubermag + OOMMF (FOSS micromagnetic simulation) --------------
try:
    import discretisedfield as df  # type: ignore
    import micromagneticmodel as mm  # type: ignore
    import oommfc as mc  # type: ignore
    import numpy as np  # type: ignore

    cell_nm = 3.0
    # Snap half-widths to integer multiples of cell_nm so Region divides evenly.
    sx_cells = max(4, math.ceil(a_nm * 1.05 / cell_nm))
    sy_cells = max(4, math.ceil(b_nm * 1.05 / cell_nm))
    sx = sx_cells * cell_nm * 1e-9
    sy = sy_cells * cell_nm * 1e-9
    sz = thickness_nm * 1e-9
    cell_m = cell_nm * 1e-9
    # The z extent is a single cell (thickness).
    region = df.Region(p1=(-sx, -sy, -sz / 2), p2=(sx, sy, sz / 2))
    mesh = df.Mesh(region=region, cell=(cell_m, cell_m, sz))

    # Superellipse indicator — |x/a|^n + |y/b|^n <= 1.
    a_m = a_nm * 1e-9
    b_m = b_nm * 1e-9
    n_exp = 2.5

    def norm_field(point):
        x, y, z = point
        inside = (abs(x) / a_m) ** n_exp + (abs(y) / b_m) ** n_exp <= 1.0
        return Ms if inside else 0.0

    system = mm.System(name="sensor")
    system.energy = (
        mm.Exchange(A=Aex)
        + mm.UniaxialAnisotropy(K=K1, u=(1, 0, 0))
        + mm.Demag()
        + mm.Zeeman(H=(0.0, 0.0, 0.0))
    )
    # discretisedfield 0.90+ renamed dim -> nvdim.
    try:
        system.m = df.Field(mesh, nvdim=3, value=(1, 0.05, 0), norm=norm_field)
    except TypeError:
        system.m = df.Field(mesh, dim=3, value=(1, 0.05, 0), norm=norm_field)

    H_values = np.linspace(H_max, -H_max, n_steps)
    H_values = np.concatenate([H_values, H_values[::-1]])

    md = mc.MinDriver()
    H_rec, M_rec = [], []

    def _avg_mx(field):
        # In modern discretisedfield, a Field with norm=Ms carries values
        # in A/m directly, so mean() already returns an absolute
        # magnetisation. Older releases stored a unit vector and needed
        # multiplying by Ms — we detect which is which by magnitude.
        if hasattr(field, "mean"):
            v = field.mean()
        else:
            v = field.average
        vx = float(v[0] if hasattr(v, "__len__") else v)
        if abs(vx) <= 1.05:
            # Normalised (unit magnitude) convention.
            return vx * Ms
        return vx

    for H in H_values:
        system.energy.zeeman.H = (float(H), 0.0, 0.0)
        md.drive(system)
        Mx = _avg_mx(system.m)
        H_rec.append(float(H))
        M_rec.append(Mx)

    # Derive Hc and Mr from the recorded arrays.
    H_arr = np.asarray(H_rec)
    M_arr = np.asarray(M_rec)
    half = len(H_arr) // 2
    # Descending branch: Hc = |H| where M crosses zero.
    desc_H, desc_M = H_arr[:half], M_arr[:half]
    sign = np.sign(desc_M)
    flips = np.where(np.diff(sign) != 0)[0]
    if len(flips):
        i = int(flips[0])
        x0, x1 = desc_H[i], desc_H[i + 1]
        y0, y1 = desc_M[i], desc_M[i + 1]
        Hc = abs(x0 - y0 * (x1 - x0) / (y1 - y0)) if y1 != y0 else abs(0.5 * (x0 + x1))
    else:
        Hc = 0.0
    idx0 = int(np.argmin(np.abs(desc_H)))
    Mr = float(abs(desc_M[idx0]))

    print(json.dumps({
        "backend_used": "ubermag",
        "H_A_per_m": list(map(float, H_rec)),
        "M_A_per_m": list(map(float, M_rec)),
        "Hc_A_per_m": float(Hc),
        "Mr_A_per_m": float(Mr),
        "H_sweep_max_A_per_m": float(H_max),
    }))
    raise SystemExit(0)
except ImportError as exc:
    sys.stderr.write(f"ubermag stack unavailable: {exc!r}\n")
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"ubermag simulation failed: {exc!r}\n")

# No real backend succeeded — let the host-side surrogate kick in.
raise SystemExit(2)
"""


__all__ = [
    "MicromagneticHysteresis",
    "SensorFigureOfMerit",
    "SensorMesh",
]
