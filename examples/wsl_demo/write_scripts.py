"""Write WSL scripts via subprocess — run once to populate ~/autolab-wsl/scripts/."""
import subprocess, sys

SCRIPTS = {
    "numpy_eval.py": '''\
import sys, json, math
import numpy as np
from scipy import stats

x = float(sys.argv[1])
expression = sys.argv[2]
ns = {"np": np, "math": math, "stats": stats, "x": x}
result = float(eval(expression, ns))
print(json.dumps({"result": result, "x": x, "expression": expression}))
''',

    "health.py": '''\
import json, sys, platform, os

packages = {}
for pkg in ["numpy", "scipy", "matplotlib", "pandas"]:
    try:
        m = __import__(pkg)
        packages[pkg] = getattr(m, "__version__", "installed")
    except ImportError:
        packages[pkg] = None

print(json.dumps({
    "python": sys.version.split()[0],
    "hostname": platform.node(),
    "system": platform.system(),
    "machine": platform.machine(),
    "cpus": os.cpu_count(),
    "packages": packages,
    "pixi_env": os.environ.get("PIXI_ENVIRONMENT_NAME", "none"),
}))
''',
}

PIXI_TOML = '''\
[workspace]
name = "autolab-wsl"
version = "0.1.0"
description = "Scientific Python environment for autolab WSL capabilities"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
python = "3.12.*"
numpy = ">=1.26"
scipy = ">=1.12"
matplotlib = ">=3.8"
pandas = ">=2.0"
'''

def run(cmd):
    r = subprocess.run(["wsl", "-e", "bash", "-c", cmd],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"WARN: {cmd!r} -> {r.stderr.strip()}", file=sys.stderr)
    return r.stdout.strip()

def write_wsl(path, content):
    """Write content to a WSL path using stdin as UTF-8 bytes."""
    subprocess.run(
        ["wsl", "-e", "bash", "-c", f"cat > {path}"],
        input=content.encode("utf-8"),
        check=True,
    )

if __name__ == "__main__":
    run("mkdir -p /home/sam/autolab-wsl/scripts")
    write_wsl("/home/sam/autolab-wsl/pixi.toml", PIXI_TOML)
    for name, content in SCRIPTS.items():
        write_wsl(f"/home/sam/autolab-wsl/scripts/{name}", content)
    # Re-install in case pixi.toml changed
    r = subprocess.run(
        ["wsl", "-e", "bash", "-c",
         "cd /home/sam/autolab-wsl && /home/sam/.pixi/bin/pixi install 2>&1 | tail -3"],
        capture_output=True, text=True
    )
    print(r.stdout)
    # Verify
    out = run("cd /home/sam/autolab-wsl && /home/sam/.pixi/bin/pixi run python3 scripts/health.py")
    import json
    info = json.loads(out)
    print(f"WSL env ready: Python {info['python']}, numpy {info['packages']['numpy']}")
    out2 = run("cd /home/sam/autolab-wsl && /home/sam/.pixi/bin/pixi run python3 scripts/numpy_eval.py 3.14159 'np.sin(x)**2 + np.cos(x)**2'")
    res = json.loads(out2)
    assert abs(res["result"] - 1.0) < 1e-6, f"sin^2+cos^2 should be 1, got {res}"
    print(f"numpy_eval ok: sin2(x)+cos2(x)={res['result']:.6f} (expect 1.0)")
    print("All WSL scripts verified.")
