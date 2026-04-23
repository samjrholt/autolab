"""Strict-backend mode for the MaMMoS sensor demonstrator.

The sensor example has two host-side execution paths per Operation:

- the real path — whatever the VM-side script succeeded at (``mammos_mumag``,
  ``ubermag``, ``mace_torch``, …);
- a closed-form surrogate fallback used when none of the real backends is
  installed in the VM.

By default, the demo runs in **strict mode**: the surrogate path is
disabled entirely and any VM-side script failure propagates as a Record
with ``status="failed"``. That keeps the provenance story honest and
matches the framework invariant *"surrogates are never silently
substituted"* — in strict mode they are not substituted *at all*.

The surrogate path is still useful in CI where nobody is going to stand
up a WSL pixi environment. Opt back in per-run with::

    $env:AUTOLAB_MAMMOS_ALLOW_SURROGATE = "1"

Records produced on the surrogate path already stamp ``outputs.backend =
"surrogate"`` so downstream consumers can filter them out.
"""

from __future__ import annotations

import os

from autolab.models import OperationResult

_STRICT_ENV = "AUTOLAB_MAMMOS_ALLOW_SURROGATE"


def strict_mode() -> bool:
    """Return True iff surrogate fallbacks are forbidden.

    Default is strict. The env var ``AUTOLAB_MAMMOS_ALLOW_SURROGATE=1``
    re-enables fallbacks for CI / offline testing.
    """
    return os.environ.get(_STRICT_ENV, "").lower() not in ("1", "true", "yes", "on")


_SETUP_HINT = (
    "Set up the WSL pixi environment described in "
    "examples/mammos_sensor/README.md (`~/autolab-mammos`), or set "
    "AUTOLAB_MAMMOS_ALLOW_SURROGATE=1 to allow closed-form fallbacks."
)


def strict_failure(operation: str, exc: Exception) -> OperationResult:
    """Return a clean ``failed`` OperationResult when a real backend is required."""
    return OperationResult(
        status="failed",
        error=(
            f"{operation}: real backend unavailable in VM and surrogate "
            f"fallback is disabled.\n"
            f"Underlying error: {exc}\n"
            f"{_SETUP_HINT}"
        ),
        failure_mode="process_deviation",
    )


__all__ = ["strict_failure", "strict_mode"]
