"""WSL-backed Operations for the wsl_demo example.

Each Operation calls into the WSL pixi environment (Python 3.12 + numpy +
scipy) via wsl.exe subprocess.  The backend pattern is intentionally simple:
no asyncssh needed, no extra config, just wsl.exe on PATH.

Capabilities registered here
------------------------------
wsl_info        No inputs. Returns system info dict (python, packages, cpus).
wsl_numpy_eval  Inputs: x (float), expression (str using np.* and x).
                Returns: result (float). Example: expression="np.sin(x)**2".
"""
from __future__ import annotations

from typing import Any

from autolab.models import OperationResult
from autolab.operations.base import Operation, OperationContext

from examples.wsl_demo.wsl import run_pixi_script


class WslInfo(Operation):
    """Gather system information from the WSL pixi environment."""

    capability = "wsl_info"
    resource_kind = None
    module = "examples.wsl_demo.v1"
    typical_duration = 3.0

    async def run(
        self, inputs: dict[str, Any], context: OperationContext | None = None
    ) -> OperationResult:
        try:
            info = run_pixi_script("health.py", timeout=15)
        except Exception as exc:
            return OperationResult(status="failed", outputs={"reason": str(exc)})

        return OperationResult(
            status="completed",
            outputs={
                "python": info.get("python"),
                "hostname": info.get("hostname"),
                "cpus": info.get("cpus"),
                "numpy": info.get("packages", {}).get("numpy"),
                "scipy": info.get("packages", {}).get("scipy"),
                "matplotlib": info.get("packages", {}).get("matplotlib"),
                "pixi_env": info.get("pixi_env"),
            },
        )


class WslNumpyEval(Operation):
    """Evaluate a numpy expression for a given x in the WSL pixi environment.

    Inputs
    ------
    x : float
        The value of the variable 'x' in the expression.
    expression : str
        A Python expression using 'x' and 'np.*' (numpy) or 'stats.*' (scipy.stats).
        Examples:
          - "np.sin(x) * np.cos(x / 2)"
          - "x ** 2 - 3 * x + 2"
          - "np.exp(-x**2 / 2) / np.sqrt(2 * np.pi)"

    Outputs
    -------
    result : float
        The evaluated value.
    x : float
        The input x (echoed for traceability).
    """

    capability = "wsl_numpy_eval"
    resource_kind = None
    module = "examples.wsl_demo.v1"
    typical_duration = 2.0

    async def run(
        self, inputs: dict[str, Any], context: OperationContext | None = None
    ) -> OperationResult:
        try:
            x = float(inputs["x"])
        except (KeyError, TypeError, ValueError) as exc:
            return OperationResult(status="failed", outputs={"reason": f"bad input x: {exc}"})

        expression = str(inputs.get("expression", "x"))

        try:
            data = run_pixi_script("numpy_eval.py", str(x), expression, timeout=15)
        except Exception as exc:
            return OperationResult(status="failed", outputs={"reason": str(exc)})

        return OperationResult(
            status="completed",
            outputs={
                "result": data["result"],
                "x": data["x"],
                "expression": data["expression"],
            },
        )


__all__ = ["WslInfo", "WslNumpyEval"]
