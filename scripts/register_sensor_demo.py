"""Register the MaMMoS sensor shape-optimisation demo against a running Lab.

Usage::

    pixi run serve-prod     # in one terminal, boots the Lab
    pixi run sensor-demo    # in another, POSTs the demo to the running Lab

What it does:

1. Apply the ``sensor_shape_opt`` bootstrap via ``POST /bootstraps/apply``.
   This registers only the VM resource, two sensor Operations, and the
   two-step ``sensor_shape_opt`` WorkflowTemplate.

2. Create prepared Campaigns with ``autostart=false``. By default it
   creates one Optuna campaign and one Claude campaign with the same
   objective, bounds, budget, and workflow so you can compare convergence
   side by side from the Console.

3. Print a summary of the ``/status`` endpoint so you can visually confirm
   nothing is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

SHAPE_SEARCH_SPACE = {
    "sx_nm": {"type": "float", "low": 5.0, "high": 70.0},
    "sy_nm": {"type": "float", "low": 5.0, "high": 70.0},
}


def _url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(_url(base, path), timeout=30) as r:
        return json.loads(r.read())


def _post(base: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        _url(base, path),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise SystemExit(f"[error] POST {path} -> HTTP {e.code}: {body_text}") from None


def _campaign_body(planner: str, workflow: dict) -> dict:
    base = {
        "objective": {"key": "Hmax_A_per_m", "direction": "maximise"},
        "budget": 12,
        "parallelism": 1,
        "priority": 50,
        "workflow": workflow,
        "autostart": False,
    }
    if planner == "optuna":
        return {
            **base,
            "name": "sensor-shape-opt (optuna)",
            "description": (
                "Shape-optimise a Permalloy superellipse sensor (Ni80Fe20 @ 300 K). "
                "Optuna TPE sweeps (sx_nm, sy_nm) over the linear-region width Hmax. "
                "Prepared - start from the Console."
            ),
            "planner": "optuna",
            "planner_config": {
                "operation": "mammos.sensor_shape_fom",
                "search_space": SHAPE_SEARCH_SPACE,
            },
        }
    if planner == "claude":
        return {
            **base,
            "name": "sensor-shape-opt (claude)",
            "description": (
                "Same objective and bounds as the Optuna campaign - Claude as planner. "
                "Reads campaign history and reasons about the next (sx_nm, sy_nm) to try. "
                "Prepared - start from the Console."
            ),
            "planner": "claude",
            "planner_config": {
                "operation": "mammos.sensor_shape_fom",
                "search_space": SHAPE_SEARCH_SPACE,
                "batch_size": 1,
            },
            "use_claude_policy": True,
        }
    raise ValueError(f"unknown planner {planner!r}")


def _selected_planners(selection: str) -> list[str]:
    return ["optuna", "claude"] if selection == "both" else [selection]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="http://127.0.0.1:8000",
        help="Lab service base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--skip-campaign",
        action="store_true",
        help="Register bootstrap only; do not create prepared campaigns.",
    )
    parser.add_argument(
        "--planner",
        default="both",
        choices=("both", "optuna", "claude"),
        help="Prepared campaign(s) to create (default: both).",
    )
    args = parser.parse_args()
    planners = _selected_planners(args.planner)

    # --- 1. Probe health -----------------------------------------------------
    try:
        with urllib.request.urlopen(_url(args.base, "/health"), timeout=10) as r:
            _ = r.read()  # body is "ok", not JSON
    except Exception as exc:
        print(f"[error] Lab is not reachable at {args.base}: {exc}", file=sys.stderr)
        print("        Start it first with: pixi run serve-prod", file=sys.stderr)
        return 2

    # --- 2. Apply the minimal sensor shape-opt bootstrap --------------------
    print(f"[1/3] POST {args.base}/bootstraps/apply  mode=sensor_shape_opt")
    applied = _post(args.base, "/bootstraps/apply", {"mode": "sensor_shape_opt"})
    if not applied.get("ok"):
        print(f"      failed: {applied}", file=sys.stderr)
        return 1
    print(
        f"      resources={applied['resources']}\n"
        f"      capabilities={applied['capabilities']}\n"
        f"      workflows={applied['workflows']}"
    )
    if applied.get("bootstrap_error"):
        print(f"      bootstrap_error: {applied['bootstrap_error']}", file=sys.stderr)

    # --- 3. Fetch the sensor_shape_opt workflow from /status ----------------
    status = _get(args.base, "/status")
    if "claude" in planners and not status.get("claude_configured"):
        print(
            "[error] Claude comparison campaign requires ANTHROPIC_API_KEY on the server. "
            "Set it in .env and restart, or run only Optuna with: "
            "pixi run sensor-demo -- --planner optuna",
            file=sys.stderr,
        )
        return 1
    wf = next((w for w in status.get("workflows", []) if w.get("name") == "sensor_shape_opt"), None)
    if not wf:
        print("[error] sensor_shape_opt workflow not found in /status", file=sys.stderr)
        return 1

    # --- 4. Create the prepared campaigns -----------------------------------
    if not args.skip_campaign:
        print(f"[4/5] POST {args.base}/campaigns  (autostart=false, planners={planners})")
        for planner in planners:
            camp = _post(args.base, "/campaigns", _campaign_body(planner, wf))
            print(
                f"      planner={planner:<6} campaign_id={camp['campaign_id']}  "
                f"name={camp['name']!r}  status={camp.get('status', '?')}"
            )
    else:
        print("[4/5] (skipped campaign creation)")

    # --- 5. Verify by hitting /status ---------------------------------------
    print(f"[5/5] GET  {args.base}/status  (verification)")
    s = _get(args.base, "/status")
    resources = [r["name"] for r in s["resources"]]
    workflows = [w["name"] for w in s["workflows"]]
    tools = [t["capability"] for t in s["tools"]]
    campaigns = s.get("campaigns", [])
    print(f"      resources      = {resources}")
    print(f"      workflows      = {workflows}")
    print(f"      tools          = {tools}")
    print(f"      planners       = {s.get('planners_available')}")
    print(f"      claude_ready   = {s.get('claude_configured')}")
    print(f"      campaigns      = {[(c.get('name'), c.get('status')) for c in campaigns]}")

    missing = []
    for resource in ("this-pc", "vm-primary"):
        if resource not in resources:
            missing.append(f"resource {resource}")
    if "sensor_shape_opt" not in workflows:
        missing.append("workflow sensor_shape_opt")
    for tool in ("mammos.sensor_material_at_T", "mammos.sensor_shape_fom"):
        if tool not in tools:
            missing.append(f"tool {tool}")

    unexpected = sorted(set(tools) - {"mammos.sensor_material_at_T", "mammos.sensor_shape_fom"})
    if unexpected:
        missing.append(f"unexpected extra tools: {unexpected}")
    unexpected_wf = sorted(set(workflows) - {"sensor_shape_opt"})
    if unexpected_wf:
        missing.append(f"unexpected extra workflows: {unexpected_wf}")

    if not args.skip_campaign:
        queued_names = {c.get("name") for c in campaigns if c.get("status") == "queued"}
        for planner in planners:
            expected = f"sensor-shape-opt ({planner})"
            if expected not in queued_names:
                missing.append(f"prepared queued campaign {expected}")
    if missing:
        print("[error] verification failed: " + "; ".join(missing), file=sys.stderr)
        return 1

    print(
        "\n[done] sensor demo registered. Open the Console at "
        + args.base
        + " and start the prepared campaign(s) you want to compare."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
