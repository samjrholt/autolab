"""Run directly: PYTHONPATH=. pixi run python examples/wsl_demo/debug_bootstrap.py"""
import sys, os, logging, pathlib, tempfile
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

print(f"CWD: {os.getcwd()}")
print(f"AUTOLAB_BOOTSTRAP env: {os.environ.get('AUTOLAB_BOOTSTRAP', '(not set)')}")
print(f"'examples' importable: ", end="")
try:
    import examples.wsl_demo.bootstrap
    print("YES")
except ImportError as e:
    print(f"NO — {e}")

print()

# Simulate exactly what _bootstrap() does
os.environ["AUTOLAB_BOOTSTRAP"] = "wsl_demo"
sys.path.insert(0, os.getcwd())

from autolab.lab import Lab
lab = Lab(root=pathlib.Path(tempfile.mkdtemp()) / "lab")

try:
    from examples.wsl_demo.bootstrap import bootstrap
    bootstrap(lab)
    print("Bootstrap SUCCESS")
    print("  Resources:", [r.name for r in lab.resources.list()])
    print("  Tools:", [t.capability for t in lab.tools.list()])
    print("  Workflows:", list(lab._workflows.keys()))
except Exception as exc:
    print(f"Bootstrap FAILED: {exc!r}")
    import traceback; traceback.print_exc()
