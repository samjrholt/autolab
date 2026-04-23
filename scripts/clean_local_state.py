"""Wipe local state so the next ``pixi run serve`` boots from a clean slate.

Removes (relative to the repo root):

- ``.autolab-runs/``  — all ledger directories across all labs.
- ``.pytest_cache/``  — pytest's cache of last-failed test ids.
- ``frontend/.vite/`` and ``frontend/dist/``  — Vite build artefacts.

Does NOT touch the production static bundle at
``src/autolab/server/static/`` (that's committed source), node_modules,
or the pixi env.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    targets = [
        root / ".autolab-runs",
        root / ".pytest_cache",
        root / "frontend" / ".vite",
        root / "frontend" / "dist",
    ]
    removed: list[str] = []
    missing: list[str] = []
    for t in targets:
        if t.exists():
            shutil.rmtree(t, ignore_errors=True)
            removed.append(str(t.relative_to(root)))
        else:
            missing.append(str(t.relative_to(root)))

    if removed:
        print("removed:")
        for p in removed:
            print(f"  {p}")
    if missing:
        print("(already absent):")
        for p in missing:
            print(f"  {p}")
    print("\nclean state. ready for: pixi run serve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
