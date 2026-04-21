"""Boot a Lab, register the example, and run the superellipse campaign.

Run with::

    python -m examples.superellipse_sensor.run                # Optuna/TPE
    python -m examples.superellipse_sensor.run --planner bo    # in-house GP-EI

The framework sees no magnetism here — only a YAML *tool* declaration,
an adapter import, and a Campaign authored in Python.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from autolab import Lab, Resource

from examples.superellipse_sensor.campaign import (
    build_bo_planner,
    build_campaign,
    build_optuna_planner,
)


HERE = Path(__file__).parent


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the superellipse sensor demo campaign.")
    parser.add_argument("--root", type=Path, default=Path("./.autolab-runs/superellipse"))
    parser.add_argument("--tool", type=Path, default=HERE / "tool.yaml")
    parser.add_argument(
        "--planner",
        choices=("optuna", "bo"),
        default="optuna",
        help="Which Planner to drive the search with.",
    )
    parser.add_argument(
        "--sampler",
        default="tpe",
        help="Optuna sampler (tpe, cmaes, gp, random). Ignored for --planner bo.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    campaign = build_campaign()
    if args.planner == "optuna":
        planner = build_optuna_planner(sampler=args.sampler, seed=args.seed)
    else:
        planner = build_bo_planner(seed=args.seed)

    with Lab(args.root, lab_id="lab-superellipse") as lab:
        lab.register_resource(
            Resource(
                name="this-machine",
                kind="computer",
                capabilities={"cores_gte": 1, "has_oommf": False},
                description="The local box running ubermag (or its surrogate).",
            )
        )
        decl = lab.register_tool(args.tool)
        print(f"registered tool {decl.name!r} hash={decl.declaration_hash[:12]}…")
        print(f"campaign {campaign.id} planner={planner.name}")

        async def _print_events() -> None:
            queue = lab.events.subscribe()
            while True:
                event = await queue.get()
                if event.kind.startswith("record."):
                    rec = event.payload.get("record", {})
                    status = rec.get("record_status")
                    op = rec.get("operation")
                    rid = rec.get("id", "")[:12]
                    outs = rec.get("outputs") or {}
                    extra = ""
                    if status == "completed" and "sensitivity" in outs:
                        extra = (
                            f"  sens={outs['sensitivity']:.3f}/T"
                            f"  Hc={outs['Hc']:.0f}A/m"
                            f"  Mr/Ms={outs['Mr_over_Ms']:.2f}"
                            f"  lin={outs['linear_range']*1e3:.2f}mT"
                        )
                    print(
                        f"[{event.timestamp:%H:%M:%S}] {event.kind:24s} {op or '':30s} {rid}{extra}"
                    )
                elif event.kind.startswith("campaign."):
                    print(f"[{event.timestamp:%H:%M:%S}] {event.kind}: {event.payload}")

        printer = asyncio.create_task(_print_events())
        try:
            summary = await lab.run_campaign(campaign, planner)
        finally:
            printer.cancel()

        print("\n=== Summary ===")
        print(f"campaign : {summary.campaign_id}")
        print(f"status   : {summary.status}")
        print(f"reason   : {summary.reason}")
        print(f"steps    : {summary.steps_run}")
        if summary.best_outputs:
            scalar = {
                k: v
                for k, v in summary.best_outputs.items()
                if isinstance(v, int | float)
            }
            print(f"best     : {scalar}")

        bad = lab.verify_ledger()
        print(f"checksum verification: {'OK' if not bad else f'BAD: {bad}'}")


if __name__ == "__main__":
    asyncio.run(main())
