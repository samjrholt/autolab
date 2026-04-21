"""Example workflows.

Each subpackage under this package is a registered set of Operations, Tool
YAMLs, and optional Skills for a specific science vertical — e.g. a
MaMMoS-style hard-magnet pipeline (MLIP relax → `mammos-dft` → Kuzmin →
`mammos-mumag` → Hc).

The framework does not depend on any example. Swapping the example is an
adapter-and-YAML change, not a framework code change.
"""

from __future__ import annotations
