"""Tests for RO-Crate / PROV export, annotation_extract Operation, CLI."""

from __future__ import annotations

import asyncio

from autolab.export import to_prov, to_ro_crate
from autolab.models import Annotation, Record
from autolab.operations.base import OperationContext
from autolab.operations.interpretation import AnnotationExtract


def test_ro_crate_shape(make_lab):
    with make_lab() as lab:
        session = lab.new_session()
        rec = Record(
            lab_id=lab.lab_id,
            session_id=session.id,
            operation="stub",
            record_status="completed",
            outputs={"score": 0.9},
            inputs={"x": 0.5},
        )
        asyncio.run(lab.ledger.append(rec))
        crate = to_ro_crate(lab)
        graph = crate["@graph"]
        type_names: set[str] = set()
        for e in graph:
            t = e.get("@type")
            if isinstance(t, list):
                type_names.update(t)
            elif isinstance(t, str):
                type_names.add(t)
        assert "Dataset" in type_names
        assert any(isinstance(e.get("@type"), list) and "CreateAction" in e["@type"] for e in graph)
        # The Record must carry its checksum as an identifier.
        rec_entity = next(e for e in graph if e.get("@id") == f"#{rec.id}")
        assert rec_entity["identifier"]  # checksum present


def test_prov_shape(make_lab):
    with make_lab() as lab:
        session = lab.new_session()
        parent = Record(
            lab_id=lab.lab_id, session_id=session.id, operation="a", record_status="completed"
        )
        asyncio.run(lab.ledger.append(parent))
        child = Record(
            lab_id=lab.lab_id,
            session_id=session.id,
            operation="b",
            record_status="completed",
            parent_ids=[parent.id],
        )
        asyncio.run(lab.ledger.append(child))
        doc = to_prov(lab)
        ids = {e["id"] for e in doc["entity"]}
        assert f"rec:{parent.id}" in ids and f"rec:{child.id}" in ids
        assert any(
            d["generatedEntity"] == f"rec:{child.id}" and d["usedEntity"] == f"rec:{parent.id}"
            for d in doc["wasDerivedFrom"]
        )


def test_annotation_extract_offline(make_lab):
    """The Interpretation Op runs in offline Claude mode and returns a valid Record."""
    from autolab.agents.claude import ClaudeTransport

    with make_lab() as lab:
        session = lab.new_session()
        target = Record(
            lab_id=lab.lab_id,
            session_id=session.id,
            operation="sinter",
            record_status="completed",
            outputs={"grain_size_nm": 12.3},
        )
        asyncio.run(lab.ledger.append(target))
        asyncio.run(
            lab.ledger.annotate(
                Annotation(
                    target_record_id=target.id,
                    kind="note",
                    body={"note": "tube-furnace-A ran 20 K hot today; visible second phase"},
                    author="sam",
                )
            )
        )

        ctx = OperationContext(
            record_id="ctx",
            operation="annotation_extract",
            metadata={"lab": lab, "claude": ClaudeTransport(offline=True)},
        )
        result = asyncio.run(
            AnnotationExtract().run(
                {"target_record_id": target.id},
                ctx,
            )
        )
        assert result.status == "completed"
        assert result.outputs["source_annotation_count"] == 1
        # Offline transport is permissive — tags/extracted may be empty; confidence is a float.
        assert "confidence" in result.outputs
        assert isinstance(result.outputs["confidence"], float)


def test_annotation_extract_no_notes_is_empty(make_lab):
    from autolab.agents.claude import ClaudeTransport

    with make_lab() as lab:
        session = lab.new_session()
        target = Record(
            lab_id=lab.lab_id,
            session_id=session.id,
            operation="op",
            record_status="completed",
        )
        asyncio.run(lab.ledger.append(target))
        ctx = OperationContext(
            record_id="ctx",
            operation="annotation_extract",
            metadata={"lab": lab, "claude": ClaudeTransport(offline=True)},
        )
        result = asyncio.run(
            AnnotationExtract().run(
                {"target_record_id": target.id},
                ctx,
            )
        )
        assert result.status == "completed"
        assert result.outputs["source_annotation_count"] == 0


def test_cli_verify(make_lab):
    """The CLI verify path rehydrates a persisted ledger and validates checksums."""
    from typer.testing import CliRunner

    from autolab.cli import app as cli_app

    runner = CliRunner()
    with make_lab() as lab:
        session = lab.new_session()
        for i in range(3):
            rec = Record(
                lab_id=lab.lab_id,
                session_id=session.id,
                operation="x",
                record_status="completed",
                outputs={"v": i},
            )
            asyncio.run(lab.ledger.append(rec))
        root = lab.root
    # Reopen via CLI (the context manager above already closed the ledger).
    result = runner.invoke(cli_app, ["verify", "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
