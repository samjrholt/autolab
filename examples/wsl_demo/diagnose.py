"""Run: pixi run python examples/wsl_demo/diagnose.py
Simulates exactly what the server does at startup to find why bootstrap fails.
"""
import sys, os

print("=== ENVIRONMENT ===")
print(f"CWD: {os.getcwd()}")
print(f"AUTOLAB_BOOTSTRAP: {os.environ.get('AUTOLAB_BOOTSTRAP', '(not set)')}")
print(f"PYTHONPATH env: {os.environ.get('PYTHONPATH', '(not set)')}")
print(f"sys.path[0:5]: {sys.path[:5]}")

print("\n=== IMPORT TEST ===")
# This is what _ensure_repo_on_path does
from pathlib import Path
cwd = str(Path.cwd())
if cwd not in sys.path:
    sys.path.insert(0, cwd)
    print(f"Added {cwd} to sys.path")
else:
    print(f"{cwd} already in sys.path")

try:
    from examples.wsl_demo.bootstrap import bootstrap
    print("examples.wsl_demo.bootstrap: IMPORTABLE")
except ImportError as e:
    print(f"examples.wsl_demo.bootstrap: IMPORT FAILED — {e}")
    sys.exit(1)

print("\n=== WSL CHECK ===")
try:
    from examples.wsl_demo.wsl import wsl_available, run_pixi_script
    ok = wsl_available()
    print(f"wsl_available(): {ok}")
    if ok:
        info = run_pixi_script("health.py")
        print(f"WSL Python: {info['python']}, numpy: {info['packages']['numpy']}")
except Exception as e:
    print(f"WSL check failed: {e}")

print("\n=== BOOTSTRAP TEST ===")
import tempfile, pathlib
from autolab.lab import Lab
lab = Lab(root=pathlib.Path(tempfile.mkdtemp()) / "lab")
try:
    bootstrap(lab)
    print(f"Resources: {[r.name for r in lab.resources.list()]}")
    print(f"Tools: {[t.capability for t in lab.tools.list()]}")
    print(f"Workflows: {list(lab._workflows.keys())}")
    print("Bootstrap: SUCCESS")
except Exception as e:
    import traceback
    print(f"Bootstrap FAILED: {e}")
    traceback.print_exc()
