"""Quick status snapshot of the Optuna-vs-Claude rehearsal."""
from __future__ import annotations
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
OPTUNA = "camp-66e8129e36"
CLAUDE = "camp-223d4804cc"


def fetch_campaign(cid: str) -> dict:
    with urllib.request.urlopen(f"{BASE}/campaigns/{cid}", timeout=60) as r:
        return json.loads(r.read())


def fetch_ledger() -> list[dict]:
    with urllib.request.urlopen(f"{BASE}/ledger?limit=2000", timeout=60) as r:
        return json.loads(r.read()).get("records", [])


all_records = fetch_ledger()
for label, cid in (("OPTUNA", OPTUNA), ("CLAUDE", CLAUDE)):
    d = fetch_campaign(cid)
    records = [r for r in all_records if r.get("campaign_id") == cid]
    by_status: dict[str, int] = {}
    for r in records:
        s = r.get("record_status", "?")
        by_status[s] = by_status.get(s, 0) + 1
    fom_records = [r for r in records if r.get("operation") == "mammos.sensor_shape_fom"]
    completed_fom = [r for r in fom_records if r.get("record_status") == "completed"]
    best = None
    for r in completed_fom:
        h = (r.get("outputs") or {}).get("Hmax_A_per_m")
        if h is None:
            continue
        if best is None or h > best:
            best = h
    print(
        f"{label}: status={d.get('status')} total={len(records)} {by_status} "
        f"fom_done={len(completed_fom)} best_Hmax={best}"
    )
