"""Boot the server using the same env as pixi run serve-wsl, check /debug/bootstrap."""
import subprocess, sys, time, os, pathlib, atexit
import httpx

PORT = 8003
BASE = f"http://127.0.0.1:{PORT}"

env = os.environ.copy()
env["PYTHONPATH"] = str(pathlib.Path(__file__).parent.parent.parent)
env["AUTOLAB_BOOTSTRAP"] = "wsl_demo"

proc = subprocess.Popen(
    ["pixi", "run", "python", "-m", "uvicorn",
     "autolab.server.app:app", "--port", str(PORT), "--log-level", "info"],
    env=env,
    cwd=pathlib.Path(__file__).parent.parent.parent,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
atexit.register(proc.terminate)

# Collect startup output
import threading
output_lines = []
def collect():
    for line in proc.stdout:
        output_lines.append(line.decode("ascii", errors="replace").rstrip())
t = threading.Thread(target=collect, daemon=True)
t.start()

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
    print("\n".join(output_lines[-20:]))
    sys.exit("Server did not start")

# Print relevant log lines
bootstrap_lines = [l for l in output_lines if any(k in l for k in ["bootstrap", "wsl", "ERROR", "WARNING", "resources=", "tools="])]
print("--- Bootstrap log lines ---")
for l in bootstrap_lines:
    print(l.encode("ascii", errors="replace").decode("ascii"))

# Check /debug/bootstrap
debug = httpx.get(f"{BASE}/debug/bootstrap").json()
print("\n--- /debug/bootstrap ---")
import json
print(json.dumps(debug, indent=2))

# Assert
assert "wsl-ubuntu" in debug["resources"], f"wsl-ubuntu missing: {debug}"
assert "wsl_info" in debug["capabilities"], f"wsl_info missing: {debug}"
assert "wsl_health_check" in debug["workflows"], f"wsl_health_check missing: {debug}"
print("\nSERVE-WSL TEST PASS: all resources, capabilities, and workflows present.")
proc.terminate()
