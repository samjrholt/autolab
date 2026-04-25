"""Render the Optuna-vs-Claude best-so-far comparison chart.

Inputs: hardcoded campaign IDs (update per rehearsal).
Output: var/demo_lab/_compare_optuna_vs_claude.png
"""
from __future__ import annotations
import json
import math
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = "http://127.0.0.1:8000"
OPTUNA = "camp-66e8129e36"
CLAUDE = "camp-223d4804cc"
OUT = Path("var/demo_lab/_compare_optuna_vs_claude.png")

MU0 = 4 * math.pi * 1e-7  # H/m

MATERIAL_COLOR = {
    "Fe16N2": "#d62728",
    "Ni80Fe20": "#1f77b4",
    "Fe2.33Ta0.67Y": "#2ca02c",
}


def fetch_ledger() -> list[dict]:
    with urllib.request.urlopen(f"{BASE}/ledger?limit=2000", timeout=60) as r:
        return json.loads(r.read()).get("records", [])


def trials(records: list[dict]) -> list[tuple[int, str, float]]:
    """Pair fom records with their material step by created_at order.

    Workflow runs material → fom sequentially per trial, so the i-th
    completed material record pairs with the i-th completed fom record.
    Returns (trial_idx, material, Hmax_A_per_m).
    """
    fom_records = [r for r in records if r.get("operation") == "mammos.sensor_shape_fom"
                   and r.get("record_status") == "completed"]
    material_records = [r for r in records if r.get("operation") == "mammos.sensor_material_at_T"
                        and r.get("record_status") == "completed"]
    fom_records.sort(key=lambda r: r.get("created_at") or "")
    material_records.sort(key=lambda r: r.get("created_at") or "")

    out: list[tuple[int, str, float]] = []
    for i, fom in enumerate(fom_records, start=1):
        h = (fom.get("outputs") or {}).get("Hmax_A_per_m")
        if h is None:
            continue
        mat = material_records[i - 1] if i - 1 < len(material_records) else None
        mat_name = (mat.get("inputs") or {}).get("material", "?") if mat else "?"
        out.append((i, str(mat_name), float(h)))
    return out


def best_so_far(values: list[float]) -> list[float]:
    out: list[float] = []
    cur = -math.inf
    for v in values:
        if v > cur:
            cur = v
        out.append(cur)
    return out


def main() -> int:
    all_records = fetch_ledger()
    o_trials = trials([r for r in all_records if r.get("campaign_id") == OPTUNA])
    c_trials = trials([r for r in all_records if r.get("campaign_id") == CLAUDE])

    if not o_trials and not c_trials:
        print("No completed trials yet — aborting chart render.")
        return 1

    fig, (ax_curve, ax_scatter) = plt.subplots(1, 2, figsize=(14, 6), dpi=100)

    # --- Best-so-far curves ---
    for label, color, data in (
        ("Optuna (TPE)", "#ff7f0e", o_trials),
        ("Claude", "#1f77b4", c_trials),
    ):
        if not data:
            continue
        idx = [i + 1 for i, _ in enumerate(data)]
        h = [t[2] for t in data]
        bsf = best_so_far(h)
        # Convert A/m -> mT (μ0 H).
        h_mT = [v * MU0 * 1e3 for v in h]
        bsf_mT = [v * MU0 * 1e3 for v in bsf]
        ax_curve.plot(idx, bsf_mT, color=color, linewidth=2.5, label=f"{label} best-so-far", zorder=3)
        ax_curve.scatter(idx, h_mT, color=color, s=40, alpha=0.5, zorder=2)

    ax_curve.set_xlabel("Trial number", fontsize=12)
    ax_curve.set_ylabel(r"$\mu_0 H_{\max}$  (mT)", fontsize=12)
    ax_curve.set_title("Best-so-far  ·  higher is better", fontsize=12)
    ax_curve.grid(True, linewidth=0.4, alpha=0.4)
    ax_curve.legend(loc="lower right", fontsize=10)

    # --- Scatter colored by material ---
    for label, marker, data in (
        ("Optuna", "o", o_trials),
        ("Claude", "s", c_trials),
    ):
        if not data:
            continue
        for tn, mat, h in data:
            color = MATERIAL_COLOR.get(mat, "#666666")
            ax_scatter.scatter(
                tn,
                h * MU0 * 1e3,
                color=color,
                marker=marker,
                s=70,
                edgecolor="black",
                linewidth=0.5,
                alpha=0.85,
                zorder=3,
            )

    # Material legend.
    from matplotlib.lines import Line2D

    handles = []
    for mat, color in MATERIAL_COLOR.items():
        handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                              markeredgecolor="black", markersize=9, label=mat))
    handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="lightgray",
                          markeredgecolor="black", markersize=9, label="Optuna (○)"))
    handles.append(Line2D([0], [0], marker="s", color="w", markerfacecolor="lightgray",
                          markeredgecolor="black", markersize=9, label="Claude (□)"))
    ax_scatter.legend(handles=handles, loc="lower right", fontsize=9)

    ax_scatter.set_xlabel("Trial number", fontsize=12)
    ax_scatter.set_ylabel(r"$\mu_0 H_{\max}$  (mT)", fontsize=12)
    ax_scatter.set_title("Per-trial outcomes by material", fontsize=12)
    ax_scatter.grid(True, linewidth=0.4, alpha=0.4)

    fig.suptitle("Sensor shape optimisation  ·  Optuna vs Claude", fontsize=14, fontweight="bold")
    fig.tight_layout()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=120, bbox_inches="tight")
    plt.close(fig)

    # Summary line.
    o_best = max((t[2] for t in o_trials), default=None)
    c_best = max((t[2] for t in c_trials), default=None)
    print(f"Saved {OUT}")
    print(f"Optuna trials={len(o_trials)} best_Hmax_A_per_m={o_best}")
    print(f"Claude trials={len(c_trials)} best_Hmax_A_per_m={c_best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
