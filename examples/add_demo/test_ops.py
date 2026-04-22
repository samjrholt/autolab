import asyncio
from examples.add_demo.operations import AddTwo, AddThree

async def test():
    r2 = await AddTwo().run({"x": 5})
    assert r2.status == "completed"
    assert r2.outputs["result"] == 7.0

    r3 = await AddThree().run({"x": r2.outputs["result"]})
    assert r3.status == "completed"
    assert r3.outputs["result"] == 10.0

    print(f"add_two(5)={r2.outputs['result']}, add_three(7)={r3.outputs['result']} — PASS")

asyncio.run(test())
