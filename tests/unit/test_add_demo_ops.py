"""Unit tests for the add_demo example Operations.

Tests every code path in AddTwo and AddThree:
  - correct arithmetic
  - bad / missing input returns status="failed" (not an exception)
  - chain: add_two output feeds add_three correctly
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure repo root is on path so `examples.*` is importable in the test runner.
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.add_demo.operations import AddThree, AddTwo

# ---------------------------------------------------------------------------
# AddTwo
# ---------------------------------------------------------------------------


class TestAddTwo:
    @pytest.mark.asyncio
    async def test_integer_input(self):
        result = await AddTwo().run({"x": 5})
        assert result.status == "completed"
        assert result.outputs["result"] == 7.0

    @pytest.mark.asyncio
    async def test_float_input(self):
        result = await AddTwo().run({"x": 3.5})
        assert result.status == "completed"
        assert abs(result.outputs["result"] - 5.5) < 1e-9

    @pytest.mark.asyncio
    async def test_zero(self):
        result = await AddTwo().run({"x": 0})
        assert result.status == "completed"
        assert result.outputs["result"] == 2.0

    @pytest.mark.asyncio
    async def test_negative(self):
        result = await AddTwo().run({"x": -10})
        assert result.status == "completed"
        assert result.outputs["result"] == -8.0

    @pytest.mark.asyncio
    async def test_boundary_max(self):
        result = await AddTwo().run({"x": 10.0})
        assert result.status == "completed"
        assert result.outputs["result"] == 12.0

    @pytest.mark.asyncio
    async def test_missing_x_returns_failed(self):
        result = await AddTwo().run({})
        assert result.status == "failed"
        assert "reason" in result.outputs

    @pytest.mark.asyncio
    async def test_bad_type_returns_failed(self):
        result = await AddTwo().run({"x": "not_a_number"})
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_string_number_coerces(self):
        # float("3") works — be permissive
        result = await AddTwo().run({"x": "3"})
        assert result.status == "completed"
        assert result.outputs["result"] == 5.0

    @pytest.mark.asyncio
    async def test_extra_inputs_ignored(self):
        result = await AddTwo().run({"x": 1, "y": 999, "irrelevant": True})
        assert result.status == "completed"
        assert result.outputs["result"] == 3.0


# ---------------------------------------------------------------------------
# AddThree
# ---------------------------------------------------------------------------


class TestAddThree:
    @pytest.mark.asyncio
    async def test_basic(self):
        result = await AddThree().run({"x": 7})
        assert result.status == "completed"
        assert result.outputs["result"] == 10.0

    @pytest.mark.asyncio
    async def test_zero(self):
        result = await AddThree().run({"x": 0})
        assert result.status == "completed"
        assert result.outputs["result"] == 3.0

    @pytest.mark.asyncio
    async def test_missing_x_returns_failed(self):
        result = await AddThree().run({})
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_bad_type_returns_failed(self):
        result = await AddThree().run({"x": None})
        assert result.status == "failed"


# ---------------------------------------------------------------------------
# Chain: add_two → add_three = x + 5
# ---------------------------------------------------------------------------


class TestChain:
    @pytest.mark.asyncio
    async def test_chain_x_equals_five(self):
        r2 = await AddTwo().run({"x": 5})
        assert r2.status == "completed"
        r3 = await AddThree().run({"x": r2.outputs["result"]})
        assert r3.status == "completed"
        assert r3.outputs["result"] == 10.0  # 5 + 2 + 3 = 10

    @pytest.mark.asyncio
    async def test_chain_x_equals_zero(self):
        r2 = await AddTwo().run({"x": 0})
        r3 = await AddThree().run({"x": r2.outputs["result"]})
        assert r3.outputs["result"] == 5.0

    @pytest.mark.asyncio
    async def test_chain_x_equals_ten_optimal(self):
        """x=10 is the optimal input — chain gives 15.0."""
        r2 = await AddTwo().run({"x": 10})
        r3 = await AddThree().run({"x": r2.outputs["result"]})
        assert r3.outputs["result"] == 15.0

    @pytest.mark.parametrize("x", [0, 1, 2.5, 5, 7.7, 10])
    @pytest.mark.asyncio
    async def test_chain_always_equals_x_plus_five(self, x):
        r2 = await AddTwo().run({"x": x})
        r3 = await AddThree().run({"x": r2.outputs["result"]})
        assert abs(r3.outputs["result"] - (x + 5)) < 1e-9
