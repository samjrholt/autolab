"""End-to-end test: boot the server with add_demo bootstrap, submit a campaign
using the WorkflowChainOptimizer planner, wait for it to finish, then verify:
  - add_two records exist (step 1 of each trial)
  - add_three records exist (step 2, chained via react())
  - best add_three.result >= 14.0 (Optuna converging to x≈10 → result=15)

Run:
    PYTHONPATH=. pixi run python examples/add_demo/test_e2e.py
"""
from __future__ import annotations
import subprocess, sys, time, os, pathlib, atexit
import httpx

PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"

# ---- Start server -------------------------------------------------------
env = os.environ.copy()
env["AUTOLAB_BOOTSTRAP"] = "add_demo"
env["PYTHONPATH"] = str(pathlib.Path(__file__).parent.parent.parent)

proc = subprocess.Popen(
    ["pixi", "run", "python", "-m", "uvicorn",
     "autolab.server.app:app", "--port", str(PORT), "--log-level", "warning"],
    env=env,
    cwd=pathlib.Path(__file__).parent.parent.parent,
)
atexit.register(proc.terminate)

for _ in range(30):
    try:
        r = httpx.get(f"{BASE}/status", timeout=2)
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(1)
else:
    proc.terminate()
    sys.exit("Server did not start in 30s")

print("Server up.")

# ---- Verify bootstrap ---------------------------------------------------
status = httpx.get(f"{BASE}/status").json()
resources = [r["name"] for r in status.get("resources", [])]
tools = [t["capability"] for t in status.get("tools", [])]
workflows = [w["name"] for w in status.get("workflows", [])]

assert "wsl-local" in resources, f"wsl-local missing: {resources}"
assert "add_two" in tools, f"add_two missing: {tools}"
assert "add_three" in tools, f"add_three missing: {tools}"
assert "add_two_then_three" in workflows, f"workflow missing: {workflows}"
print(f"Bootstrap OK — resources={resources}, tools={tools}")

# ---- Submit campaign ----------------------------------------------------
campaign_body = {
    "name": "find_max_add_demo",
    "description": "Maximise x+5 via add_two→add_three. Optimal x=10 → result=15.",
    "objective": {"key": "result", "direction": "maximise"},
    "budget": 20,
    "planner": "add_demo_optuna",
    "planner_config": {},
}
resp = httpx.post(f"{BASE}/campaigns", json=campaign_body)
assert resp.status_code == 200, f"Campaign submit failed: {resp.text}"
cid = resp.json()["campaign_id"]
print(f"Campaign submitted: {cid}")

# ---- Wait for completion ------------------------------------------------
for attempt in range(90):
    time.sleep(2)
    st = httpx.get(f"{BASE}/status").json()
    camp = next((c for c in st.get("campaigns", []) if c["campaign_id"] == cid), {})
    status_str = camp.get("status", "unknown")
    completed_count = len([
        r for r in httpx.get(f"{BASE}/ledger?campaign_id={cid}&limit=100").json().get("records", [])
        if r.get("record_status") == "completed"
    ])
    print(f"  [{attempt*2}s] campaign={status_str}, completed_records={completed_count}")
    if status_str in ("completed", "failed", "stopped"):
        break
else:
    proc.terminate()
    sys.exit("Campaign did not complete in 180s")

assert status_str == "completed", f"Campaign ended: {status_str}"
print("Campaign completed.")

# ---- Check ledger -------------------------------------------------------
records = httpx.get(f"{BASE}/ledger?campaign_id={cid}&limit=200").json().get("records", [])
completed_add_two = [r for r in records if r["operation"] == "add_two" and r["record_status"] == "completed"]
completed_add_three = [r for r in records if r["operation"] == "add_three" and r["record_status"] == "completed"]

print(f"add_two runs: {len(completed_add_two)}, add_three runs: {len(completed_add_three)}")
assert len(completed_add_two) > 0, "No completed add_two records"
assert len(completed_add_three) > 0, "No completed add_three records — react() chain broken"

# Verify chain integrity: each add_two result should equal add_three input
for r3 in completed_add_three[:3]:
    x_in = (r3.get("inputs") or {}).get("x")
    result = (r3.get("outputs") or {}).get("result")
    if x_in is not None and result is not None:
        assert abs(result - x_in - 3.0) < 0.001, f"add_three math wrong: {x_in} + 3 != {result}"

best = max((r.get("outputs") or {}).get("result", 0) for r in completed_add_three)
print(f"Best result: {best:.2f} (optimal = 15.0)")
assert best >= 14.0, f"Optuna did not converge: best={best}"

print(f"\nAll assertions PASS. Best result = {best:.2f}/15.0 optimal.")
proc.terminate()
