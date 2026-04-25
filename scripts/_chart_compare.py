"""Render best-so-far Hmax curves with material annotation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "src")

from autolab.lab import Lab

OPTUNA_ID = "camp-f92759a3b1"
CLAUDE_ID = "camp-acd804d988"
OUT = Path("var/demo_lab/_compare_optuna_vs_claude.png")


def per_trial(records):
    completed = [
        r for r in records
        if r.operation == "mammos.sensor_shape_fom"
        and r.record_status in {"completed", "soft_fail"}
        and (r.outputs or {}).get("Hmax_A_per_m") is not None
    ]
    completed.sort(key=lambda r: r.created_at or "")
    rows = []
    best = None
    for i, r in enumerate(completed, 1):
        v = float(r.outputs["Hmax_A_per_m"])
        best = v if best is None or v > best else best
        # Material is an input on the upstream material step; pull from its source record via parent_ids if present, else from rec.outputs (echoed inputs).
        mat = (r.outputs or {}).get("material")
        if not mat:
            # walk parents to find a material lookup record
            for pid in (r.parent_ids or []):
                pr = next((q for q in records if q.id == pid), None)
                if pr and pr.operation == "mammos.sensor_material_at_T":
                    mat = (pr.inputs or {}).get("material")
                    break
        rows.append({
            "trial": i,
            "Hmax_A_per_m": v,
            "best_so_far": best,
            "sx_nm": (r.inputs or {}).get("sx_nm"),
            "sy_nm": (r.inputs or {}).get("sy_nm"),
            "material": mat,
        })
    return rows


def main() -> None:
    lab = Lab(Path("var/demo_lab"))
    all_recs = list(lab.ledger.iter_records())
    optuna_rows = per_trial([r for r in all_recs if r.campaign_id == OPTUNA_ID])
    claude_rows = per_trial([r for r in all_recs if r.campaign_id == CLAUDE_ID])

    mu0 = 4 * 3.141592653589793 * 1e-7

    def mt(v):
        return v * mu0 * 1e3

    print(f"{'planner':<8} {'trial':<5} {'mat':<10} {'sx':>5} {'sy':>5} {'Hmax(mT)':>10} {'best(mT)':>10}")
    for label, rows in (("optuna", optuna_rows), ("claude", claude_rows)):
        for r in rows:
            print(f"{label:<8} {r['trial']:<5} {str(r['material']):<10} "
                  f"{(r['sx_nm'] or 0):>5.1f} {(r['sy_nm'] or 0):>5.1f} "
                  f"{mt(r['Hmax_A_per_m']):>10.1f} {mt(r['best_so_far']):>10.1f}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=110)
    mat_color = {"Ni80Fe20": "#9ecae1", "FeCo": "#ffbf69"}

    for label, rows, color, marker in [
        ("Optuna (TPE)", optuna_rows, "#d62728", "o"),
        ("Claude Opus 4.7", claude_rows, "#1f77b4", "s"),
    ]:
        if not rows:
            continue
        xs = [r["trial"] for r in rows]
        bsf = [mt(r["best_so_far"]) for r in rows]
        ax.plot(xs, bsf, marker=marker, linewidth=2.0, color=color,
                label=f"{label} — best={bsf[-1]:.0f} mT")
        # annotate per-trial material with a short marker on the per-trial points
        per = [mt(r["Hmax_A_per_m"]) for r in rows]
        for r, y in zip(rows, per):
            ax.scatter([r["trial"]], [y], s=70, alpha=0.5,
                       color=mat_color.get(str(r["material"]), "#cccccc"),
                       edgecolor=color, linewidth=1.0, zorder=2)

    # Material-color legend (proxies)
    from matplotlib.lines import Line2D
    extra = [
        Line2D([0], [0], marker="o", linestyle="", markersize=10,
               markerfacecolor=c, markeredgecolor="black", label=m)
        for m, c in mat_color.items()
    ]
    leg1 = ax.legend(loc="upper left", fontsize=10, title="Best-so-far")
    ax.add_artist(leg1)
    ax.legend(handles=extra, loc="lower right", fontsize=10, title="Material per trial")

    ax.set_xlabel("Trial #", fontsize=12)
    ax.set_ylabel(r"Best-so-far $\mu_0 H_{\max}$ (mT)", fontsize=12)
    ax.set_title("Material + shape sweep — Optuna vs Claude (cold start, budget=12)",
                 fontsize=12)
    ax.grid(True, linewidth=0.4, alpha=0.5)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"\nChart written to: {OUT.resolve()}")


if __name__ == "__main__":
    main()
