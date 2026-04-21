"""Tool adapters — the Python side of each YAML Tool declaration.

Each adapter wraps an external library or a simulated backend and implements
the input / output contract declared in the corresponding YAML. One adapter
per capability. Adapters are autolab-owned so the provenance contract stays
verifiable.
"""

from __future__ import annotations
