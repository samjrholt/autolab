"""Build a flat pandas DataFrame view of the ledger for chat kernels."""
from __future__ import annotations

from typing import Any

import pandas as pd


def build_ledger_frame(records: list[Any], campaigns: dict[str, Any]) -> pd.DataFrame:
    """Flatten records into one row per record with inputs.* and outputs.* columns.

    `records` is the full ledger list (objects with to_dict()).
    `campaigns` maps campaign_id -> campaign dict (for name and objective lookups).
    """
    rows: list[dict[str, Any]] = []
    for rec in records:
        d = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec)
        campaign_id = d.get("campaign_id")
        campaign = campaigns.get(campaign_id) or {}
        base = {
            "id": d.get("id"),
            "campaign_id": campaign_id,
            "campaign_name": campaign.get("name"),
            "capability": d.get("capability"),
            "module": d.get("module"),
            "status": d.get("status"),
            "started_at": d.get("started_at"),
            "completed_at": d.get("completed_at"),
            "trial": (d.get("metadata") or {}).get("trial"),
            "parent_ids": d.get("parent_ids") or [],
        }
        for k, v in (d.get("inputs") or {}).items():
            base[f"inputs.{k}"] = v
        for k, v in (d.get("outputs") or {}).items():
            base[f"outputs.{k}"] = v
        rows.append(base)
    df = pd.DataFrame(rows)
    for col in ("started_at", "completed_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def describe_columns(df: pd.DataFrame) -> str:
    """Compact schema description for the agent system prompt."""
    if df.empty:
        return "(no records yet)"
    lines = []
    for col in df.columns:
        sample = df[col].dropna()
        dtype = str(df[col].dtype)
        example = sample.iloc[0] if not sample.empty else None
        lines.append(f"- {col}: {dtype}  e.g. {example!r}")
    return "\n".join(lines)
