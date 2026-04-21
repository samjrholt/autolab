"""Smoke tests for the append-only, hashed Ledger."""

from __future__ import annotations

import pytest

from autolab.models import Annotation, Record
from autolab.provenance.hashing import hash_record
from autolab.provenance.store import Ledger, LedgerError


def _new_record(**overrides):
    base = dict(
        lab_id="lab-test",
        session_id="ses-test",
        operation="noop",
        record_status="pending",
    )
    base.update(overrides)
    return Record(**base)


@pytest.mark.asyncio
async def test_append_assigns_checksum_and_recovers(tmp_path):
    ledger = Ledger(tmp_path)
    rec = _new_record()
    stored = await ledger.append(rec)
    assert stored.checksum is not None
    assert stored.checksum == hash_record(stored)
    fetched = ledger.get(stored.id)
    assert fetched is not None
    assert fetched.checksum == stored.checksum


@pytest.mark.asyncio
async def test_finalised_record_cannot_be_reopened(tmp_path):
    ledger = Ledger(tmp_path)
    rec = _new_record()
    await ledger.append(rec)
    rec_running = rec.model_copy(update={"record_status": "running"})
    await ledger.append(rec_running)
    rec_done = rec.model_copy(update={"record_status": "completed", "outputs": {"x": 1}})
    await ledger.append(rec_done)

    again = rec.model_copy(update={"record_status": "running"})
    with pytest.raises(LedgerError):
        await ledger.append(again)


@pytest.mark.asyncio
async def test_history_preserves_every_version(tmp_path):
    ledger = Ledger(tmp_path)
    rec = _new_record()
    await ledger.append(rec)
    await ledger.append(rec.model_copy(update={"record_status": "running"}))
    await ledger.append(rec.model_copy(update={"record_status": "completed", "outputs": {"v": 1}}))
    history = ledger.history(rec.id)
    assert [r.record_status for r in history] == ["pending", "running", "completed"]


@pytest.mark.asyncio
async def test_annotations_extend_without_mutation(tmp_path):
    ledger = Ledger(tmp_path)
    rec = _new_record(record_status="completed")
    await ledger.append(rec)
    ann = Annotation(target_record_id=rec.id, kind="note", body={"note": "hi"})
    await ledger.annotate(ann)

    ann_unknown = Annotation(target_record_id="rec-nope", kind="note", body={})
    with pytest.raises(LedgerError):
        await ledger.annotate(ann_unknown)

    assert len(ledger.annotations(rec.id)) == 1
    assert ledger.verify_all() == []
