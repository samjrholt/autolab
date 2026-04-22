"""Shared pytest fixtures for the autolab test suite.

Philosophy: every test that touches persistent state gets its own
``tmp_path`` Lab — no shared state between tests. Fixtures here are
thin factory functions (``make_*``) because a single "one true Lab"
fixture encourages coupling between tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autolab import (
    AcceptanceCriteria,
    Campaign,
    Lab,
    Objective,
    OperationResult,
    Resource,
)
from autolab.operations.base import Operation

# ---------------------------------------------------------------------------
# Stub Operations — deterministic, tiny, dependency-free
# ---------------------------------------------------------------------------


class StubOp(Operation):
    """Operation that returns ``score = -(x - target)**2`` + a sample."""

    capability = "stub"
    resource_kind = "computer"
    produces_sample = True
    module = "stub.v1"

    async def run(self, inputs: dict[str, Any]) -> OperationResult:
        x = float(inputs["x"])
        target = float(inputs.get("target", 0.5))
        score = -((x - target) ** 2)
        return OperationResult(
            status="completed",
            outputs={"x": x, "score": score},
        )


class AlwaysFailsOp(Operation):
    """Operation that raises — used to exercise the failure path."""

    capability = "always_fails"
    resource_kind = "computer"
    module = "always_fails.v1"

    async def run(self, inputs: dict[str, Any]) -> OperationResult:
        raise RuntimeError("planned failure")


STUB_TOOL_DECL: dict[str, Any] = {
    "name": "stub",
    "capability": "stub",
    "version": "0.1.0",
    "module": "stub.v1",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.conftest:StubOp",
    "produces_sample": True,
    "destructive": False,
    "inputs": {"x": {"kind": "scalar"}, "target": {"kind": "scalar"}},
    "outputs": {"score": {"kind": "scalar"}, "x": {"kind": "scalar"}},
}

FAIL_TOOL_DECL: dict[str, Any] = {
    "name": "always_fails",
    "capability": "always_fails",
    "version": "0.1.0",
    "module": "always_fails.v1",
    "resource": "computer",
    "requires": {},
    "adapter": "tests.conftest:AlwaysFailsOp",
    "produces_sample": False,
    "destructive": False,
    "inputs": {},
    "outputs": {},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_lab(tmp_path: Path):
    """Return a factory that builds a fresh Lab in a subdirectory of ``tmp_path``.

    Usage::

        def test_x(make_lab):
            with make_lab() as lab:
                ...

    The factory can be called multiple times — each invocation gets its
    own subdirectory so two Labs don't share a ledger.
    """
    counter = {"n": 0}

    def _factory(
        *,
        lab_id: str = "lab-test",
        register_stub: bool = True,
        with_failing_tool: bool = False,
        resources: list[Resource] | None = None,
    ) -> Lab:
        counter["n"] += 1
        lab = Lab(tmp_path / f"lab-{counter['n']}", lab_id=lab_id)
        for res in resources or [
            Resource(name="pc-1", kind="computer", capabilities={"cores_gte": 4})
        ]:
            lab.register_resource(res)
        if register_stub:
            lab.register_tool_dict(STUB_TOOL_DECL)
        if with_failing_tool:
            lab.register_tool_dict(FAIL_TOOL_DECL)
        return lab

    return _factory


@pytest.fixture
def make_campaign():
    """Return a factory for a default stub Campaign."""

    def _factory(
        *,
        name: str = "stub-campaign",
        key: str = "score",
        direction: str = "maximise",
        rules: dict[str, dict[str, Any]] | None = None,
        budget: int = 8,
        parallelism: int = 1,
    ) -> Campaign:
        criteria = AcceptanceCriteria(rules=rules or {"score": {">=": -0.01}})
        return Campaign(
            name=name,
            objective=Objective(key=key, direction=direction),
            acceptance=criteria,
            budget=budget,
            parallelism=parallelism,
        )

    return _factory
