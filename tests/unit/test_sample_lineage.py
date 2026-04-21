"""Unit tests for the Ledger's sample lineage queries + session persistence."""

from __future__ import annotations

import pytest

from autolab.models import EnvironmentSnapshot, Record, Session
from autolab.provenance.store import Ledger


def _rec(**overrides):
    base = dict(
        lab_id="lab-test",
        session_id="ses-test",
        operation="stub",
        record_status="completed",
    )
    base.update(overrides)
    return Record(**base)


class TestSessions:
    @pytest.mark.asyncio
    async def test_register_session_round_trips(self, tmp_path):
        ledger = Ledger(tmp_path)
        session = Session(environment=EnvironmentSnapshot(seeds={"numpy": 7}))
        await ledger.register_session(session)
        fetched = ledger.get_session(session.id)
        assert fetched is not None
        assert fetched.id == session.id
        assert fetched.environment.seeds == {"numpy": 7}

    @pytest.mark.asyncio
    async def test_register_session_is_idempotent(self, tmp_path):
        ledger = Ledger(tmp_path)
        session = Session()
        await ledger.register_session(session)
        await ledger.register_session(session)  # second call is a no-op
        assert len(ledger.sessions()) == 1


class TestSampleLineage:
    @pytest.mark.asyncio
    async def test_sample_history_includes_record_that_minted_sample(self, tmp_path):
        ledger = Ledger(tmp_path)
        minted = _rec(sample_id="sam-1")
        await ledger.append(minted)
        history = ledger.sample_history("sam-1")
        assert [r.id for r in history] == [minted.id]

    @pytest.mark.asyncio
    async def test_sample_history_picks_up_downstream_references(self, tmp_path):
        ledger = Ledger(tmp_path)
        parent = _rec(sample_id="sam-parent")
        await ledger.append(parent)

        measure = _rec(
            sample_id=None,
            parent_sample_ids=["sam-parent"],
            operation="measurement",
        )
        await ledger.append(measure)

        history = ledger.sample_history("sam-parent")
        ids = {r.id for r in history}
        assert parent.id in ids
        assert measure.id in ids

    @pytest.mark.asyncio
    async def test_sample_lineage_walks_ancestor_chain(self, tmp_path):
        ledger = Ledger(tmp_path)
        # grand: mints sam-A → parent of sam-B → parent of sam-C
        await ledger.append(_rec(sample_id="sam-A"))
        await ledger.append(_rec(sample_id="sam-B", parent_sample_ids=["sam-A"]))
        await ledger.append(_rec(sample_id="sam-C", parent_sample_ids=["sam-B"]))

        lineage = ledger.sample_lineage("sam-C")
        assert lineage == ["sam-C", "sam-B", "sam-A"]

    @pytest.mark.asyncio
    async def test_sample_lineage_breaks_cycles_defensively(self, tmp_path):
        ledger = Ledger(tmp_path)
        # Pathological but should not loop.
        await ledger.append(_rec(sample_id="sam-X", parent_sample_ids=["sam-X"]))
        lineage = ledger.sample_lineage("sam-X")
        assert lineage == ["sam-X"]
