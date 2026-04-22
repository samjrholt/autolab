"""Operations for wsl_ssh_demo: add_two and cube, each executed on WSL via SSH."""

from __future__ import annotations

from typing import Any

from autolab.models import OperationResult
from autolab.operations.base import Operation, OperationContext

from examples.wsl_ssh_demo.ssh import run_script


class WslAddTwo(Operation):
    """Return ``result = x + 2``, computed by a remote script on WSL."""

    capability = "add_two"
    resource_kind = "computer"
    module = "examples.wsl_ssh_demo.v1"
    typical_duration = 0.5

    async def run(
        self,
        inputs: dict[str, Any],
        context: OperationContext | None = None,
    ) -> OperationResult:
        try:
            x = float(inputs["x"])
        except (KeyError, TypeError, ValueError) as exc:
            return OperationResult(status="failed", outputs={"reason": f"bad input x: {exc}"})
        try:
            data = run_script("add_two.py", str(x))
        except Exception as exc:  # noqa: BLE001
            return OperationResult(status="failed", outputs={"reason": str(exc)})
        return OperationResult(
            status="completed",
            outputs={"result": float(data["result"]), "x": float(data["x"])},
        )


class WslCube(Operation):
    """Return ``result = x ** 3``, computed by a remote script on WSL."""

    capability = "cube"
    resource_kind = "computer"
    module = "examples.wsl_ssh_demo.v1"
    typical_duration = 0.5

    async def run(
        self,
        inputs: dict[str, Any],
        context: OperationContext | None = None,
    ) -> OperationResult:
        try:
            x = float(inputs["x"])
        except (KeyError, TypeError, ValueError) as exc:
            return OperationResult(status="failed", outputs={"reason": f"bad input x: {exc}"})
        try:
            data = run_script("cube.py", str(x))
        except Exception as exc:  # noqa: BLE001
            return OperationResult(status="failed", outputs={"reason": str(exc)})
        return OperationResult(
            status="completed",
            outputs={"result": float(data["result"]), "x": float(data["x"])},
        )


__all__ = ["WslAddTwo", "WslCube"]
