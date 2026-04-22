"""Bootstrap the superellipse-sensor example into a running Lab service.

Set ``AUTOLAB_BOOTSTRAP=examples.superellipse_sensor.server_bootstrap:bootstrap``
before ``pixi run serve`` to pre-register the example Tool + Resource
so the Console can drive a real campaign against it.
"""

from __future__ import annotations

from pathlib import Path

from autolab import Lab, Resource


HERE = Path(__file__).parent


def bootstrap(lab: Lab) -> None:
    lab.register_resource(
        Resource(
            name="this-machine",
            kind="computer",
            capabilities={"cores_gte": 1, "has_oommf": False},
            description="Local box running ubermag (or its surrogate).",
            typical_operation_durations={"superellipse_hysteresis": 8},
        )
    )
    decl = lab.register_tool(HERE / "tool.yaml")
    print(
        f"[superellipse bootstrap] registered tool {decl.name!r} "
        f"hash={decl.declaration_hash[:12]}…"
    )
