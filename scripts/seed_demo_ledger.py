"""Seed the autolab Ledger with plausible prior-run history for the hackathon demo.

Writes 9 Records using the SAME operation names as the live demo workflow
(mammos.sensor_material_at_T + mammos.sensor_shape_fom) so Claude sees them
as directly relevant prior runs and cites their hashes inline.

Four narrative threads:

  A  Ni80Fe20 (Permalloy) baseline — 60×20 nm ellipse, AR=3, gradient≈3.8. OK.
  B  Circular geometry FAILURE — Ni80Fe20, 50×50 nm, AR=1. Near-square loop,
     gradient≈0.02. KEY CITATION TARGET: Claude should say "same square loop
     as 0xXXXX" when it sees another isotropic shape fail.
  C  Elongated fix — Ni80Fe20 70×10 nm, AR=7, gradient≈5.8. Recovers linear range.
  D  FeCo material upgrade — 70×10 nm, gradient≈9.4. Best run. Human intervention
     note: enforce sx/sy ≥ 4 for all future trials.

Expected citation hints (printed at the end of this script):
  - Circular-shape record (Thread B) is the #1 citation target.
  - FeCo record (Thread D) is the benchmark to beat.
  - Human-intervention record constrains the search space.

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
    mu0 = 4 * math.pi * 1e-7

    def append(r: Record) -> Record:
        saved = lab.ledger.append_sync(r)
        records.append(saved)
        return saved

    # ------------------------------------------------------------------ #
    # Thread A — Ni80Fe20 baseline (3 days ago)
    # 60×20 nm ellipse, AR=3 → clean single-domain switching, gradient≈3.8
    # ------------------------------------------------------------------ #
    r_a1 = append(_make_record(lid, "mammos.sensor_material_at_T",
        inputs={"material": "Ni80Fe20", "temperature_K": 300.0},
        outputs={"backend": "mammos_spindynamics", "material": "Ni80Fe20",
                 "temperature_K": 300.0, "Ms_A_per_m": 8.0e5, "A_J_per_m": 1.3e-11},
        created_at=_dt(3.0, 9, 0), tags=["thread:A", "material:Ni80Fe20"],
    ))

    Ha, Ma, Hca, Mra = _soft_loop(Ms=8.0e5, Hc_frac=0.22, H_max=16000)
    png_a = _render_hysteresis_png(Ha, Ma, Hca, Mra, "A-Ni80Fe20-60x20")
    Hmax_a = 3580.0  # A/m  (≈ 4.5 mT)
    r_a2_out: dict = {
        "backend": "ubermag",
        "Hmax_A_per_m": Hmax_a, "mu0_Hmax_T": Hmax_a * mu0,
        "gradient": 3.8, "Mr_A_per_m": 720e3,
        "H_A_per_m": Ha, "M_A_per_m": Ma,
        "Ms_A_per_m": 8.0e5, "sx_nm": 60.0, "sy_nm": 20.0,
        "n_exp": 2.0, "thickness_nm": 5.0,
    }
    if png_a:
        r_a2_out["hysteresis_loop_png"] = png_a
    r_a2 = append(_make_record(lid, "mammos.sensor_shape_fom",
        inputs={"Ms_A_per_m": 8.0e5, "A_J_per_m": 1.3e-11,
                "sx_nm": 60.0, "sy_nm": 20.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs=r_a2_out,
        created_at=_dt(3.0, 9, 20), parent_ids=[r_a1.id],
        tags=["thread:A", "NOTABLE"],
        decision={"verdict": "pass",
                  "notes": "Ni80Fe20 60×20 nm baseline: gradient=3.8, Hmax=4.5 mT. Linear range adequate."},
    ))

    # ------------------------------------------------------------------ #
    # Thread B — Circular geometry FAILURE (2 days ago)
    # 50×50 nm circular disk, AR=1 → near-square loop, gradient≈0.02
    # KEY CITATION TARGET — circular/isotropic shape is disqualifying.
    # ------------------------------------------------------------------ #
    r_b1 = append(_make_record(lid, "mammos.sensor_material_at_T",
        inputs={"material": "Ni80Fe20", "temperature_K": 300.0},
        outputs={"backend": "mammos_spindynamics", "material": "Ni80Fe20",
                 "temperature_K": 300.0, "Ms_A_per_m": 8.0e5, "A_J_per_m": 1.3e-11},
        created_at=_dt(2.0, 10, 0), tags=["thread:B", "material:Ni80Fe20"],
    ))

    Hb, Mb, Hcb, Mrb = _square_loop(Ms=8.0e5, Hc=80.0, H_max=16000)
    png_b = _render_hysteresis_png(Hb, Mb, Hcb, Mrb, "B-Ni80Fe20-50x50-SQUARE-LOOP")
    Hmax_b = 40.0  # A/m  (≈ 0.05 mT — essentially zero linear range)
    r_b2_out: dict = {
        "backend": "ubermag",
        "Hmax_A_per_m": Hmax_b, "mu0_Hmax_T": Hmax_b * mu0,
        "gradient": 0.02, "Mr_A_per_m": 792e3,
        "H_A_per_m": Hb, "M_A_per_m": Mb,
        "Ms_A_per_m": 8.0e5, "sx_nm": 50.0, "sy_nm": 50.0,
        "n_exp": 2.0, "thickness_nm": 5.0,
    }
    if png_b:
        r_b2_out["hysteresis_loop_png"] = png_b
    r_b2 = append(_make_record(lid, "mammos.sensor_shape_fom",
        inputs={"Ms_A_per_m": 8.0e5, "A_J_per_m": 1.3e-11,
                "sx_nm": 50.0, "sy_nm": 50.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs=r_b2_out,
        status="soft_fail",
        created_at=_dt(2.0, 10, 22), parent_ids=[r_b1.id],
        tags=["thread:B", "NOTABLE"],
        decision={"verdict": "soft_fail",
                  "reason": ("Circular disk (sx=sy=50 nm, AR=1) produces a near-square "
                             "hysteresis loop — multi-domain vortex state switches abruptly "
                             "with no linear sensing region. gradient=0.02 ≈ 0. "
                             "Shape anisotropy completely absent. Isotropic geometries "
                             "are disqualified as sensor free layers.")},
    ))

    # ------------------------------------------------------------------ #
    # Thread C — Elongated 70×10 nm fix (1.8 days ago)
    # AR=7 → single-domain, large linear range, gradient≈5.8
    # ------------------------------------------------------------------ #
    Hc, Mc, Hcc, Mrc = _soft_loop(Ms=8.0e5, Hc_frac=0.35, H_max=16000)
    png_c = _render_hysteresis_png(Hc, Mc, Hcc, Mrc, "C-Ni80Fe20-70x10")
    Hmax_c = 5570.0  # A/m  (≈ 7.0 mT)
    r_c1_out: dict = {
        "backend": "ubermag",
        "Hmax_A_per_m": Hmax_c, "mu0_Hmax_T": Hmax_c * mu0,
        "gradient": 5.8, "Mr_A_per_m": 760e3,
        "H_A_per_m": Hc, "M_A_per_m": Mc,
        "Ms_A_per_m": 8.0e5, "sx_nm": 70.0, "sy_nm": 10.0,
        "n_exp": 2.0, "thickness_nm": 5.0,
    }
    if png_c:
        r_c1_out["hysteresis_loop_png"] = png_c
    r_c1 = append(_make_record(lid, "mammos.sensor_shape_fom",
        inputs={"Ms_A_per_m": 8.0e5, "A_J_per_m": 1.3e-11,
                "sx_nm": 70.0, "sy_nm": 10.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs=r_c1_out,
        created_at=_dt(1.8, 11, 0), parent_ids=[r_b1.id],
        tags=["thread:C", "NOTABLE"],
        decision={"verdict": "pass",
                  "retry_of": r_b2.id,
                  "notes": ("Elongated 70×10 nm (AR=7) recovers single-domain switching "
                            "and a broad linear range. gradient=5.8 vs 0.02 for circular. "
                            "Shape lesson confirmed: AR≥4 required.")},
    ))

    # ------------------------------------------------------------------ #
    # Thread D — FeCo material upgrade (1 day ago)
    # Higher Ms → larger signal → gradient≈9.4 at same 70×10 nm geometry
    # ------------------------------------------------------------------ #
    r_d1 = append(_make_record(lid, "mammos.sensor_material_at_T",
        inputs={"material": "FeCo", "temperature_K": 300.0},
        outputs={"backend": "mammos_spindynamics", "material": "FeCo",
                 "temperature_K": 300.0, "Ms_A_per_m": 1.9e6, "A_J_per_m": 2.8e-11},
        created_at=_dt(1.0, 9, 0), tags=["thread:D", "material:FeCo"],
    ))

    Hd, Md, Hcd, Mrd = _soft_loop(Ms=1.9e6, Hc_frac=0.33, H_max=16000)
    png_d = _render_hysteresis_png(Hd, Md, Hcd, Mrd, "D-FeCo-70x10")
    Hmax_d = 8360.0  # A/m  (≈ 10.5 mT)
    r_d2_out: dict = {
        "backend": "ubermag",
        "Hmax_A_per_m": Hmax_d, "mu0_Hmax_T": Hmax_d * mu0,
        "gradient": 9.4, "Mr_A_per_m": 1.71e6,
        "H_A_per_m": Hd, "M_A_per_m": Md,
        "Ms_A_per_m": 1.9e6, "sx_nm": 70.0, "sy_nm": 10.0,
        "n_exp": 2.0, "thickness_nm": 5.0,
    }
    if png_d:
        r_d2_out["hysteresis_loop_png"] = png_d
    r_d2 = append(_make_record(lid, "mammos.sensor_shape_fom",
        inputs={"Ms_A_per_m": 1.9e6, "A_J_per_m": 2.8e-11,
                "sx_nm": 70.0, "sy_nm": 10.0, "n_exp": 2.0, "thickness_nm": 5.0},
        outputs=r_d2_out,
        created_at=_dt(1.0, 9, 25), parent_ids=[r_d1.id],
        tags=["thread:D", "NOTABLE"],
        decision={"verdict": "pass",
                  "notes": ("FeCo 70×10 nm: gradient=9.4, Hmax=10.5 mT. "
                            "Best result to date. Higher Ms (1.9 MA/m vs 0.8 MA/m) "
                            "amplifies the signal without degrading shape anisotropy.")},
    ))

    # ------------------------------------------------------------------ #
    # Human intervention (1 day ago)
    # Constraint: elongated shapes only (sx/sy ≥ 4)
    # ------------------------------------------------------------------ #
    r_e1 = append(_make_record(lid, "human_intervention",
        inputs={},
        outputs={"constraint": "sx_nm / sy_nm >= 4",
                 "rationale": ("Circular and near-isotropic shapes (AR < 4) consistently "
                               "produce multi-domain vortex states and near-square loops "
                               "with no linear sensing region (see 0x{} for the definitive "
                               "failure case). All future shape proposals must satisfy "
                               "sx/sy ≥ 4.".format(
                                   (r_b2.checksum or "")[:6]))},
        created_at=_dt(1.0, 11, 0), tags=["intervention", "NOTABLE"],
        module="human.v1", resource_kind=None,
        decision={"author": "scientist", "constraint_added": "sx/sy >= 4"},
    ))

    return records

def main() -> None:
    global CAMPAIGN_ID
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
