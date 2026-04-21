"""MaMMoS sensor demonstrator on autolab.

Reimplements the MaMMoS multiscale chain
(https://mammos-project.github.io/mammos/demonstrator/sensor.html) as a
set of reusable :class:`~autolab.Operation` subclasses executed on a
VM resource (WSL by default). The chain is modelled as a
:class:`~autolab.WorkflowTemplate` so the same steps can be composed
into different campaigns.

Scope of reusability
--------------------

**Material-parameter operations** (domain-agnostic, reusable for any
candidate magnetic material):

- :class:`StructureRelax` — MLIP relaxation (MACE / CHGNet / MatterSim)
- :class:`IntrinsicMagnetics0K` — Ms, K1, A_ex at 0 K from DFT / AI
- :class:`FiniteTemperatureMagnetics` — Ms(T), K1(T), Tc via spin
  dynamics + Kuzmin fit

**Sensor-specific operations**:

- :class:`SensorMesh` — superellipse free-layer mesh
- :class:`MicromagneticHysteresis` — H-M loop via mammos-mumag
- :class:`SensorFigureOfMerit` — sensitivity, linear range, Hc, Mr/Ms

Swap a material-parameter operation (e.g. pull from a database instead
of computing) and the sensor operations keep working — the Ms/K1/A_ex
contract is the interface.
"""

from __future__ import annotations

from examples.mammos_sensor.vm import VMConfig, VMError, VMExecutor, probe_vm

__all__ = ["VMConfig", "VMError", "VMExecutor", "probe_vm"]
