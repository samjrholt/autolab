"""Long-running watcher: snapshots both campaigns every 30s until both
reach a terminal status (completed / stopped / failed / cancelled).
Writes a single line of progress per snapshot to stdout."""
from __future__ import annotations
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
OPTUNA = "camp-66e8129e36"
CLAUDE = "camp-223d4804cc"
TERMINAL = {"completed", "stopped", "failed", "cancelled"}


def fetch_campaign(cid: str) -> dict:
    try:
        with urllib.request.urlopen(f"{BASE}/campaigns/{cid}", timeout=60) as r:
            return json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        return {"status": f"err:{type(exc).__name__}"}


def fetch_ledger() -> list[dict]:
    try:
        with urllib.request.urlopen(f"{BASE}/ledger?limit=2000", timeout=60) as r:
            return json.loads(r.read()).get("records", [])
    except Exception:
        return []


def summary(cid: str, all_records: list[dict]) -> tuple[str, str]:
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
    return (
        d.get("status", "?"),
        f"total={len(records)} {by_status} fom_done={len(completed_fom)} best_Hmax={best}",
    )


t0 = time.time()
while True:
    elapsed = int(time.time() - t0)
    all_records = fetch_ledger()
    o_status, o_sum = summary(OPTUNA, all_records)
    c_status, c_sum = summary(CLAUDE, all_records)
    print(f"[{elapsed:4d}s] OPTUNA[{o_status}] {o_sum} | CLAUDE[{c_status}] {c_sum}", flush=True)
    if o_status in TERMINAL and c_status in TERMINAL:
        print(f"[{elapsed:4d}s] Both terminal — exiting watcher.")
        break
    time.sleep(30)
    if elapsed > 60 * 60:
        print("[timeout] watcher hit 60 min ceiling — exiting.")
        break
