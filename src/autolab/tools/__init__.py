"""Capability-named Tool registry.

Each Tool is declared in a YAML file naming a scientific capability
(`micromagnetics_hysteresis`, not `ubermag_hysteresis`) with typed inputs,
typed outputs, a target Resource kind, and an adapter module path. The MCP
gateway reads this registry and exposes every declared capability over MCP.
The Tool declaration's SHA-256 lands in every Record the Tool produces;
updating a declaration is a provenance-visible event.

External libraries (MaMMoS, ubermag, real instruments) are wrapped by
autolab-owned adapters in `src/autolab/tools/adapters/`. Ownership of the
adapter is how the provenance contract is guaranteed.
"""

from __future__ import annotations
