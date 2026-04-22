"""Verify the wsl_demo bootstrap against a real Lab + real WSL."""
import sys, pathlib, tempfile, asyncio
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from autolab.lab import Lab
from examples.wsl_demo.bootstrap import bootstrap
from examples.wsl_demo.operations import WslInfo, WslNumpyEval

with tempfile.TemporaryDirectory() as tmp:
    lab = Lab(root=pathlib.Path(tmp) / "lab")
    bootstrap(lab)

    resources = [r.name for r in lab.resources.list()]
    tools = [d.capability for d in lab.tools.list()]
    workflows = list(lab._workflows.keys())

    print("Resources:", resources)
    print("Capabilities:", tools)
    print("Workflows:", workflows)

    assert "wsl-ubuntu" in resources
    assert "wsl_info" in tools
    assert "wsl_numpy_eval" in tools
    assert "wsl_health_check" in workflows
    assert "wsl_compute_chain" in workflows
    assert "wsl_wave_eval" in workflows

async def run_ops():
    # wsl_info
    r = await WslInfo().run({})
    assert r.status == "completed", r.outputs
    print(f"wsl_info: Python {r.outputs['python']}, numpy {r.outputs['numpy']}")

    # wsl_numpy_eval basic
    r2 = await WslNumpyEval().run({"x": 3.14159, "expression": "np.sin(x)**2 + np.cos(x)**2"})
    assert r2.status == "completed"
    assert abs(r2.outputs["result"] - 1.0) < 1e-4
    print(f"wsl_numpy_eval(Pythagorean): {r2.outputs['result']:.6f}")

    # wave function
    r3 = await WslNumpyEval().run({"x": 1.15, "expression": "np.sin(x) * np.cos(x/2)"})
    assert r3.status == "completed"
    assert r3.outputs["result"] > 0.7
    print(f"wsl_numpy_eval(wave at x=1.15): {r3.outputs['result']:.4f}")

    # chain test (x^2 then sqrt)
    r4 = await WslNumpyEval().run({"x": 7.5, "expression": "x**2"})
    r5 = await WslNumpyEval().run({"x": r4.outputs["result"], "expression": "np.sqrt(x)"})
    assert abs(r5.outputs["result"] - 7.5) < 1e-4
    print(f"chain sqrt(7.5^2) = {r5.outputs['result']:.4f} (expect 7.5)")

    print("\nAll assertions PASS.")

asyncio.run(run_ops())
