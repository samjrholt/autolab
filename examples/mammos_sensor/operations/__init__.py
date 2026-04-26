"""MaMMoS demonstrator operations.

Two workflow shapes share these Operations:

- **Sensor shape-opt demo** (the MVP hackathon path). Two Operations
  that mirror the `MaMMoS sensor demonstrator
  <https://mammos-project.github.io/mammos/demonstrator/sensor.html>`_
  page verbatim:

  - :class:`SensorMaterialAtT` — Ms(T) + A(T) from the mammos-spindynamics
    DB with Kuzmin fit.
  - :class:`SensorShapeFOM` — elliptical mesh + OOMMF hysteresis loop +
    linear-segment analysis → Hmax (sensor FOM).

- **Full materials chain** (retained for the 6-step multiscale
  demonstrator). Run material design from composition up:

  - :class:`StructureRelax`
  - :class:`IntrinsicMagnetics0K`
  - :class:`FiniteTemperatureMagnetics`
  - :class:`SensorMesh`
  - :class:`MicromagneticHysteresis`
  - :class:`SensorFigureOfMerit`

Each Operation dispatches to a real backend inside the VM (``mammos-*``,
``ubermag``, OOMMF). When the VM-side script fails because the real
backend isn't installed, strict mode (default) returns a failed Record
with an actionable setup hint — **no silent surrogate substitution**.
Set ``AUTOLAB_MAMMOS_ALLOW_SURROGATE=1`` to opt back in to the closed-form
fallbacks for CI / offline use.
"""

from __future__ import annotations

from examples.mammos_sensor.operations.material import (
    FiniteTemperatureMagnetics,
    IntrinsicMagnetics0K,
    StructureRelax,
)
from examples.mammos_sensor.operations.sensor import (
    MicromagneticHysteresis,
    SensorFigureOfMerit,
    SensorMesh,
)
from examples.mammos_sensor.operations.sensor_demo import (
    SensorMaterialAtT,
    SensorShapeFOM,
)

ALL_OPERATIONS = (
    # Full materials chain (6 steps)
    StructureRelax,
    IntrinsicMagnetics0K,
    FiniteTemperatureMagnetics,
    SensorMesh,
    MicromagneticHysteresis,
    SensorFigureOfMerit,
    # Sensor shape-opt demo (2 steps)
    SensorMaterialAtT,
    SensorShapeFOM,
)

__all__ = [
    "ALL_OPERATIONS",
    "FiniteTemperatureMagnetics",
    "IntrinsicMagnetics0K",
    "MicromagneticHysteresis",
    "SensorFigureOfMerit",
    "SensorMaterialAtT",
    "SensorMesh",
    "SensorShapeFOM",
    "StructureRelax",
]
