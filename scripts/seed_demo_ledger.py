"""Seed the autolab Ledger with plausible prior-run history for the hackathon demo.

Writes 18 Records covering 4 narrative threads that Claude can cite by hash
during the live demo:

  A  Successful Permalloy sensor run (3 days ago) — baseline good design.
  B  Nd2Fe14B FAILURE as a sensor free layer (2 days ago) — square loop, FoM≈0.
     This is the key "recognisable anomaly" Claude should cite when it sees
     another square loop: "Record 0xXXXX showed the same square hysteresis..."
  C  Too-small aspect-ratio Permalloy sensor then a rerun that worked (2 days ago).
  D  Dy-substitution overshoot — 25% Dy crashed Ms below target (1 day ago).
  E  Human intervention note (1 day ago): "restrict Ms > 1 MA/m".

Expected citation hints (printed at the end of this script):
  - The Nd2Fe14B square-loop record is the #1 citation target.
  - The Dy-overshoot record motivates "try 5–10% Dy instead".
  - The human-intervention record motivates the Ms constraint.

Usage
-----
    python scripts/seed_demo_ledger.py [--lab-root VAR_DIR] [--campaign-id ID] [--reset]

Defaults:
  --lab-root   var/demo_lab
  --campaign-id  demo-campaign-seed-1
  --reset      Drop and recreate the lab root before seeding.
"""

from __future__ import annotations

import argparse
import base64
import math
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── ensure the repo root is on sys.path ────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
    sys.path.insert(0, str(_REPO / "src"))

from autolab.lab import Lab
from autolab.models import Record


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "demo-campaign-seed-1"
SESSION_ID = "seed-session-001"
LAB_ROOT_DEFAULT = str(_REPO / "var" / "demo_lab")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(days_ago: float, hour: int = 10, minute: int = 0) -> datetime:
    now = datetime.now(tz=timezone.utc)
    return (now - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def _make_record(
    lab_id: str,
    operation: str,
    inputs: dict,
    outputs: dict,
    *,
    status: str = "completed",
    failure_mode: str | None = None,
    decision: dict | None = None,
    created_at: datetime,
    parent_ids: list[str] | None = None,
    tags: list[str] | None = None,
    module: str = "surrogate.v0",
    resource_kind: str = "vm",
) -> Record:
    return Record(
        lab_id=lab_id,
        campaign_id=CAMPAIGN_ID,
        session_id=SESSION_ID,
        operation=operation,
        module=module,
        resource_kind=resource_kind,
        inputs=inputs,
        outputs=outputs,
        record_status=status,  # type: ignore[arg-type]
        failure_mode=failure_mode,  # type: ignore[arg-type]
        decision=decision or {},
        created_at=created_at,
        finalised_at=created_at + timedelta(seconds=30),
        tags=tags or [],
        parent_ids=parent_ids or [],
    )


def _render_hysteresis_png(H: list, M: list, Hc: float, Mr: float, label: str) -> str | None:
    """Render a hysteresis loop PNG, return path or None if matplotlib missing."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    mu0 = 4 * math.pi * 1e-7
    H_mT = [h * mu0 * 1e3 for h in H]
    M_kA = [m * 1e-3 for m in M]
    Hc_mT = Hc * mu0 * 1e3
    Mr_kA = Mr * 1e-3

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    ax.plot(H_mT, M_kA, color="#1f77b4", linewidth=1.8)
    ax.axhline(0, color="k", linewidth=0.6, linestyle="--", alpha=0.5)
    ax.axvline(0, color="k", linewidth=0.6, linestyle="--", alpha=0.5)
    if abs(Hc_mT) > 0.001:
        ax.annotate(f"Hc={Hc_mT:.2f} mT", xy=(Hc_mT, 0),
                    xytext=(Hc_mT * 2 + 0.1, max(M_kA) * 0.2),
                    fontsize=9, color="#d62728",
                    arrowprops={"arrowstyle": "->", "color": "#d62728"})
    if abs(Mr_kA) > 0.001:
        ax.annotate(f"Mr={Mr_kA:.1f} kA/m", xy=(0, Mr_kA),
                    xytext=(max(H_mT) * 0.3, Mr_kA * 1.2),
                    fontsize=9, color="#2ca02c",
                    arrowprops={"arrowstyle": "->", "color": "#2ca02c"})
    ax.set_xlabel(r"$\mu_0 H$ (mT)", fontsize=12)
    ax.set_ylabel(r"$M$ (kA/m)", fontsize=12)
    ax.set_title(f"Hysteresis — {label}", fontsize=11)
    ax.grid(True, linewidth=0.4, alpha=0.4)
    fig.tight_layout()

    out_dir = Path(tempfile.gettempdir()) / "autolab_artefacts" / f"seed-{label.replace(' ', '_')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "hysteresis.png"
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _soft_loop(Ms: float, Hc_frac: float, H_max: float, n: int = 41):
    """Soft-magnet tanh loop (for Permalloy-like materials)."""
    import math
    Hk = Hc_frac * H_max
    Hc = Hk * 0.15
    pts = n
    h_up = [H_max * (2 * i / (pts - 1) - 1) for i in range(pts)]
    h_dn = list(reversed(h_up))
    m_up = [Ms * math.tanh((h + Hc) / max(Hk, 1.0)) for h in h_up]
    m_dn = [Ms * math.tanh((h - Hc) / max(Hk, 1.0)) for h in h_dn]
    H = h_up + h_dn
    M = m_up + m_dn
    # Mr = M(H=0) on descending branch
    mid = pts // 2
    Mr = abs(m_dn[mid])
    return H, M, float(Hc), float(Mr)


def _square_loop(Ms: float, Hc: float, H_max: float, n: int = 41):
    """Near-square loop for hard magnets (sign-flip approximation)."""
    import math
    pts = n
    h_up = [H_max * (2 * i / (pts - 1) - 1) for i in range(pts)]
    h_dn = list(reversed(h_up))
    sharpness = 20.0 / max(abs(Hc), 1.0)
    m_up = [Ms * math.tanh(sharpness * (h + Hc)) for h in h_up]
    m_dn = [Ms * math.tanh(sharpness * (h - Hc)) for h in h_dn]
    H = h_up + h_dn
    M = m_up + m_dn
    mid = pts // 2
    Mr = abs(m_dn[mid])
    return H, M, float(Hc), float(Mr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(lab: Lab) -> list[Record]:
    lid = lab.lab_id
    records: list[Record] = []

    def append(r: Record) -> Record:
        saved = lab.ledger.append_sync(r)
        records.append(saved)
        return saved

    # ------------------------------------------------------------------ #
    # Thread A — Permalloy baseline success (3 days ago)
    # ------------------------------------------------------------------ #
    r_a1 = append(_make_record(lid, "mammos.relax_structure",
        inputs={"composition": {"Ni": 80, "Fe": 20}, "prototype": "Permalloy"},
        outputs={"backend": "surrogate", "a_ang": 3.54, "c_ang": 3.54,
                 "volume_ang3": 44.4, "energy_ev_per_atom": -4.90,
                 "composition": {"Ni": 80, "Fe": 20}},
        created_at=_dt(3.0, 9, 0), tags=["thread:A", "material:Permalloy"],
    ))

    r_a2 = append(_make_record(lid, "mammos.intrinsic_magnetics_0k",
        inputs={"prototype": "Permalloy", "a_ang": 3.54, "c_ang": 3.54,
                "composition": {"Ni": 80, "Fe": 20}},
        outputs={"backend": "surrogate", "Ms0_A_per_m": 8.6e5,
                 "K1_0_J_per_m3": 1e2, "Aex0_J_per_m": 1.3e-11},
        created_at=_dt(3.0, 9, 5), parent_ids=[r_a1.id], tags=["thread:A"],
    ))

    r_a3 = append(_make_record(lid, "mammos.finite_temperature_magnetics",
        inputs={"prototype": "Permalloy", "Ms0_A_per_m": 8.6e5,
                "K1_0_J_per_m3": 1e2, "Aex0_J_per_m": 1.3e-11,
                "target_temp_k": 300.0},
        outputs={"backend": "surrogate", "Tc_K": 853.0,
                 "Ms_T_A_per_m": 8.0e5, "K1_T_J_per_m3": 88.0,
                 "Aex_T_J_per_m": 1.25e-11, "m_T_over_Ms0": 0.93},
        created_at=_dt(3.0, 9, 12), parent_ids=[r_a2.id], tags=["thread:A"],
    ))

    r_a4 = append(_make_record(lid, "mammos.sensor_mesh",
        inputs={"a_nm": 500.0, "b_nm": 200.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs={"backend": "surrogate", "area_nm2": 314159.0,
                 "aspect_ratio": 2.5, "mesh_path": None},
        created_at=_dt(3.0, 9, 15), tags=["thread:A"],
    ))

    Ha, Ma, Hca, Mra = _soft_loop(Ms=8.0e5, Hc_frac=0.05, H_max=8e4)
    png_a = _render_hysteresis_png(Ha, Ma, Hca, Mra, "A Permalloy success")
    r_a5_out = {"backend": "surrogate", "H_A_per_m": Ha, "M_A_per_m": Ma,
                "Hc_A_per_m": float(Hca), "Mr_A_per_m": float(Mra),
                "H_sweep_max_A_per_m": 8e4}
    if png_a:
        r_a5_out["hysteresis_loop_png"] = png_a
    r_a5 = append(_make_record(lid, "mammos.micromagnetic_hysteresis",
        inputs={"Ms_A_per_m": 8.0e5, "K1_J_per_m3": 88.0,
                "Aex_J_per_m": 1.25e-11, "area_nm2": 314159.0,
                "aspect_ratio": 2.5, "thickness_nm": 5.0},
        outputs=r_a5_out,
        created_at=_dt(3.0, 9, 45), parent_ids=[r_a3.id, r_a4.id], tags=["thread:A"],
    ))

    r_a6 = append(_make_record(lid, "mammos.sensor_fom",
        inputs={"H_A_per_m": Ha[:5], "M_A_per_m": Ma[:5],
                "Ms_A_per_m": 8.0e5, "Hc_A_per_m": float(Hca)},
        outputs={"backend": "analytic", "sensitivity": 3.8e-5,
                 "linear_range_T": 0.0021, "Mr_over_Ms": 0.05,
                 "Hc_A_per_m": float(Hca)},
        created_at=_dt(3.0, 9, 46), parent_ids=[r_a5.id], tags=["thread:A"],
        decision={"notes": "Good sensitivity and linear range. Baseline established."},
    ))

    # ------------------------------------------------------------------ #
    # Thread B — Nd2Fe14B FAILURE as sensor free layer (2 days ago)
    # NB: square loop → sensitivity ≈ 0.  KEY CITATION TARGET.
    # ------------------------------------------------------------------ #
    r_b1 = append(_make_record(lid, "mammos.relax_structure",
        inputs={"composition": {"Nd": 2, "Fe": 14, "B": 1}, "prototype": "Nd2Fe14B"},
        outputs={"backend": "surrogate", "a_ang": 8.82, "c_ang": 12.23,
                 "volume_ang3": 951.0, "energy_ev_per_atom": -8.12,
                 "composition": {"Nd": 2, "Fe": 14, "B": 1}},
        created_at=_dt(2.0, 10, 0), tags=["thread:B", "material:Nd2Fe14B"],
    ))

    r_b2 = append(_make_record(lid, "mammos.intrinsic_magnetics_0k",
        inputs={"prototype": "Nd2Fe14B", "a_ang": 8.82, "c_ang": 12.23,
                "composition": {"Nd": 2, "Fe": 14, "B": 1}},
        outputs={"backend": "surrogate", "Ms0_A_per_m": 1.61e6,
                 "K1_0_J_per_m3": 4.9e6, "Aex0_J_per_m": 8.0e-12},
        created_at=_dt(2.0, 10, 8), parent_ids=[r_b1.id], tags=["thread:B"],
    ))

    r_b3 = append(_make_record(lid, "mammos.finite_temperature_magnetics",
        inputs={"prototype": "Nd2Fe14B", "Ms0_A_per_m": 1.61e6,
                "K1_0_J_per_m3": 4.9e6, "Aex0_J_per_m": 8.0e-12,
                "target_temp_k": 300.0},
        outputs={"backend": "surrogate", "Tc_K": 585.0,
                 "Ms_T_A_per_m": 1.42e6, "K1_T_J_per_m3": 3.8e6,
                 "Aex_T_J_per_m": 7.5e-12, "m_T_over_Ms0": 0.88},
        created_at=_dt(2.0, 10, 14), parent_ids=[r_b2.id], tags=["thread:B"],
    ))

    r_b4 = append(_make_record(lid, "mammos.sensor_mesh",
        inputs={"a_nm": 500.0, "b_nm": 200.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs={"backend": "surrogate", "area_nm2": 314159.0,
                 "aspect_ratio": 2.5, "mesh_path": None},
        created_at=_dt(2.0, 10, 16), tags=["thread:B"],
    ))

    # Nd2Fe14B has huge K1 → square loop, Hc ~ Ms*K1/(2*Ms^2) * shape
    Hc_b = 3.2e4  # ~3.2e4 A/m (40 mT) — clearly too large for a sensor
    Hb, Mb, Hcb, Mrb = _square_loop(Ms=1.42e6, Hc=Hc_b, H_max=8e4)
    png_b = _render_hysteresis_png(Hb, Mb, Hcb, Mrb, "B Nd2Fe14B SQUARE LOOP")
    r_b5_out = {"backend": "surrogate", "H_A_per_m": Hb, "M_A_per_m": Mb,
                "Hc_A_per_m": float(Hcb), "Mr_A_per_m": float(Mrb),
                "H_sweep_max_A_per_m": 8e4}
    if png_b:
        r_b5_out["hysteresis_loop_png"] = png_b
    r_b5 = append(_make_record(lid, "mammos.micromagnetic_hysteresis",
        inputs={"Ms_A_per_m": 1.42e6, "K1_J_per_m3": 3.8e6,
                "Aex_J_per_m": 7.5e-12, "area_nm2": 314159.0,
                "aspect_ratio": 2.5, "thickness_nm": 5.0},
        outputs=r_b5_out,
        created_at=_dt(2.0, 10, 50), parent_ids=[r_b3.id, r_b4.id], tags=["thread:B"],
    ))

    r_b6 = append(_make_record(lid, "mammos.sensor_fom",
        inputs={"H_A_per_m": Hb[:5], "M_A_per_m": Mb[:5],
                "Ms_A_per_m": 1.42e6, "Hc_A_per_m": float(Hcb)},
        outputs={"backend": "analytic", "sensitivity": 1.2e-7,
                 "linear_range_T": 0.000012, "Mr_over_Ms": 0.92,
                 "Hc_A_per_m": float(Hcb)},
        status="soft_fail",
        decision={"verdict": "soft_fail",
                  "reason": ("Nd2Fe14B is a hard magnet with near-square hysteresis; "
                             "sensitivity is essentially zero. Unsuitable as a sensor "
                             "free-layer material. High K1 (3.8 MJ/m³) drives square loop.")},
        created_at=_dt(2.0, 10, 51), parent_ids=[r_b5.id], tags=["thread:B", "NOTABLE"],
    ))

    # ------------------------------------------------------------------ #
    # Thread C — aspect-ratio fix (2 days ago → 1.8 days ago)
    # ------------------------------------------------------------------ #
    r_c1 = append(_make_record(lid, "mammos.sensor_mesh",
        inputs={"a_nm": 300.0, "b_nm": 250.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs={"backend": "surrogate", "area_nm2": 235619.0,
                 "aspect_ratio": 1.2, "mesh_path": None},
        created_at=_dt(1.8, 11, 0), tags=["thread:C", "material:Permalloy"],
    ))

    Hc1, Hm1 = 4e3 * 0.15, 4e3
    Hc_c1, Mc_low, Hcc1, Mrc1 = _soft_loop(Ms=8.0e5, Hc_frac=0.05, H_max=8e4)
    # low-AR → lower sensitivity; use same loop, sensitivity will be low via FOM
    r_c2 = append(_make_record(lid, "mammos.micromagnetic_hysteresis",
        inputs={"Ms_A_per_m": 8.0e5, "K1_J_per_m3": 88.0,
                "Aex_J_per_m": 1.25e-11, "area_nm2": 235619.0,
                "aspect_ratio": 1.2, "thickness_nm": 5.0},
        outputs={"backend": "surrogate", "H_A_per_m": Hc_c1,
                 "M_A_per_m": Mc_low, "Hc_A_per_m": float(Hcc1),
                 "Mr_A_per_m": float(Mrc1), "H_sweep_max_A_per_m": 8e4},
        created_at=_dt(1.8, 11, 30), parent_ids=[r_c1.id, r_a3.id], tags=["thread:C"],
    ))

    r_c3 = append(_make_record(lid, "mammos.sensor_fom",
        inputs={"H_A_per_m": Hc_c1[:5], "M_A_per_m": Mc_low[:5],
                "Ms_A_per_m": 8.0e5, "Hc_A_per_m": float(Hcc1)},
        outputs={"backend": "analytic", "sensitivity": 0.9e-5,
                 "linear_range_T": 0.0005, "Mr_over_Ms": 0.04,
                 "Hc_A_per_m": float(Hcc1)},
        status="soft_fail",
        decision={"verdict": "soft_fail",
                  "reason": "Low aspect ratio (1.2:1) insufficient shape anisotropy; retry with AR≥3."},
        created_at=_dt(1.8, 11, 31), parent_ids=[r_c2.id], tags=["thread:C"],
    ))

    # Rerun with AR=3
    r_c4 = append(_make_record(lid, "mammos.sensor_mesh",
        inputs={"a_nm": 600.0, "b_nm": 200.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs={"backend": "surrogate", "area_nm2": 376991.0,
                 "aspect_ratio": 3.0, "mesh_path": None},
        created_at=_dt(1.7, 14, 0), tags=["thread:C"],
        decision={"retry_of": r_c1.id, "reason": "increased aspect ratio to 3:1"},
    ))

    Hc_fix, Mc_fix, Hcc_fix, Mrc_fix = _soft_loop(Ms=8.0e5, Hc_frac=0.08, H_max=8e4)
    png_c = _render_hysteresis_png(Hc_fix, Mc_fix, Hcc_fix, Mrc_fix, "C fix AR=3 success")
    r_c5_out = {"backend": "surrogate", "H_A_per_m": Hc_fix, "M_A_per_m": Mc_fix,
                "Hc_A_per_m": float(Hcc_fix), "Mr_A_per_m": float(Mrc_fix),
                "H_sweep_max_A_per_m": 8e4}
    if png_c:
        r_c5_out["hysteresis_loop_png"] = png_c
    r_c5 = append(_make_record(lid, "mammos.micromagnetic_hysteresis",
        inputs={"Ms_A_per_m": 8.0e5, "K1_J_per_m3": 88.0,
                "Aex_J_per_m": 1.25e-11, "area_nm2": 376991.0,
                "aspect_ratio": 3.0, "thickness_nm": 5.0},
        outputs=r_c5_out,
        created_at=_dt(1.7, 14, 30), parent_ids=[r_c4.id, r_a3.id], tags=["thread:C"],
    ))

    r_c6 = append(_make_record(lid, "mammos.sensor_fom",
        inputs={"H_A_per_m": Hc_fix[:5], "M_A_per_m": Mc_fix[:5],
                "Ms_A_per_m": 8.0e5, "Hc_A_per_m": float(Hcc_fix)},
        outputs={"backend": "analytic", "sensitivity": 4.2e-5,
                 "linear_range_T": 0.0024, "Mr_over_Ms": 0.06,
                 "Hc_A_per_m": float(Hcc_fix)},
        decision={"verdict": "pass", "notes": "AR=3:1 recovers sensitivity. Shape lesson confirmed."},
        created_at=_dt(1.7, 14, 31), parent_ids=[r_c5.id], tags=["thread:C", "NOTABLE"],
    ))

    # ------------------------------------------------------------------ #
    # Thread D — Dy-substitution overshoot (1 day ago)
    # ------------------------------------------------------------------ #
    x_Dy = 0.25  # 25% → Ms crashes
    Ms_dy = 1.61e6 * (1 - 0.4 * x_Dy)
    K1_dy = 4.9e6 * (1 + 2.0 * x_Dy)

    r_d1 = append(_make_record(lid, "mammos.relax_structure",
        inputs={"composition": {"Nd": 1.5, "Dy": 0.5, "Fe": 14, "B": 1}, "prototype": "Nd2Fe14B"},
        outputs={"backend": "surrogate", "a_ang": 8.81, "c_ang": 12.20,
                 "volume_ang3": 945.0, "energy_ev_per_atom": -8.08,
                 "composition": {"Nd": 1.5, "Dy": 0.5, "Fe": 14, "B": 1}},
        created_at=_dt(1.0, 9, 0), tags=["thread:D", "material:Nd2Fe14B-Dy25"],
    ))

    r_d2 = append(_make_record(lid, "mammos.intrinsic_magnetics_0k",
        inputs={"prototype": "Nd2Fe14B", "a_ang": 8.81, "c_ang": 12.20,
                "composition": {"Nd": 1.5, "Dy": 0.5, "Fe": 14, "B": 1}},
        outputs={"backend": "surrogate", "Ms0_A_per_m": Ms_dy,
                 "K1_0_J_per_m3": K1_dy, "Aex0_J_per_m": 8.0e-12},
        created_at=_dt(1.0, 9, 8), parent_ids=[r_d1.id], tags=["thread:D"],
    ))

    Ms_dy_T = Ms_dy * 0.86  # Kuzmin @ 300K with lower Tc
    K1_dy_T = K1_dy * 0.75

    r_d3 = append(_make_record(lid, "mammos.finite_temperature_magnetics",
        inputs={"prototype": "Nd2Fe14B", "Ms0_A_per_m": Ms_dy,
                "K1_0_J_per_m3": K1_dy, "Aex0_J_per_m": 8.0e-12,
                "target_temp_k": 300.0},
        outputs={"backend": "surrogate", "Tc_K": 540.0,
                 "Ms_T_A_per_m": Ms_dy_T, "K1_T_J_per_m3": K1_dy_T,
                 "Aex_T_J_per_m": 7.8e-12, "m_T_over_Ms0": 0.86},
        created_at=_dt(1.0, 9, 15), parent_ids=[r_d2.id], tags=["thread:D"],
        decision={"notes": f"25% Dy: Ms={Ms_dy_T/1e6:.3f} MA/m — BELOW 1 MA/m target. "
                           "K1 boosted to 12.25 MJ/m³ but sensor sensitivity destroyed."},
    ))

    # ------------------------------------------------------------------ #
    # Thread E — Human intervention (1 day ago)
    # ------------------------------------------------------------------ #
    r_e1 = append(_make_record(lid, "human_intervention",
        inputs={},
        outputs={"constraint": "Ms_T_A_per_m >= 1e6",
                 "rationale": ("Sensor free-layer requires Ms > 1 MA/m for adequate "
                               "signal-to-noise. Dy substitution above ~15% pushes Ms "
                               "below this threshold. Restrict search to x_Dy ≤ 0.10.")},
        created_at=_dt(1.0, 11, 30), tags=["intervention", "NOTABLE"],
        module="human.v1", resource_kind=None,
        decision={"author": "scientist", "constraint_added": "Ms_T >= 1 MA/m"},
    ))

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-root", default=LAB_ROOT_DEFAULT)
    parser.add_argument("--campaign-id", default=CAMPAIGN_ID)
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate the lab root first.")
    args = parser.parse_args()

    root = Path(args.lab_root)
    if args.reset and root.exists():
        shutil.rmtree(root)
        print(f"[seed] Cleared {root}")

    global CAMPAIGN_ID
    CAMPAIGN_ID = args.campaign_id

    lab = Lab(root)
    print(f"[seed] Lab ID: {lab.lab_id}")
    print(f"[seed] Lab root: {root.resolve()}")
    print(f"[seed] Campaign ID: {CAMPAIGN_ID}")

    records = seed(lab)
    lab.ledger.close()

    print(f"\n[seed] Written {len(records)} records.")
    print("\n=== Record hashes (for demo citation reference) ===")
    for rec in records:
        cs = rec.checksum or ""
        short = f"0x{cs[:6]}"
        print(f"  {short}  {rec.operation:<45} status={rec.record_status}  "
              f"tags={rec.tags}")

    # Print citation hints.
    notable = [r for r in records if "NOTABLE" in r.tags]
    print("\n=== Demo citation hints ===")
    for rec in notable:
        cs = rec.checksum or ""
        short = f"0x{cs[:6]}"
        dec_note = (rec.decision or {}).get("notes") or (rec.decision or {}).get("reason") or ""
        print(f"  {short}  {rec.operation}  →  {dec_note[:80]}")

    print("\n[seed] Done. Boot the Lab with this root and run a demo campaign to see citations.")


if __name__ == "__main__":
    main()
