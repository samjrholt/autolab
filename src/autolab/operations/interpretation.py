"""Interpretation Operations — LLM-backed Operations that read evidence
and return structured Claims.

The landscape analysis in
[docs/design/2026-04-22-competitive-landscape.md](../../../docs/design/2026-04-22-competitive-landscape.md)
calls out **"post-hoc LLM structuring"** as a differentiator when it
ships in-loop. This module is that in-loop shipment.

:class:`AnnotationExtract`
    Reads a target Record's free-text ``note`` annotations, asks Claude
    to extract tagged structured facts (dates, conditions, named
    entities, measurements), and returns an ``OperationResult`` whose
    outputs are the extracted fields plus a confidence score.  The
    Orchestrator's provenance contract records the call as its own
    Record, so the extraction itself is hashed and replayable.

Offline mode: if ``ANTHROPIC_API_KEY`` is unset, the Operation still
runs — the offline Claude transport returns a minimal stub payload so
the ledger entry exists without real LLM inference.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from autolab.models import OperationResult
from autolab.operations.base import Operation, OperationContext


_SYSTEM = """You are an Interpretation Operation inside an autonomous science lab.
A scientist attached free-text annotations to a lab Record. Extract structured facts.

Reply with a single compact JSON object:

  {
    "tags": ["short", "lowercase", "tag", "list"],
    "extracted": { "<field>": <typed value>, ... },
    "confidence": 0.0-1.0,
    "rationale": "short sentence"
  }

Rules:
- Tags are short lowercase identifiers (e.g. "temperature_drift", "off_target_phase").
- "extracted" contains structured facts: dates ISO-8601, numbers with unit keys
  (e.g. "temp_k": 1320), observed names/labels.
- Never emit prose outside the JSON.
"""


class AnnotationExtract(Operation):
    """Read free-text Annotations on a Record and extract structured Claims."""

    capability = "annotation_extract"
    resource_kind = None  # runs in-process; needs no resource
    produces_sample = False
    destructive = False
    module = "annotation_extract.v0"
    typical_duration = 4

    class Inputs(BaseModel):
        target_record_id: str = Field(..., description="Record whose annotations to read")
        extra_hints: str | None = Field(default=None, description="Optional extra guidance for the LLM")

    class Outputs(BaseModel):
        tags: list[str] = Field(default_factory=list)
        extracted: dict[str, Any] = Field(default_factory=dict)
        confidence: float = 0.0
        rationale: str = ""
        source_annotation_count: int = 0
        model: str = ""

    async def run(self, inputs: dict[str, Any], ctx: OperationContext) -> OperationResult:
        # Lazy imports to keep the core operations module free of LLM deps.
        from autolab.agents.claude import ClaudeTransport, _safe_json

        parsed = self.Inputs(**inputs)
        lab = (ctx.metadata or {}).get("lab")
        if lab is None:
            return OperationResult(
                status="failed",
                failure_mode="process_deviation",
                error="annotation_extract requires ctx.metadata['lab']",
            )

        annotations = lab.ledger.annotations(parsed.target_record_id)
        notes: list[str] = []
        for a in annotations:
            if a.kind not in ("note", "correction"):
                continue
            body = a.body or {}
            text = body.get("note") if isinstance(body, dict) else None
            if text:
                notes.append(f"[{a.author} · {a.created_at.isoformat()}] {text}")
        if not notes:
            return OperationResult(
                status="completed",
                outputs={
                    "tags": [],
                    "extracted": {},
                    "confidence": 0.0,
                    "rationale": "no free-text annotations to extract from",
                    "source_annotation_count": 0,
                    "model": "n/a",
                },
            )

        target = lab.ledger.get(parsed.target_record_id)
        header = f"Target Record: {target.operation if target else 'unknown'}"
        if target and target.outputs:
            header += f"\nOutputs (abridged): {json.dumps(target.outputs)[:400]}"
        hint = parsed.extra_hints or ""
        user = header + "\n\nAnnotations:\n" + "\n".join(notes) + (f"\n\nHint: {hint}" if hint else "")

        transport: ClaudeTransport = (ctx.metadata or {}).get("claude") or ClaudeTransport()
        resp = transport.call(_SYSTEM, user)
        data = _safe_json(resp.text) or {}
        out = {
            "tags": list(data.get("tags") or []),
            "extracted": dict(data.get("extracted") or {}),
            "confidence": float(data.get("confidence") or 0.0),
            "rationale": str(data.get("rationale") or ""),
            "source_annotation_count": len(notes),
            "model": resp.model,
        }
        return OperationResult(status="completed", outputs=out)


__all__ = ["AnnotationExtract"]
