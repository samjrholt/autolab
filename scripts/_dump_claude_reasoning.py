"""Dump Claude's planner reasoning across the rehearsal."""
from __future__ import annotations
import json
import math

mu0 = 4 * math.pi * 1e-7
LEDGER = "var/demo_lab/ledger/ledger.jsonl"
CLAUDE_CAMP = "camp-223d4804cc"


def main() -> None:
    with open(LEDGER, encoding="utf-8") as f:
        items = [json.loads(line) for line in f]

    # All claude planner claims, ordered by time.
    claims = [c for c in items if c.get("kind") == "claim" and c.get("author") == "claude/planner"]
    claims.sort(key=lambda c: c.get("created_at", ""))

    # Map FOM records (Claude campaign, completed) by created_at order = trial order.
    fom = sorted(
        [
            r for r in items
            if r.get("kind") == "record"
            and r.get("campaign_id") == CLAUDE_CAMP
            and r.get("operation") == "mammos.sensor_shape_fom"
            and r.get("record_status") == "completed"
        ],
        key=lambda r: r.get("created_at", ""),
    )

    print(f"=== Claude planner reasoning across {len(claims)} planner calls ===\n")
    for i, c in enumerate(claims, 1):
        body = c.get("body") or {}
        resp = body.get("response_text", "")
        try:
            parsed = json.loads(resp)
        except Exception:
            parsed = {"raw": resp}

        proposals = parsed.get("proposals", [])
        reason = parsed.get("reason", "")

        if i - 1 < len(fom):
            f = fom[i - 1]
            h = (f.get("outputs") or {}).get("Hmax_A_per_m", 0)
            sx = f.get("inputs", {}).get("sx_nm", 0)
            sy = f.get("inputs", {}).get("sy_nm", 0)
            outcome = f"  outcome: sx={sx:.1f} sy={sy:.1f}  Hmax={h*mu0*1e3:.1f} mT"
        else:
            outcome = ""

        print(f"--- Trial {i} ({c.get('created_at','')[:19]}) ---")
        if proposals:
            inp = proposals[0].get("inputs", {})
            rat = (proposals[0].get("decision") or {}).get("rationale", "")
            print(f"  proposed: material={inp.get('material')} sx={inp.get('sx_nm')} sy={inp.get('sy_nm')}")
            if rat:
                print(f"  rationale: {rat}")
        if reason:
            print(f"  reason:    {reason}")
        if outcome:
            print(outcome)
        print()


if __name__ == "__main__":
    main()
