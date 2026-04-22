"""Verify the add_demo bootstrap runs cleanly against a real Lab instance."""
import sys
sys.path.insert(0, ".")

import tempfile, pathlib
from autolab.lab import Lab
from examples.add_demo.bootstrap import bootstrap

lab = Lab(root=pathlib.Path(tempfile.mkdtemp()) / "test_lab")
bootstrap(lab)

resources = [r.name for r in lab.resources.list()]
tools = [d.capability for d in lab.tools.list()]
workflows = list(lab._workflows.keys())

print("Resources:", resources)
print("Tools:", tools)
print("Workflows:", workflows)

assert "wsl-local" in resources, "wsl-local resource missing"
assert "add_two" in tools, "add_two capability missing"
assert "add_three" in tools, "add_three capability missing"
assert "add_two_then_three" in workflows, "workflow missing"

# Run the operations directly
import asyncio
from examples.add_demo.operations import AddTwo, AddThree

async def run():
    r2 = await AddTwo().run({"x": 7.0})
    assert r2.status == "completed" and r2.outputs["result"] == 9.0, r2
    r3 = await AddThree().run({"x": r2.outputs["result"]})
    assert r3.status == "completed" and r3.outputs["result"] == 12.0, r3
    print(f"\nadd_two(7)={r2.outputs['result']}, add_three(9)={r3.outputs['result']}")
    print("All assertions PASS.")

asyncio.run(run())
