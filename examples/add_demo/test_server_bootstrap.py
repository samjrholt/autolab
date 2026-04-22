"""Simulate exactly what the server does at startup: no PYTHONPATH tricks."""
import os, sys, pathlib, subprocess, time, atexit
import httpx

PORT = 8002
BASE = f"http://127.0.0.1:{PORT}"

env = os.environ.copy()
env["AUTOLAB_BOOTSTRAP"] = "add_demo"
# Deliberately NOT setting PYTHONPATH — server must work without it

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
    sys.exit("Server did not start")

status = httpx.get(f"{BASE}/status").json()
resources = [r["name"] for r in status.get("resources", [])]
tools = [t["capability"] for t in status.get("tools", [])]
workflows = [w["name"] for w in status.get("workflows", [])]

print("Resources:", resources)
print("Tools:", tools)
print("Workflows:", workflows)

assert "wsl-local" in resources, f"wsl-local missing: {resources}"
assert "add_two" in tools, f"add_two missing: {tools}"
assert "add_three" in tools, f"add_three missing: {tools}"
assert "add_two_then_three" in workflows, f"workflow missing: {workflows}"
print("\nBootstrap verified — all resources, capabilities and workflow present. PASS.")
proc.terminate()
