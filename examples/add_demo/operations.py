"""add_two and add_three Operations for the add_demo example.

These are the simplest possible real Operations: they read ``x`` from
inputs and return ``result = x + k``.  They exist to test the whole
framework stack without needing WSL, SSH, or any external tool.

The "run on WSL" use case: replace the body of ``run`` with a
``ShellCommand``-style call that SSHes into WSL and runs a Python
one-liner.  The capability name, inputs, and outputs are identical; only
the adapter changes.  That is the whole point of the Operation interface.
"""

from __future__ import annotations

from typing import Any

from autolab.models import OperationResult
from autolab.operations.base import Operation, OperationContext


class AddTwo(Operation):
    """Return ``result = x + 2``."""

    capability = "add_two"
    resource_kind = None
    module = "examples.add_demo.v1"
    typical_duration = 0.01

    async def run(
        self,
        inputs: dict[str, Any],
        context: OperationContext | None = None,
    ) -> OperationResult:
        try:
            x = float(inputs["x"])
        except (KeyError, TypeError, ValueError) as exc:
            return OperationResult(status="failed", outputs={"reason": f"bad input: {exc}"})
        return OperationResult(status="completed", outputs={"result": x + 2.0})


class AddThree(Operation):
    """Return ``result = x + 3``."""

    capability = "add_three"
    resource_kind = None
    module = "examples.add_demo.v1"
    typical_duration = 0.01

    async def run(
        self,
        inputs: dict[str, Any],
        context: OperationContext | None = None,
    ) -> OperationResult:
        try:
            x = float(inputs["x"])
        except (KeyError, TypeError, ValueError) as exc:
            return OperationResult(status="failed", outputs={"reason": f"bad input: {exc}"})
        return OperationResult(status="completed", outputs={"result": x + 3.0})


__all__ = ["AddTwo", "AddThree"]
