"""Ledger export formats.

Two views of the same ledger data, for interoperability with existing
scientific-data ecosystems — the action items called out in
[docs/design/2026-04-22-competitive-landscape.md](../../docs/design/2026-04-22-competitive-landscape.md).

- :func:`to_ro_crate` — RO-Crate 1.1 JSON-LD. Drops into every
  ELN that speaks the ELN Consortium ``.eln`` format (Chemotion,
  eLabFTW, RSpace, Kadi4Mat).
- :func:`to_prov` — W3C PROV-O shaped JSON. ``Entity`` for every
  Record, ``Activity`` for every Operation run, ``Agent`` for the
  Planner / PolicyProvider / Campaign Designer.

Both functions read the ledger; neither mutates it.  The ledger remains
the ground truth — exports are projections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autolab.lab import Lab


# ---------------------------------------------------------------------------
# RO-Crate 1.1 — http://www.researchobject.org/ro-crate/1.1/
# ---------------------------------------------------------------------------


def to_ro_crate(lab: Lab, *, campaign_id: str | None = None) -> dict[str, Any]:
    """Return an RO-Crate JSON-LD metadata document for the ledger slice.

    If ``campaign_id`` is given, only that campaign's records are
    included. Otherwise every record in the ledger is exported.

    The root ``Dataset`` carries the lab id and record count. Each
    Record becomes a ``CreateAction`` with its inputs/outputs encoded
    as ``object`` / ``result`` entities. Annotations are attached as
    ``comment`` properties.
    """
    records = list(
        lab.ledger.iter_records(campaign_id=campaign_id)
        if campaign_id
        else lab.ledger.iter_records()
    )
    entities: list[dict[str, Any]] = [
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@type": "CreativeWork",
            "@id": "ro-crate-metadata.json",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": f"autolab ledger export — {lab.lab_id}",
            "description": "append-only, hashed provenance ledger",
            "hasPart": [{"@id": f"#{r.id}"} for r in records],
            "autolab:lab_id": lab.lab_id,
            "autolab:record_count": len(records),
            "autolab:campaign_id": campaign_id,
        },
    ]
    for rec in records:
        entity: dict[str, Any] = {
            "@id": f"#{rec.id}",
            "@type": ["CreateAction", "autolab:Record"],
            "name": rec.operation,
            "actionStatus": _action_status(rec.record_status),
            "startTime": rec.created_at.isoformat(),
            "endTime": rec.finalised_at.isoformat() if rec.finalised_at else None,
            "agent": [{"@id": f"#session:{rec.session_id}"}],
            "instrument": {"@id": f"#tool:{rec.operation}"},
            "object": {
                "@id": f"#inputs:{rec.id}",
                "@type": "PropertyValue",
                "value": rec.inputs,
            },
            "result": {
                "@id": f"#outputs:{rec.id}",
                "@type": "PropertyValue",
                "value": rec.outputs,
            },
            "identifier": rec.checksum,
            "autolab:record_status": rec.record_status,
            "autolab:tool_declaration_hash": rec.tool_declaration_hash,
            "autolab:module": rec.module,
            "autolab:resource_name": rec.resource_name,
            "autolab:failure_mode": rec.failure_mode,
            "autolab:outcome_class": rec.outcome_class,
            "autolab:gate_result": rec.gate_result,
        }
        anns = lab.ledger.annotations(rec.id)
        if anns:
            entity["comment"] = [
                {
                    "@id": f"#annotation:{a.id}",
                    "@type": "Comment",
                    "text": str(a.body),
                    "author": a.author,
                    "dateCreated": a.created_at.isoformat(),
                    "autolab:kind": a.kind,
                }
                for a in anns
            ]
        entities.append(entity)

    return {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {"autolab": "https://autolab.sh/schema#"},
        ],
        "@graph": entities,
    }


def _action_status(record_status: str) -> str:
    return {
        "completed": "CompletedActionStatus",
        "failed": "FailedActionStatus",
        "soft_fail": "FailedActionStatus",
        "running": "ActiveActionStatus",
        "pending": "PotentialActionStatus",
        "paused": "PotentialActionStatus",
    }.get(record_status, "PotentialActionStatus")


# ---------------------------------------------------------------------------
# W3C PROV-O — https://www.w3.org/TR/prov-o/
# ---------------------------------------------------------------------------


def to_prov(lab: Lab, *, campaign_id: str | None = None) -> dict[str, Any]:
    """Return a PROV-O shaped JSON document for the ledger slice.

    ``entities`` — one per Record id (typed as ``autolab:Record``).
    ``activities`` — one per Operation run (typed as ``autolab:Operation``).
    ``agents`` — one per Session, plus one pseudo-agent per distinct
    Claude role (PolicyProvider / Planner / Designer).
    ``wasDerivedFrom`` — edges from a Record to each ``parent_ids``.
    """
    records = list(
        lab.ledger.iter_records(campaign_id=campaign_id)
        if campaign_id
        else lab.ledger.iter_records()
    )
    entities: list[dict[str, Any]] = []
    activities: list[dict[str, Any]] = []
    agents_seen: set[str] = set()
    agents: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []
    associated: list[dict[str, Any]] = []
    used: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []

    for rec in records:
        entities.append(
            {
                "id": f"rec:{rec.id}",
                "type": ["prov:Entity", "autolab:Record"],
                "checksum": rec.checksum,
                "label": rec.operation,
                "record_status": rec.record_status,
            }
        )
        activity_id = f"op:{rec.id}"
        activities.append(
            {
                "id": activity_id,
                "type": ["prov:Activity", "autolab:Operation"],
                "label": rec.operation,
                "module": rec.module,
                "startedAt": rec.created_at.isoformat(),
                "endedAt": rec.finalised_at.isoformat() if rec.finalised_at else None,
                "toolDeclarationHash": rec.tool_declaration_hash,
            }
        )
        generated.append({"entity": f"rec:{rec.id}", "activity": activity_id})

        session_agent = f"agent:session:{rec.session_id}"
        if session_agent not in agents_seen:
            agents.append({"id": session_agent, "type": ["prov:Agent", "autolab:Session"]})
            agents_seen.add(session_agent)
        associated.append({"activity": activity_id, "agent": session_agent})

        for parent in rec.parent_ids or []:
            derived.append({"generatedEntity": f"rec:{rec.id}", "usedEntity": f"rec:{parent}"})
            used.append({"activity": activity_id, "entity": f"rec:{parent}"})

        for parent_sid in rec.parent_sample_ids or []:
            used.append({"activity": activity_id, "entity": f"sample:{parent_sid}"})

    return {
        "@context": {
            "prov": "http://www.w3.org/ns/prov#",
            "autolab": "https://autolab.sh/schema#",
        },
        "entity": entities,
        "activity": activities,
        "agent": agents,
        "wasGeneratedBy": generated,
        "wasDerivedFrom": derived,
        "wasAssociatedWith": associated,
        "used": used,
    }


__all__ = ["to_prov", "to_ro_crate"]
