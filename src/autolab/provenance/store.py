"""Append-only, hashed, write-ahead Record ledger.

Dual-write contract: every Record lands in SQLite (WAL mode) **and** in a
plain `.jsonl` file. If SQLite corrupts, the ledger can be rebuilt from
the log. Records are written ahead of the Operation actually running so a
crash mid-Operation still leaves a `pending` or `running` breadcrumb.

Records are never mutated in place. `append()` writes a new finalised row
that supersedes the earlier write-ahead row for the same `record.id`;
every previous version is preserved in the JSONL history. Corrections and
notes land via Annotations, which are themselves rows in a sibling table.

See docs/design/autolab-ideas-foundation.md §6 for the invariants.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

from autolab.models import Annotation, Record, Session
from autolab.provenance.hashing import canonical_bytes, hash_record

_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT NOT NULL,
    version INTEGER NOT NULL,
    lab_id TEXT NOT NULL,
    campaign_id TEXT,
    experiment_id TEXT,
    session_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    record_status TEXT NOT NULL,
    sample_id TEXT,
    parent_ids_json TEXT NOT NULL,
    checksum TEXT,
    created_at TEXT NOT NULL,
    finalised_at TEXT,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (id, version)
);
"""

_ANNOTATIONS_DDL = """
CREATE TABLE IF NOT EXISTS annotations (
    id TEXT PRIMARY KEY,
    target_record_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""

_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_records_campaign ON records (campaign_id);",
    "CREATE INDEX IF NOT EXISTS idx_records_experiment ON records (experiment_id);",
    "CREATE INDEX IF NOT EXISTS idx_records_session ON records (session_id);",
    "CREATE INDEX IF NOT EXISTS idx_records_operation ON records (operation);",
    "CREATE INDEX IF NOT EXISTS idx_records_sample ON records (sample_id);",
    "CREATE INDEX IF NOT EXISTS idx_annotations_target ON annotations (target_record_id);",
]


class LedgerError(RuntimeError):
    """Raised on invariant violations (mutating a finalised Record, etc.)."""


class Ledger:
    """The Lab's append-only Record store.

    All writes go through `append()` / `annotate()`. Concurrent writers
    are serialised via an asyncio lock so the dual-write (SQLite + JSONL)
    stays consistent. The ledger is safe to call from async and sync code
    paths — read helpers run under `asyncio.to_thread` when needed.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "ledger.sqlite"
        self.jsonl_path = self.root / "ledger.jsonl"
        self._conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.executescript(_RECORDS_DDL + _ANNOTATIONS_DDL + _SESSIONS_DDL)
        for stmt in _INDEXES:
            self._conn.execute(stmt)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def append(self, record: Record) -> Record:
        """Persist a Record version. Returns the stored Record with checksum set."""
        async with self._lock:
            return await asyncio.to_thread(self._append_sync, record)

    def append_sync(self, record: Record) -> Record:
        """Synchronous variant for non-async contexts (e.g. tests, CLI replay)."""
        return self._append_sync(record)

    def _append_sync(self, record: Record) -> Record:
        finalised = record.record_status in {"completed", "failed", "soft_fail"}
        # Freshly compute checksum on every write so each version is verifiable.
        stamped = record.model_copy(
            update={
                "checksum": None,
                "finalised_at": record.finalised_at
                if record.finalised_at is not None
                else (datetime.now(tz=record.created_at.tzinfo) if finalised else None),
            }
        )
        stamped = stamped.model_copy(update={"checksum": hash_record(stamped)})

        version = self._next_version(stamped.id)
        self._enforce_append_only(stamped, version)

        payload = stamped.model_dump(mode="json")
        payload_blob = orjson.dumps(payload).decode()
        self._conn.execute(
            """
            INSERT INTO records (
                id, version, lab_id, campaign_id, experiment_id, session_id,
                operation, record_status, sample_id, parent_ids_json, checksum,
                created_at, finalised_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stamped.id,
                version,
                stamped.lab_id,
                stamped.campaign_id,
                stamped.experiment_id,
                stamped.session_id,
                stamped.operation,
                stamped.record_status,
                stamped.sample_id,
                json.dumps(stamped.parent_ids),
                stamped.checksum,
                stamped.created_at.isoformat(),
                stamped.finalised_at.isoformat() if stamped.finalised_at else None,
                payload_blob,
            ),
        )

        # JSONL append — crash-safe secondary log.
        with self.jsonl_path.open("ab") as fh:
            fh.write(canonical_bytes({"kind": "record", "version": version, **payload}))
            fh.write(b"\n")
        return stamped

    async def annotate(self, annotation: Annotation) -> Annotation:
        async with self._lock:
            return await asyncio.to_thread(self._annotate_sync, annotation)

    def _annotate_sync(self, annotation: Annotation) -> Annotation:
        # Cannot annotate a record that doesn't exist.
        if self._latest_version(annotation.target_record_id) is None:
            raise LedgerError(f"cannot annotate unknown record {annotation.target_record_id!r}")
        payload = annotation.model_dump(mode="json")
        self._conn.execute(
            """
            INSERT INTO annotations (id, target_record_id, kind, author, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                annotation.id,
                annotation.target_record_id,
                annotation.kind,
                annotation.author,
                annotation.created_at.isoformat(),
                orjson.dumps(payload).decode(),
            ),
        )
        with self.jsonl_path.open("ab") as fh:
            fh.write(canonical_bytes({"kind": "annotation", **payload}))
            fh.write(b"\n")
        return annotation

    # ------------------------------------------------------------------
    # Invariant checks
    # ------------------------------------------------------------------

    def _enforce_append_only(self, record: Record, new_version: int) -> None:
        """Lifecycle policy: once a Record is finalised it cannot re-open."""
        if new_version == 1:
            return
        prev = self._latest_row(record.id)
        assert prev is not None
        prev_status: str = prev[0]
        if prev_status in {"completed", "failed", "soft_fail"}:
            raise LedgerError(
                f"record {record.id} is finalised ({prev_status}); "
                "use annotate() to add corrections"
            )

    def _next_version(self, record_id: str) -> int:
        row = self._conn.execute(
            "SELECT MAX(version) FROM records WHERE id = ?", (record_id,)
        ).fetchone()
        return 1 if row is None or row[0] is None else int(row[0]) + 1

    def _latest_row(self, record_id: str) -> tuple[str] | None:
        row = self._conn.execute(
            """
            SELECT record_status FROM records
            WHERE id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (record_id,),
        ).fetchone()
        return row if row is not None else None

    def _latest_version(self, record_id: str) -> int | None:
        row = self._conn.execute(
            "SELECT MAX(version) FROM records WHERE id = ?", (record_id,)
        ).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(self, record_id: str, version: int | None = None) -> Record | None:
        if version is None:
            row = self._conn.execute(
                """
                SELECT payload_json FROM records
                WHERE id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (record_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT payload_json FROM records WHERE id = ? AND version = ?",
                (record_id, version),
            ).fetchone()
        if row is None:
            return None
        return Record.model_validate_json(row[0])

    def history(self, record_id: str) -> list[Record]:
        rows = self._conn.execute(
            "SELECT payload_json FROM records WHERE id = ? ORDER BY version ASC",
            (record_id,),
        ).fetchall()
        return [Record.model_validate_json(r[0]) for r in rows]

    def iter_records(
        self,
        *,
        campaign_id: str | None = None,
        experiment_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        latest_only: bool = True,
    ) -> Iterable[Record]:
        clauses: list[str] = []
        params: list[Any] = []
        if campaign_id is not None:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        if experiment_id is not None:
            clauses.append("experiment_id = ?")
            params.append(experiment_id)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            clauses.append("record_status = ?")
            params.append(status)
        if latest_only:
            clauses.append(
                "version = (SELECT MAX(version) FROM records r2 WHERE r2.id = records.id)"
            )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "ORDER BY created_at ASC" if latest_only else "ORDER BY created_at ASC, version ASC"
        sql = f"SELECT payload_json FROM records {where} {order}"
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        for (payload_json,) in rows:
            yield Record.model_validate_json(payload_json)

    def annotations(self, target_record_id: str) -> list[Annotation]:
        rows = self._conn.execute(
            "SELECT payload_json FROM annotations WHERE target_record_id = ? ORDER BY created_at ASC",
            (target_record_id,),
        ).fetchall()
        return [Annotation.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------------------
    # Sessions (environment snapshots live on Session)
    # ------------------------------------------------------------------

    async def register_session(self, session: Session) -> Session:
        """Persist a :class:`Session` (with its :class:`EnvironmentSnapshot`).

        Idempotent — registering the same session twice is a no-op.
        """
        async with self._lock:
            return await asyncio.to_thread(self._register_session_sync, session)

    def _register_session_sync(self, session: Session) -> Session:
        existing = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session.id,)
        ).fetchone()
        if existing is not None:
            return session
        payload = session.model_dump(mode="json")
        blob = orjson.dumps(payload).decode()
        self._conn.execute(
            "INSERT INTO sessions (id, started_at, payload_json) VALUES (?, ?, ?)",
            (session.id, session.started_at.isoformat(), blob),
        )
        with self.jsonl_path.open("ab") as fh:
            fh.write(canonical_bytes({"kind": "session", **payload}))
            fh.write(b"\n")
        return session

    def get_session(self, session_id: str) -> Session | None:
        row = self._conn.execute(
            "SELECT payload_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return Session.model_validate_json(row[0])

    def sessions(self) -> list[Session]:
        rows = self._conn.execute(
            "SELECT payload_json FROM sessions ORDER BY started_at ASC"
        ).fetchall()
        return [Session.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------------------
    # Sample lineage
    # ------------------------------------------------------------------

    def sample_history(self, sample_id: str) -> list[Record]:
        """Every Record that touched ``sample_id`` (as sample or parent).

        Returned chronologically by ``created_at``. Includes every version
        of each Record — useful for auditing sample state transitions.
        """
        rows = self._conn.execute(
            """
            SELECT payload_json FROM records
            WHERE sample_id = ?
            ORDER BY created_at ASC, version ASC
            """,
            (sample_id,),
        ).fetchall()
        primary = [Record.model_validate_json(r[0]) for r in rows]

        # Also pull Records that name sample_id as a parent_sample.
        other_rows = self._conn.execute(
            "SELECT payload_json FROM records ORDER BY created_at ASC, version ASC"
        ).fetchall()
        mentions: list[Record] = []
        for (pj,) in other_rows:
            rec = Record.model_validate_json(pj)
            if rec.sample_id == sample_id:
                continue  # already in primary
            if sample_id in rec.parent_sample_ids:
                mentions.append(rec)

        merged = primary + mentions
        merged.sort(key=lambda r: (r.created_at, r.id))
        return merged

    def sample_lineage(self, sample_id: str) -> list[str]:
        """Return the ancestor chain of ``sample_id`` (closest → oldest).

        Walks ``parent_sample_ids`` on the *latest* Record that minted
        each sample. Cycles are broken defensively.
        """
        order: list[str] = [sample_id]
        seen: set[str] = {sample_id}
        queue: list[str] = [sample_id]
        while queue:
            current = queue.pop(0)
            # Find the first Record whose new sample_id is `current`.
            row = self._conn.execute(
                """
                SELECT payload_json FROM records
                WHERE sample_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (current,),
            ).fetchone()
            if row is None:
                continue
            rec = Record.model_validate_json(row[0])
            for parent in rec.parent_sample_ids:
                if parent in seen:
                    continue
                seen.add(parent)
                order.append(parent)
                queue.append(parent)
        return order

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify(self, record_id: str) -> bool:
        """Recompute the checksum of the latest stored version."""
        record = self.get(record_id)
        if record is None or record.checksum is None:
            return False
        return record.checksum == hash_record(record)

    def verify_all(self) -> list[str]:
        """Return a list of record ids whose checksum does not validate."""
        bad: list[str] = []
        ids = [r[0] for r in self._conn.execute("SELECT DISTINCT id FROM records").fetchall()]
        for rid in ids:
            if not self.verify(rid):
                bad.append(rid)
        return bad

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()


__all__ = ["Ledger", "LedgerError"]
