"""Operations — the atomic work unit.

An Operation is anything that transforms, measures, or analyses — synthesis,
characterisation, simulation, post-processing. Each Operation declares its
Resource kind, its capability requirements, whether it produces a Sample,
and whether it is destructive. Operations never write to the ledger directly;
the Orchestrator wraps every call.
"""

from __future__ import annotations
