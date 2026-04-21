"""Append-only, hashed, write-ahead Record store.

Framework-enforced provenance: every Operation the Orchestrator wraps produces
a Record that is persisted (SQLite + JSONL, dual-write) before the Operation
runs, updated as it completes, and never mutated thereafter. Corrections are
Annotations — new Records pointing at existing ones.

See docs/design/autolab-ideas-foundation.md §6 for the full invariants.
"""

from __future__ import annotations
