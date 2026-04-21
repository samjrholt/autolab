"""Canonical SHA-256 hashing for Records and arbitrary payloads.

Records are hashed with the `checksum` field cleared so the digest is
self-consistent — verifying on read recomputes with the same exclusion.
"""

from __future__ import annotations

import hashlib
from typing import Any

import orjson

from autolab.models import Record

_HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset({"checksum"})


def canonical_bytes(data: Any) -> bytes:
    """Deterministic canonical JSON encoding suitable for hashing."""
    return orjson.dumps(
        data,
        option=orjson.OPT_SORT_KEYS | orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY,
    )


def sha256_hex(data: Any) -> str:
    """SHA-256 of arbitrary JSON-serialisable data."""
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def record_payload(record: Record) -> dict[str, Any]:
    """Strip non-hashed fields and return the canonical record dict."""
    payload = record.model_dump(mode="json")
    for field in _HASH_EXCLUDED_FIELDS:
        payload.pop(field, None)
    return payload


def hash_record(record: Record) -> str:
    """SHA-256 of a Record with `checksum` excluded."""
    return sha256_hex(record_payload(record))


def file_sha256(path: str) -> str:
    """SHA-256 of a file's contents — used for tool / skill declaration hashes."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "canonical_bytes",
    "file_sha256",
    "hash_record",
    "record_payload",
    "sha256_hex",
]
