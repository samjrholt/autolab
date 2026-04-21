"""Tests for ResourceState, available_after, and asset metadata."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autolab import Resource, ResourceState
from autolab.resources.manager import ResourceManager, ResourceUnavailableError


def _manager(*resources: Resource) -> ResourceManager:
    m = ResourceManager()
    for r in resources:
        m.register(r)
    return m


class TestResourceRegistration:
    def test_asset_id_and_typical_durations_stored(self):
        r = Resource(
            name="furnace-1",
            kind="tube_furnace",
            capabilities={"max_temp_k": 1400},
            asset_id="TF-2024-001",
            typical_operation_durations={"sinter": 7200, "anneal": 3600},
        )
        m = _manager(r)
        row = m.status()[0]
        assert row["asset_id"] == "TF-2024-001"
        assert row["typical_operation_durations"]["sinter"] == 7200

    def test_initial_state_is_idle(self):
        m = _manager(Resource(name="x", kind="computer"))
        assert m.get_state("x") == ResourceState.IDLE


class TestSetState:
    def test_transition_to_error(self):
        m = _manager(Resource(name="x", kind="computer"))
        m.set_state("x", ResourceState.ERROR)
        assert m.get_state("x") == ResourceState.ERROR

    def test_available_after_included_in_status(self):
        m = _manager(Resource(name="x", kind="computer"))
        eta = datetime.now(UTC) + timedelta(hours=2)
        m.set_state("x", ResourceState.COOLING, available_after=eta)
        row = m.status()[0]
        assert row["state"] == "cooling"
        assert row["wait_seconds"] > 0

    def test_cooling_auto_clears_past_eta(self):
        m = _manager(Resource(name="x", kind="computer"))
        past = datetime.now(UTC) - timedelta(seconds=1)
        m.set_state("x", ResourceState.COOLING, available_after=past)
        # _is_available should auto-clear.
        assert m._is_available("x")
        assert m.get_state("x") == ResourceState.IDLE

    def test_unknown_resource_raises_keyerror(self):
        m = ResourceManager()
        with pytest.raises(KeyError):
            m.set_state("nope", ResourceState.ERROR)


class TestAcquireWithState:
    @pytest.mark.asyncio
    async def test_acquire_idle_resource(self):
        m = _manager(Resource(name="pc", kind="computer"))
        async with m.acquire("computer") as r:
            assert r.name == "pc"
            assert m.get_state("pc") == ResourceState.BUSY
        assert m.get_state("pc") == ResourceState.IDLE

    @pytest.mark.asyncio
    async def test_acquire_skips_error_resource(self):
        m = _manager(
            Resource(name="bad", kind="computer"),
            Resource(name="good", kind="computer"),
        )
        m.set_state("bad", ResourceState.ERROR)
        async with m.acquire("computer") as r:
            assert r.name == "good"

    @pytest.mark.asyncio
    async def test_no_compatible_resource_raises_immediately(self):
        m = _manager(Resource(name="pc", kind="computer"))
        with pytest.raises(ResourceUnavailableError):
            async with m.acquire("arc_furnace"):
                pass

    @pytest.mark.asyncio
    async def test_acquire_respects_cooling_window(self):
        m = _manager(
            Resource(name="furnace", kind="tube_furnace"),
            Resource(name="backup", kind="tube_furnace"),
        )
        future = datetime.now(UTC) + timedelta(hours=1)
        m.set_state("furnace", ResourceState.COOLING, available_after=future)
        # Should acquire backup, not wait for furnace.
        async with m.acquire("tube_furnace") as r:
            assert r.name == "backup"

    @pytest.mark.asyncio
    async def test_set_cooling_inside_context_not_reset_to_idle(self):
        m = _manager(Resource(name="furnace", kind="tube_furnace"))
        eta = datetime.now(UTC) + timedelta(hours=2)
        async with m.acquire("tube_furnace") as r:
            # Simulate: after a high-temp sinter, set cooling window.
            m.set_state(r.name, ResourceState.COOLING, available_after=eta)
        # Should NOT reset to IDLE because state was changed inside the context.
        assert m.get_state("furnace") == ResourceState.COOLING
