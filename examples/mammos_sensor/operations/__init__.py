"""MaMMoS demonstrator operations.

Material-parameter operations (reusable for any candidate magnetic material):

- :class:`StructureRelax`
- :class:`IntrinsicMagnetics0K`
- :class:`FiniteTemperatureMagnetics`

Sensor-specific operations:

- :class:`SensorMesh`
- :class:`MicromagneticHysteresis`
- :class:`SensorFigureOfMerit`

Each operation follows a consistent pattern:

1. Declare a Pydantic ``Inputs`` and ``Outputs`` inner model so the
   schema is derived (not hand-authored) and the DatasetBuilder gets
   stable column names.
2. Dispatch to a ``mammos`` backend inside the VM when available; fall
   back to a labelled surrogate when not.
3. Stamp ``outputs["backend"]`` with the backend that actually ran so
   every Record carries a visible provenance breadcrumb — the framework
   invariant *"surrogates are never silently substituted"*.
4. Map VM-level failures to ``failure_mode="equipment_failure"`` and
   script-level failures to ``failure_mode="process_deviation"``.
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

ALL_OPERATIONS = (
    StructureRelax,
    IntrinsicMagnetics0K,
    FiniteTemperatureMagnetics,
    SensorMesh,
    MicromagneticHysteresis,
    SensorFigureOfMerit,
)

__all__ = [
    "ALL_OPERATIONS",
    "FiniteTemperatureMagnetics",
    "IntrinsicMagnetics0K",
    "MicromagneticHysteresis",
    "SensorFigureOfMerit",
    "SensorMesh",
    "StructureRelax",
]
