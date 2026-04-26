"""Sensor shape-optimisation demo operations.

Direct port of the `MaMMoS sensor demonstrator
<https://mammos-project.github.io/mammos/demonstrator/sensor.html>`_ into
the autolab framework. Two Operations, no surrogates:

1. :class:`SensorMaterialAtT` — given a material name in the
   ``mammos_spindynamics`` DB and a target temperature, return the
   temperature-dependent spontaneous magnetisation ``Ms(T)`` and
   exchange stiffness ``A(T)`` from the Kuzmin fit. Uses
   ``mammos_spindynamics`` + ``mammos_analysis.kuzmin_properties``.

2. :class:`SensorShapeFOM` — given ``Ms(T)``, ``A(T)``, an elliptical
   sensor geometry (``sx_nm``, ``sy_nm``, ``thickness_nm``), run an
   OOMMF hysteresis loop via ``ubermag`` / ``oommfc.HysteresisDriver``
   and extract the sensor figure of merit ``Hmax`` (width of the linear
   segment) using ``mammos_analysis.hysteresis.find_linear_segment``.

These run only inside the separate WSL pixi environment described in
``examples/mammos_sensor/README.md``. If the environment is missing the
Operations return a failed Record with a setup hint — **no fallback**.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from autolab.models import OperationResult, Sample
from autolab.operations.base import Operation, OperationContext

from examples.mammos_sensor._strict import strict_failure, strict_mode
from examples.mammos_sensor.operations.material import _executor_from_ctx
from examples.mammos_sensor.operations.sensor import _render_hysteresis_png
from examples.mammos_sensor.vm import ScriptError, VMError


# ---------------------------------------------------------------------------
# Material-at-temperature (mammos_spindynamics DB + Kuzmin fit)
# ---------------------------------------------------------------------------


class SensorMaterialAtT(Operation):
    """Return Ms(T) and A(T) for a material in the mammos DB.

    Inputs: ``material`` (DB key, default ``"Ni80Fe20"``), ``temperature_K``.
    Outputs: ``Ms_A_per_m``, ``A_J_per_m``, plus the inputs echoed.
    """

    capability = "mammos.sensor_material_at_T"
    resource_kind = "vm"
    produces_sample = False
    module = "mammos.sensor_material_at_T.v1"
    typical_duration = 10

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        material: str = Field(default="Ni80Fe20")
        temperature_K: float = Field(default=300.0, gt=0)

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        material: str
        temperature_K: float
        Ms_A_per_m: float
        A_J_per_m: float
        K1_J_per_m3: float = 0.0

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)
        try:
            result = vm.run_python(
                _MATERIAL_AT_T_SCRIPT, stdin_payload=parsed.model_dump()
            )
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during material lookup: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError as exc:
            if strict_mode():
                return strict_failure("SensorMaterialAtT", exc)
            raise
        return OperationResult(
            status="completed",
            outputs={
                "backend": result.get("backend_used", "mammos_spindynamics"),
                "material": parsed.material,
                "temperature_K": parsed.temperature_K,
                "Ms_A_per_m": float(result["Ms_A_per_m"]),
                "A_J_per_m": float(result["A_J_per_m"]),
                "K1_J_per_m3": float(result.get("K1_J_per_m3", 0.0)),
            },
        )


# ---------------------------------------------------------------------------
# Sensor-shape figure of merit (mesh + hysteresis + linear-segment)
# ---------------------------------------------------------------------------


class SensorShapeFOM(Operation):
    """One-shot sensor shape evaluation.

    Given Ms(T), A(T) and an elliptical shape, build the mesh, run the
    OOMMF hysteresis loop, and extract Hmax (the width of the linear
    segment — the sensor FOM).
    """

    capability = "mammos.sensor_shape_fom"
    resource_kind = "vm"
    produces_sample = True
    module = "mammos.sensor_shape_fom.v1"
    typical_duration = 120

    class Inputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        Ms_A_per_m: float
        A_J_per_m: float
        K1_J_per_m3: float = 0.0
        sx_nm: float = Field(..., gt=0, description="ellipse semi-axis along x (nm)")
        sy_nm: float = Field(..., gt=0, description="ellipse semi-axis along y (nm)")
        thickness_nm: float = Field(default=5.0, gt=0)
        region_L_nm: float = Field(default=100.0, gt=0, description="cubic mesh region side (nm)")
        mesh_n: int = Field(default=40, ge=10, le=120, description="cells per in-plane side")
        H_max_mT: float = Field(default=500.0, gt=0)
        n_steps: int = Field(default=101, ge=11, le=401)

    class Outputs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        backend: str
        # Primary FOM: width of linear-response region from a half-sweep
        # along the hard axis (M_y vs H_y starting at H=0).
        Hmax_A_per_m: float
        mu0_Hmax_T: float
        gradient: float
        # Mr is reported as 0.0 — undefined from a half-sweep; kept for
        # schema stability so downstream consumers do not break.
        Mr_A_per_m: float
        # Hysteresis arrays for provenance + plotting (half-sweep).
        H_A_per_m: list[float]
        M_A_per_m: list[float]
        # Echo inputs.
        Ms_A_per_m: float
        K1_J_per_m3: float = 0.0
        sx_nm: float
        sy_nm: float
        thickness_nm: float
        nz_cells: int = 1
        hysteresis_loop_png: str | None = None  # absolute path to rendered PNG

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        parsed = self.Inputs(**inputs)
        vm = _executor_from_ctx(ctx)
        try:
            result = vm.run_python(
                _SHAPE_FOM_SCRIPT, stdin_payload=parsed.model_dump()
            )
        except VMError as exc:
            return OperationResult(
                status="failed",
                error=f"VM unreachable during sensor shape FOM: {exc}",
                failure_mode="equipment_failure",
            )
        except ScriptError as exc:
            if strict_mode():
                return strict_failure("SensorShapeFOM", exc)
            raise

        sample = Sample(
            label=f"sensor-sx{parsed.sx_nm:.0f}nm-sy{parsed.sy_nm:.0f}nm",
            metadata={
                "sx_nm": parsed.sx_nm,
                "sy_nm": parsed.sy_nm,
                "thickness_nm": parsed.thickness_nm,
                "Hmax_A_per_m": float(result["Hmax_A_per_m"]),
                "backend": result.get("backend_used", "ubermag"),
            },
        )
        h_out = [float(x) for x in result["H_A_per_m"]]
        m_out = [float(x) for x in result["M_A_per_m"]]
        png_path = _render_hysteresis_png(
            H=h_out,
            M=m_out,
            Hc=None,
            Mr=float(result.get("Mr_A_per_m", 0.0)),
            record_id=ctx.record_id,
        )
        outputs: dict[str, Any] = {
            "backend": result.get("backend_used", "ubermag"),
            "Hmax_A_per_m": float(result["Hmax_A_per_m"]),
            "mu0_Hmax_T": float(result["mu0_Hmax_T"]),
            "gradient": float(result["gradient"]),
            "Mr_A_per_m": float(result["Mr_A_per_m"]),
            "H_A_per_m": h_out,
            "M_A_per_m": m_out,
            "Ms_A_per_m": parsed.Ms_A_per_m,
            "K1_J_per_m3": parsed.K1_J_per_m3,
            "sx_nm": parsed.sx_nm,
            "sy_nm": parsed.sy_nm,
            "thickness_nm": parsed.thickness_nm,
            "nz_cells": int(result.get("nz_cells", 1)),
            "hysteresis_loop_png": png_path,
        }
        return OperationResult(
            status="completed",
            outputs=outputs,
            new_sample=sample,
        )


# ---------------------------------------------------------------------------
# VM-side scripts (run inside the separate WSL pixi env)
# ---------------------------------------------------------------------------


_MATERIAL_AT_T_SCRIPT = r"""
import json, sys
try:
    import mammos_entity as me
    import mammos_spindynamics
    import mammos_analysis
    import mammos_units as u
    u.set_enabled_equivalencies(u.magnetic_flux_field())

    material = payload["material"]
    T_K = float(payload["temperature_K"])

    results = mammos_spindynamics.db.get_spontaneous_magnetization(material)
    kuz = mammos_analysis.kuzmin_properties(T=results.T, Ms=results.Ms)

    T = me.T(T_K, unit="K")
    A = kuz.A(T)
    Ms = kuz.Ms(T)

    # Magnetocrystalline anisotropy K1(T) — present on the Kuzmin fit when the
    # source material's K1(T) data was loaded; absent for soft-magnet datasets
    # that only ship Ms(T). Default to 0 in that case so shape anisotropy is
    # the only anisotropy and the soft-magnet limit is recovered.
    K1_J_per_m3 = 0.0
    for attr in ("K1", "K"):
        fn = getattr(kuz, attr, None)
        if callable(fn):
            try:
                K1_J_per_m3 = float(fn(T).q.to("J/m^3").value)
                break
            except Exception:
                continue

    print(json.dumps({
        "backend_used": "mammos_spindynamics",
        "Ms_A_per_m": float(Ms.q.to("A/m").value),
        "A_J_per_m": float(A.q.to("J/m").value),
        "K1_J_per_m3": K1_J_per_m3,
    }))
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"sensor material-at-T backend unavailable: {exc!r}\n")
    raise SystemExit(2)
"""


_SHAPE_FOM_SCRIPT = r"""
import json, sys
try:
    import math
    import numpy as np
    import discretisedfield as df
    import micromagneticmodel as mm
    import oommfc as mc
    import mammos_entity as me
    import mammos_units as u
    import mammos_analysis
    u.set_enabled_equivalencies(u.magnetic_flux_field())

    Ms_Apm = float(payload["Ms_A_per_m"])
    A_val  = float(payload["A_J_per_m"])
    K1_val = float(payload.get("K1_J_per_m3", 0.0) or 0.0)
    sx_m = payload["sx_nm"] * 1e-9
    sy_m = payload["sy_nm"] * 1e-9
    t_m = payload["thickness_nm"] * 1e-9
    L_m = payload["region_L_nm"] * 1e-9
    nmesh = int(payload["mesh_n"])
    H_max_mT = float(payload["H_max_mT"])
    n_steps = int(payload["n_steps"])

    mu0 = 4 * math.pi * 1e-7

    # Adaptive z-discretisation: keep the cell size in z below the magnetostatic
    # exchange length, otherwise micromagnetics cannot resolve through-thickness
    # variation (curling, partial vortices) and thick films are silently wrong.
    lex_m = math.sqrt(2.0 * A_val / (mu0 * Ms_Apm * Ms_Apm)) if Ms_Apm > 0 else 5e-9
    nz = max(1, int(round(t_m / lex_m)))

    # Force the in-plane cell counts to be odd so a cell is centered on the
    # origin (0, 0). Any non-degenerate ellipse contains its centre, so the
    # central cell always lies inside the geometry and the simulation is
    # never empty regardless of how small (sx, sy) are relative to the cell.
    if nmesh % 2 == 0:
        nmesh += 1

    region = df.Region(p1=(-L_m/2, -L_m/2, -t_m/2),
                       p2=( L_m/2,  L_m/2,  t_m/2))
    mesh = df.Mesh(region=region, n=(nmesh, nmesh, nz))

    def norm_fn(p):
        x, y, _ = p
        inside = (x/sx_m)**2 + (y/sy_m)**2 <= 1.0
        return Ms_Apm if inside else 0.0

    # Magnetocrystalline anisotropy: align uniaxial K with the geometric long
    # axis (assumed to be x; the search space convention is sx >= sy). When
    # K1 is zero the term contributes nothing, recovering the soft-magnet limit.
    energy = (
        mm.Exchange(A=A_val)
        + mm.Demag()
        + mm.Zeeman(H=(0, 0, 0))
    )
    if abs(K1_val) > 0:
        energy = energy + mm.UniaxialAnisotropy(K=K1_val, u=(1, 0, 0))

    system = mm.System(name="sensor_shape_fom")
    system.energy = energy
    system.m = df.Field(mesh, nvdim=3, value=(1, 0, 0), norm=norm_fn, valid="norm")

    # Half-sweep along the hard axis (y): start at H=0 with m=(1,0,0)
    # (saturated along the long/easy axis x; the search-space convention
    # is sx >= sy), then ramp H_y up to +H_max in n_steps points. M_y(H_y)
    # is the linear sensor response curve; the FOM is the width of the
    # segment that is linear in H_y. A small offset (0.1 mT) along x
    # breaks the symmetry and helps OOMMF converge near H=0.
    Hmin = (0.0, 0.0, 0.0)
    H_pos = ((0.1, +H_max_mT, 0) * u.mT).to(u.A / u.m)
    hd = mc.HysteresisDriver()
    hd.drive(
        system,
        Hsteps=[[Hmin, tuple(H_pos.value), n_steps]],
        verbose=0,
    )

    # Reject degenerate samples — geometry under-resolved so OOMMF ran with
    # M=0 everywhere, and any FOM extracted from that is a measurement
    # artifact rather than physics. (my is normalised to [-1, 1].)
    my_arr = np.asarray(system.table.data["my"].values, dtype=float)
    M_span_frac = float(my_arr.max() - my_arr.min())
    if M_span_frac < 0.05:
        raise RuntimeError(
            f"degenerate sample: |my_max - my_min|={M_span_frac:.3e} "
            f"is below 5% of Ms - geometry likely under-resolved by the mesh "
            f"(sx={payload['sx_nm']}, sy={payload['sy_nm']}, "
            f"t={payload['thickness_nm']}, cell~{payload['region_L_nm']/payload['mesh_n']:.1f} nm)"
        )

    H_y_arr = np.asarray(system.table.data["By_hysteresis"].values, dtype=float)
    H_unit_factor = float(u.Unit(system.table.units["By_hysteresis"]).to(u.A / u.m))
    H_y_arr = H_y_arr * H_unit_factor
    M_y_arr = my_arr * Ms_Apm

    # Linear-region FOM — fit the half-sweep (M_y rises from ~0 at H=0 to
    # +Ms beyond the hard-axis saturation field). find_linear_segment
    # returns the width of the segment that is linear within `margin`.
    H_y_ent = me.H(H_y_arr * (u.A / u.m))
    M_y_ent = me.Entity("Magnetization", M_y_arr * (u.A / u.m))
    res = mammos_analysis.hysteresis.find_linear_segment(
        H_y_ent, M_y_ent,
        margin=0.05 * (Ms_Apm * u.A / u.m), min_points=2,
    )
    Hmax_Apm = float(res.Hmax.value)
    gradient_val = float(res.gradient)

    # Mr is undefined for a half-sweep starting at H=0 with m=(1,0,0)
    # (no descent from saturation on the opposite side). Reported as 0.0
    # for schema stability; do not interpret as physical remanence.
    Mr_Apm = 0.0

    print(json.dumps({
        "backend_used": "ubermag",
        "Hmax_A_per_m": Hmax_Apm,
        "mu0_Hmax_T": Hmax_Apm * mu0,
        "gradient": gradient_val,
        "Mr_A_per_m": Mr_Apm,
        "H_A_per_m": list(map(float, H_y_arr)),
        "M_A_per_m": list(map(float, M_y_arr)),
        "nz_cells": int(nz),
    }))
except Exception as exc:  # noqa: BLE001
    import traceback as _tb
    sys.stderr.write(f"sensor shape-fom backend unavailable: {exc!r}\n{_tb.format_exc()}\n")
    raise SystemExit(2)
"""


__all__ = ["SensorMaterialAtT", "SensorShapeFOM"]
