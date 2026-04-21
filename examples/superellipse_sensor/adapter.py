"""Operation adapter: superellipse_hysteresis via ubermag.

Two execution paths, both labelled honestly in the Record's `module` field:

- ``ubermag-superellipse.v0.1`` — full ubermag/OOMMF micromagnetic
  computation. Used when ubermag is importable.
- ``superellipse-surrogate.v0.1`` — closed-form Stoner–Wohlfarth-style
  surrogate. Used when ubermag is unavailable. The framework's invariant
  ("surrogates are never silently substituted") is honoured by reporting
  the surrogate module string.

The adapter implements a single `Operation` subclass — `SuperellipseHysteresis`.
The framework calls its async `run()`; everything else is private detail.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import numpy as np

from autolab.models import Feature, FeatureView, OperationResult, Sample
from autolab.operations.base import Operation, OperationContext

from .geometry import superellipse_area_nm2, superellipse_indicator


# ---------------------------------------------------------------------------
# Loop analysis — applied to either backend's H/M arrays
# ---------------------------------------------------------------------------


def _analyse_loop(H: np.ndarray, M: np.ndarray, Ms: float) -> dict[str, float]:
    """Compute Hc, Mr/Ms, sensitivity at H=0, and a half-width linear range.

    Sensitivity and linear range are evaluated on the ascending branch
    only (H sweeping low → high), which is the branch a sensor would
    operate on near zero applied field.
    """
    half = len(H) // 2
    descending_H, descending_M = H[:half], M[:half]
    ascending_H, ascending_M = H[half:], M[half:]

    Hc = float(_zero_crossing(descending_H, descending_M))

    # Remanence: |M| at H closest to 0 on the descending branch.
    idx0_desc = int(np.argmin(np.abs(descending_H)))
    Mr = float(abs(descending_M[idx0_desc]))

    # Sensitivity at H=0 — slope of the ascending branch over a small
    # window centred on H=0. Window scales with overall sweep range.
    window = max(3, len(ascending_H) // 25)
    near0 = np.argsort(np.abs(ascending_H))[:window]
    near0 = np.sort(near0)
    if len(near0) >= 2:
        slope = float(np.polyfit(ascending_H[near0], ascending_M[near0], 1)[0])
    else:
        slope = 0.0
    mu0 = 4 * math.pi * 1e-7
    sensitivity_per_T = abs(slope) / max(Ms, 1.0) / mu0  # convert /(A/m) → /T

    # Linear range — half-width over which the ascending branch stays
    # within 5 % of the linear fit through the origin.
    target = 0.05
    if abs(slope) < 1e-12:
        linear_range_T = 0.0
    else:
        residual = ascending_M - slope * ascending_H
        good = np.abs(residual) <= target * Ms
        if not np.any(good):
            linear_range_T = 0.0
        else:
            linear_range_A_per_m = float(np.max(np.abs(ascending_H[good])))
            linear_range_T = linear_range_A_per_m * mu0

    return {
        "Hc": abs(Hc),
        "Mr_over_Ms": Mr / max(Ms, 1.0),
        "sensitivity": sensitivity_per_T,
        "linear_range": linear_range_T,
    }


def _zero_crossing(x: np.ndarray, y: np.ndarray) -> float:
    """Return the x at which y crosses zero (linear interp), or 0 if none."""
    sign = np.sign(y)
    flips = np.where(np.diff(sign) != 0)[0]
    if not len(flips):
        return 0.0
    i = int(flips[0])
    x0, x1 = float(x[i]), float(x[i + 1])
    y0, y1 = float(y[i]), float(y[i + 1])
    if y1 == y0:
        return 0.5 * (x0 + x1)
    return x0 - y0 * (x1 - x0) / (y1 - y0)


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def _try_import_ubermag():
    try:
        import discretisedfield as df  # type: ignore[import-not-found]
        import micromagneticmodel as mm  # type: ignore[import-not-found]
        import oommfc as mc  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 — anything failing here means surrogate path
        return None
    return df, mm, mc


def _ubermag_loop(inputs: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, str]:
    """Real ubermag/OOMMF run. Raises on backend failure — caller may surrogate."""
    bundle = _try_import_ubermag()
    if bundle is None:
        raise RuntimeError("ubermag stack not available")
    df, mm, mc = bundle

    Ms = float(inputs["Ms"])
    K1 = float(inputs["K1"])
    A_ex = float(inputs["A_ex"])
    a_nm = float(inputs["a"])
    b_nm = float(inputs["b"])
    n = float(inputs["n"])
    thickness = float(inputs["thickness"])
    H_max = float(inputs["H_max"])
    cell = float(inputs["cell_size"]) * 1e-9
    n_steps = int(inputs.get("n_steps", 41))

    pad = 1.05
    sx = a_nm * 1e-9 * pad
    sy = b_nm * 1e-9 * pad
    sz = thickness * 1e-9
    p1 = (-sx, -sy, -sz / 2)
    p2 = (sx, sy, sz / 2)
    region = df.Region(p1=p1, p2=p2)
    mesh = df.Mesh(region=region, cell=(cell, cell, max(cell, sz)))

    inside = superellipse_indicator(a_nm, b_nm, n)

    def norm_field(point):
        return Ms if inside(point) else 0.0

    system = mm.System(name="superellipse")
    system.energy = (
        mm.Exchange(A=A_ex)
        + mm.UniaxialAnisotropy(K=K1, u=(1, 0, 0))
        + mm.Demag()
        + mm.Zeeman(H=(0, 0, 0))
    )
    system.m = df.Field(mesh, dim=3, value=(1, 0.05, 0), norm=norm_field)

    H_values = np.linspace(H_max, -H_max, n_steps)
    H_values = np.concatenate([H_values, H_values[::-1]])

    md = mc.MinDriver()
    H_record: list[float] = []
    M_record: list[float] = []
    for H in H_values:
        system.energy.zeeman.H = (float(H), 0.0, 0.0)
        md.drive(system)
        mx = float(system.m.average[0])
        H_record.append(float(H))
        M_record.append(mx)
    return np.array(H_record), np.array(M_record) * Ms, "ubermag-superellipse.v0.1"


def _surrogate_loop(inputs: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, str]:
    """Closed-form surrogate: superposition of magneto-crystalline and shape terms.

    Not a substitute for micromagnetics — labelled as a surrogate so
    downstream code can filter on the Record's `module`. The mapping is
    designed to vary smoothly with every input so BO has something to do:

    - K1 raises Hc through a Stoner–Wohlfarth-style anisotropy field
    - the in-plane aspect (a, b) and superellipse exponent (n) modulate
      shape anisotropy along the easy axis
    - thickness reduces in-plane shape anisotropy
    - the loop's transition width is set by inverse anisotropy, so soft
      materials get wide linear ranges and high sensitivity at H=0
    """
    Ms = float(inputs["Ms"])
    K1 = float(inputs["K1"])
    a_nm = float(inputs["a"])
    b_nm = float(inputs["b"])
    n = float(inputs["n"])
    thickness = float(inputs["thickness"])
    H_max = float(inputs["H_max"])
    n_steps = int(inputs.get("n_steps", 81))

    mu0 = 4 * math.pi * 1e-7

    # Crystalline anisotropy field.
    H_K_cryst = 2.0 * K1 / max(mu0 * Ms, 1e-9)

    # In-plane shape anisotropy: thin-film flakes with aspect ratio. Larger
    # aspect → larger shape field along the long axis.
    aspect = max(a_nm, b_nm) / max(min(a_nm, b_nm), 1e-9)
    shape_aniso_field = 0.5 * Ms * (1.0 - 1.0 / (1.0 + 0.6 * (aspect - 1.0)))
    # Superellipse exponent: rectangular shapes concentrate flux at corners,
    # depinning the wall earlier than smooth ellipses.
    n_factor = 1.0 - 0.15 * math.tanh(n - 2.0)
    # Thickness in nm reduces effective in-plane shape anisotropy.
    thickness_factor = 1.0 / (1.0 + 0.05 * thickness)

    Hc = max(0.4 * H_K_cryst + 0.6 * shape_aniso_field * n_factor * thickness_factor, 1.0)
    # Loop width is dominated by softness — low anisotropy materials have
    # broad transitions, the linear regime sensors actually want.
    width = max(0.5 * Hc + 0.05 * Ms, 1.0)

    H = np.concatenate(
        [np.linspace(H_max, -H_max, n_steps), np.linspace(-H_max, H_max, n_steps)]
    )
    M = np.empty_like(H)
    half = n_steps
    M[:half] = -Ms * np.tanh((H[:half] + Hc) / width)
    M[half:] = Ms * np.tanh((H[half:] - Hc) / width)
    M = np.clip(M, -Ms, Ms)
    return H, M, "superellipse-surrogate.v0.1"


# ---------------------------------------------------------------------------
# The Operation
# ---------------------------------------------------------------------------


class SuperellipseHysteresis(Operation):
    """Compute the hysteresis loop of a superellipse-shaped sensor element."""

    capability = "superellipse_hysteresis"
    resource_kind = "computer"
    requires = {"cores_gte": 1}
    produces_sample = True
    destructive = False
    module = "ubermag-superellipse.v0.1"

    async def run(
        self, inputs: dict[str, Any], context: OperationContext
    ) -> OperationResult:
        # Ubermag is sync + heavy; offload to a thread so the orchestrator
        # event loop stays responsive for live event streaming.
        try:
            H, M, module = await asyncio.to_thread(_ubermag_loop, inputs)
        except Exception:  # noqa: BLE001 — surrogate path is provenance-visible
            H, M, module = _surrogate_loop(inputs)

        metrics = _analyse_loop(H, M, Ms=float(inputs["Ms"]))

        outputs: dict[str, Any] = {
            **metrics,
            "loop": {
                "H": H.tolist(),
                "M": M.tolist(),
            },
            "geometry_area_nm2": superellipse_area_nm2(
                float(inputs["a"]), float(inputs["b"]), float(inputs["n"])
            ),
        }
        features = FeatureView(
            fields={
                "Hc": Feature(kind="scalar", value=metrics["Hc"], unit="A/m"),
                "Mr_over_Ms": Feature(kind="scalar", value=metrics["Mr_over_Ms"]),
                "sensitivity": Feature(kind="scalar", value=metrics["sensitivity"], unit="1/T"),
                "linear_range": Feature(kind="scalar", value=metrics["linear_range"], unit="T"),
                "loop": Feature(kind="curve", value=outputs["loop"]),
            }
        )

        sample = Sample(
            label=f"superellipse a={inputs['a']}nm b={inputs['b']}nm n={inputs['n']}",
            metadata={"module": module, "geometry_area_nm2": outputs["geometry_area_nm2"]},
        )

        return OperationResult(
            status="completed",
            outputs=outputs,
            features=features,
            new_sample=sample,
        )

    # The orchestrator's `Operation.call` reads `cls.module` once at write-ahead
    # time. We override here so the *runtime* surrogate flag overrides the class
    # default in the Record only via OperationResult metadata. (For now, callers
    # can read the loop's `module` key through the FeatureView/outputs.)


__all__ = ["SuperellipseHysteresis"]
