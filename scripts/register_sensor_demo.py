"""Register the MaMMoS sensor shape-optimisation demo against a running Lab.

Usage::

    pixi run serve          # in one terminal — boots an empty Lab
    pixi run sensor-demo    # in another — POSTs the demo to the running Lab

What it does:

1. Apply the ``mammos`` bootstrap via ``POST /bootstraps/apply`` — this
   probes the WSL pixi env (``~/autolab-mammos`` by default) and
   registers the ``vm-primary`` Resource, the two sensor Operations
   (``mammos.sensor_material_at_T`` + ``mammos.sensor_shape_fom``) plus
   the older 6-step material-chain Operations, and two WorkflowTemplates
   (``sensor_shape_opt`` = the MVP and ``mammos_sensor`` = full chain).

2. Create one *prepared* Campaign with ``autostart=false`` — it enters the
   ledger in ``status="queued"`` and shows up in the Console ready to
   start. The user clicks Start in the UI to kick it off.

3. Print a summary of the /status endpoint so you can visually confirm
   nothing is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request


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
        body = e.read().decode(errors="replace")
        raise SystemExit(f"[error] POST {path} → HTTP {e.code}: {body}") from None


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
        help="Register bootstrap only; do not create the prepared campaign.",
    )
    parser.add_argument(
        "--planner",
        default="optuna",
        choices=("optuna", "claude"),
        help="Planner to use for the prepared campaign (default: optuna).",
    )
    args = parser.parse_args()

    # --- 1. Probe health -----------------------------------------------------
    try:
        with urllib.request.urlopen(_url(args.base, "/health"), timeout=10) as r:
            _ = r.read()  # body is "ok", not JSON
    except Exception as exc:
        print(f"[error] Lab is not reachable at {args.base}: {exc}", file=sys.stderr)
        print("        Start it first with: pixi run serve", file=sys.stderr)
        return 2

    # --- 2. Apply the minimal sensor shape-opt bootstrap --------------------
    # This registers ONLY what the sensor_shape_opt workflow needs:
    # vm-primary resource, two sensor operations, one workflow. No full
    # materials chain, no annotation_extract — demos don't pollute the Lab.
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

    # --- 3. Create the prepared campaign ------------------------------------
    if not args.skip_campaign:
        if args.planner == "optuna":
            campaign_body = {
                "name": "sensor-shape-opt (optuna)",
                "description": (
                    "Shape-optimise a Permalloy superellipse sensor (Ni80Fe20 @ 300 K). "
                    "Optuna TPE sweeps (sx_nm, sy_nm) over the linear-region width Hmax. "
                    "Prepared — start from the Console."
                ),
                "objective": {"key": "Hmax_A_per_m", "direction": "maximise"},
                "budget": 12,
                "parallelism": 1,
                "priority": 50,
                "planner": "optuna",
                "planner_config": {
                    "operation": "mammos.sensor_shape_fom",
                    "search_space": {
                        "sx_nm": {"type": "float", "low": 5.0, "high": 70.0},
                        "sy_nm": {"type": "float", "low": 5.0, "high": 70.0},
                    },
                },
                "workflow": None,
                "autostart": False,
            }
        else:  # claude
            campaign_body = {
                "name": "sensor-shape-opt (claude)",
                "description": (
                    "Same objective as the Optuna campaign — Claude as planner. "
                    "Reads campaign history and reasons about the next (sx_nm, sy_nm) "
                    "to try. Requires ANTHROPIC_API_KEY on the server. Prepared — "
                    "start from the Console."
                ),
                "objective": {"key": "Hmax_A_per_m", "direction": "maximise"},
                "budget": 12,
                "parallelism": 1,
                "priority": 50,
                "planner": "claude",
                "planner_config": {},
                "use_claude_policy": True,
                "workflow": None,
                "autostart": False,
            }
        print(f"[2/3] POST {args.base}/campaigns  (autostart=false, planner={args.planner})")
        camp = _post(args.base, "/campaigns", campaign_body)
        print(
            f"      campaign_id={camp['campaign_id']}  "
            f"name={camp['name']!r}  status={camp.get('status', '?')}"
        )
    else:
        print("[2/3] (skipped campaign creation)")

    # --- 4. Verify by hitting /status ---------------------------------------
    print(f"[3/3] GET  {args.base}/status  (verification)")
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

    # Sanity assertions.
    missing = []
    for r in ("this-pc", "vm-primary"):
        if r not in resources:
            missing.append(f"resource {r}")
    if "sensor_shape_opt" not in workflows:
        missing.append("workflow sensor_shape_opt")
    for t in ("mammos.sensor_material_at_T", "mammos.sensor_shape_fom"):
        if t not in tools:
            missing.append(f"tool {t}")
    # The minimal sensor_shape_opt bootstrap must not pollute the Lab.
    unexpected = sorted(set(tools) - {"mammos.sensor_material_at_T", "mammos.sensor_shape_fom"})
    if unexpected:
        missing.append(f"unexpected extra tools: {unexpected}")
    unexpected_wf = sorted(set(workflows) - {"sensor_shape_opt"})
    if unexpected_wf:
        missing.append(f"unexpected extra workflows: {unexpected_wf}")
    if not args.skip_campaign:
        queued = [c for c in campaigns if c.get("status") == "queued"]
        if not queued:
            missing.append("prepared (queued) campaign")
    if missing:
        print("[error] verification failed: " + "; ".join(missing), file=sys.stderr)
        return 1
    print(
        "\n[done] sensor demo registered. Open the Console at "
        + args.base
        + " and click Start on the prepared campaign to kick it off."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
