"""Claude Opus 4.7 — PolicyProvider, Planner, and Campaign Designer.

Three integrations, all optional, all offline-testable:

- :class:`ClaudePolicyProvider` — reads a :class:`DecisionContext` and
  returns an :class:`Action` drawn from the Campaign's
  ``allowed_actions``.  Used inside any Planner's ``react()`` step.
- :class:`ClaudePlanner` — proposes a small batch of
  :class:`ProposedStep` JSONs given the objective, history, and tool
  catalogue.
- :class:`CampaignDesigner` — takes free text + available tools and
  resources and returns a *draft* :class:`Campaign` plus a draft
  :class:`WorkflowTemplate`, for human approval.

Every Claude call is persisted.  The policy provider writes a ``claim``
:class:`Annotation` on the Record that prompted it, carrying the hashed
prompt, the model id, and the structured response.  The planner and
designer write ``claim`` Records of their own when a Lab handle is
supplied.  "Every LLM call is a Record" — the differentiator from the
competitive-landscape doc — is enforced here.

Offline mode
------------

If ``ANTHROPIC_API_KEY`` is unset, or ``offline=True`` is passed
explicitly, each agent uses a deterministic scripted response.  This
keeps the test suite self-contained and lets the server boot without
credentials while surfacing a clear 503 on any endpoint that asks for a
real Claude call.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from autolab.models import (
    AcceptanceCriteria,
    Action,
    ActionType,
    Annotation,
    Objective,
    ProposedStep,
    WorkflowStep,
    WorkflowTemplate,
)
from autolab.planners.base import DecisionContext, PlanContext, Planner, PolicyProvider

if TYPE_CHECKING:
    from autolab.lab import Lab

CLAUDE_MODEL_DEFAULT = "claude-opus-4-7"

# Global set of in-flight claim-persistence tasks so the server lifespan can
# drain them before closing the Ledger (otherwise a SQLite worker thread can
# race with ``Lab.close()`` on Windows and crash the process).
_PENDING_CLAIM_TASKS: set[Any] = set()


async def drain_pending_claims(timeout: float = 5.0) -> None:
    """Await any in-flight claim persistence tasks.

    Called from the FastAPI lifespan on shutdown.
    """
    if not _PENDING_CLAIM_TASKS:
        return
    import asyncio

    pending = list(_PENDING_CLAIM_TASKS)
    try:
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True),
            timeout=timeout,
        )
    except (asyncio.TimeoutError, Exception):
        pass


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


@dataclass
class ClaudeResponse:
    """Minimal wrapper around a Claude completion."""

    text: str
    model: str
    prompt_hash: str
    offline: bool


def _hash_prompt(system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


class ClaudeTransport:
    """Thin wrapper over the Anthropic SDK with an offline fallback."""

    def __init__(
        self,
        *,
        model: str = CLAUDE_MODEL_DEFAULT,
        api_key: str | None = None,
        offline: bool | None = None,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if offline is None:
            self.offline = key is None
        else:
            self.offline = offline
        self._api_key = key
        self._client: Any | None = None

    def call(self, system: str, user: str) -> ClaudeResponse:
        if self.offline:
            return ClaudeResponse(
                text=_offline_response(system, user),
                model=f"{self.model}/offline",
                prompt_hash=_hash_prompt(system, user),
                offline=True,
            )
        if self._client is None:
            import anthropic  # local import — optional dep at runtime

            self._client = anthropic.Anthropic(api_key=self._api_key)
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = [
            b.text for b in resp.content if getattr(b, "type", "text") == "text"
        ]
        return ClaudeResponse(
            text="".join(text_parts),
            model=self.model,
            prompt_hash=_hash_prompt(system, user),
            offline=False,
        )


def _offline_response(system: str, user: str) -> str:
    """Scripted response for offline tests.

    Inspects a few keywords in the prompt to return structured JSON that
    the calling agent knows how to parse.  Good enough to boot the
    server and exercise integration tests without real credentials.
    """
    lowered = (system + "\n" + user).lower()
    if "decide which action" in lowered or "policy_provider" in lowered:
        # Conservative offline policy: accept on pass, continue otherwise.
        return json.dumps(
            {
                "action": "continue",
                "reason": "[offline fallback] default: continue exploring",
            }
        )
    if "propose next batch" in lowered or "planner" in lowered:
        return json.dumps(
            {
                "proposals": [],
                "reason": "[offline fallback] no proposals produced",
            }
        )
    if (
        "campaign designer" in lowered
        or "design a campaign" in lowered
        or "campaign_designer" in lowered
        or "draft campaign" in lowered
        or "user goal" in lowered
    ):
        return json.dumps(
            {
                "campaign": {
                    "name": "offline-campaign",
                    "description": "[offline fallback] scripted campaign",
                    "objective": {"key": "score", "direction": "maximise"},
                    "acceptance": {"rules": {"score": {">=": 0.9}}},
                    "budget": 16,
                    "parallelism": 1,
                },
                "workflow": None,
                "notes": "Anthropic API key not configured; returning a stub.",
            }
        )
    return "{}"


# ---------------------------------------------------------------------------
# PolicyProvider
# ---------------------------------------------------------------------------


_POLICY_SYSTEM = """You are the PolicyProvider for an autonomous science lab
called autolab. A Planner has just finished one experimental Operation and is
asking you to decide what to do next. You MUST reply with a single compact JSON
object of the shape:

  {"action": <one of allowed_actions>, "reason": "<short human-readable reason>", "payload": {}}

Rules:
- action MUST be one of the allowed_actions supplied.
- reason is a short sentence, ASCII only.
- payload is an object; leave it {} unless you know the Planner expects specific keys.
- Do not emit any text outside the JSON.
- Prefer `accept` when the acceptance gate has passed.
- Prefer `retry_step` for equipment_failure or measurement_rejection if retries remain.
- Prefer `escalate` for process_deviation.
- Prefer `continue` for off_target synthesis deviations (discoveries to explore).
"""


class ClaudePolicyProvider(PolicyProvider):
    """LLM-backed PolicyProvider that reads a :class:`DecisionContext`."""

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
        fallback: PolicyProvider | None = None,
    ) -> None:
        from autolab.planners.base import HeuristicPolicyProvider

        self._lab = lab
        self._transport = transport or ClaudeTransport()
        self._fallback = fallback or HeuristicPolicyProvider()

    def decide(self, context: DecisionContext) -> Action:
        user = _describe_decision_context(context)
        resp = self._transport.call(_POLICY_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, context.record.id, "policy_provider", user, resp)

        data = _safe_json(resp.text)
        if not data:
            return self._fallback.decide(context)

        action_name = str(data.get("action", "")).strip().lower()
        try:
            action_type = ActionType(action_name)
        except ValueError:
            return self._fallback.decide(context)
        if action_type not in context.allowed_actions:
            return self._fallback.decide(context)
        return Action(
            type=action_type,
            reason=str(data.get("reason") or "claude policy")[:500],
            payload=dict(data.get("payload") or {}),
        )


def _describe_decision_context(ctx: DecisionContext) -> str:
    rec = ctx.record
    lines = [
        f"Operation: {rec.operation}",
        f"record_status: {rec.record_status}",
        f"failure_mode: {rec.failure_mode}",
        f"outcome_class: {rec.outcome_class}",
        f"gate.result: {ctx.gate.result}",
        f"gate.reason: {ctx.gate.reason}",
        f"allowed_actions: {[a.value for a in ctx.allowed_actions]}",
        f"remaining_budget: {ctx.remaining_budget}",
        f"inputs: {json.dumps(rec.inputs, default=str)[:400]}",
        f"outputs: {json.dumps(rec.outputs, default=str)[:400]}",
    ]
    # Short history tail.
    tail = list(ctx.history)[-6:]
    lines.append("recent_history:")
    for r in tail:
        lines.append(
            f"  - {r.operation} status={r.record_status} "
            f"fmode={r.failure_mode} outcome={r.outcome_class}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


_PLANNER_SYSTEM = """You are the Planner for an autonomous science lab called autolab.
Propose the next batch of Operations to run given the objective, available tools,
available resources, and recent history. Reply with a single compact JSON object:

  {"proposals": [
     {"operation": "<tool name>", "inputs": {...}, "decision": {...}}
  ], "reason": "<short summary>"}

Rules:
- Only use tool names that appear in the `tools` list.
- inputs MUST respect each tool's input schema.
- Prefer small batches (1-4 proposals) unless resources clearly support more.
- Never emit prose outside the JSON.
"""


class ClaudePlanner(Planner):
    """Planner whose batch proposals come from Claude.

    ``react()`` still uses its :class:`PolicyProvider`; wire a
    :class:`ClaudePolicyProvider` in to have both legs driven by Claude.
    """

    name = "claude"

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
        policy: PolicyProvider | None = None,
        fallback: Planner | None = None,
    ) -> None:
        super().__init__(policy=policy or ClaudePolicyProvider(lab=lab, transport=transport))
        self._lab = lab
        self._transport = transport or ClaudeTransport()
        self._fallback = fallback

    def plan(self, context: PlanContext) -> list[ProposedStep]:
        user = _describe_plan_context(context, self._lab)
        resp = self._transport.call(_PLANNER_SYSTEM, user)
        if self._lab is not None:
            # Persist a planner claim as an Annotation attached to the lab-level
            # "planner" pseudo-record id scoped by campaign.
            _persist_claim(
                self._lab,
                f"planner:{context.campaign_id}",
                "planner",
                user,
                resp,
                loose=True,
            )
        data = _safe_json(resp.text)
        raw_props = (data or {}).get("proposals") or []
        out: list[ProposedStep] = []
        for item in raw_props:
            try:
                op = str(item["operation"])
                inputs = dict(item.get("inputs") or {})
            except (KeyError, TypeError):
                continue
            out.append(
                ProposedStep(
                    operation=op,
                    inputs=inputs,
                    decision={
                        "planner": self.name,
                        "rationale": str(item.get("decision") or "")[:400],
                    },
                )
            )
        if not out and self._fallback is not None:
            return self._fallback.plan(context)
        return out


def _describe_plan_context(ctx: PlanContext, lab: Lab | None) -> str:
    lines = [
        "Objective:",
        f"  key={ctx.objective.key} direction={ctx.objective.direction} target={ctx.objective.target}",
    ]
    if ctx.acceptance and ctx.acceptance.rules:
        lines.append(f"Acceptance rules: {json.dumps(ctx.acceptance.rules)}")
    lines.append(f"Remaining budget: {ctx.remaining_budget}")
    if lab is not None:
        lines.append("Available tools:")
        for decl in lab.tools.list():
            lines.append(
                f"  - {decl.capability} (resource={decl.resource_kind}) "
                f"inputs={list(decl.inputs.keys()) if decl.inputs else []}"
            )
        lines.append("Available resources:")
        for res in lab.resources.list():
            lines.append(f"  - {res.name} kind={res.kind} caps={res.capabilities}")
    lines.append("Recent history (tail):")
    for r in list(ctx.history)[-6:]:
        lines.append(
            f"  - {r.operation} status={r.record_status} "
            f"inputs={json.dumps(r.inputs, default=str)[:120]}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CampaignDesigner
# ---------------------------------------------------------------------------


_DESIGNER_SYSTEM = """You are the Campaign Designer for an autonomous science lab
called autolab. A scientist has described a goal in free text. Given the available
tools and resources, output a draft Campaign and an optional WorkflowTemplate.
Reply with a single compact JSON object:

  {
    "campaign": {
      "name": "...",
      "description": "...",
      "objective": {"key": "...", "direction": "maximise|minimise", "target": <num?>, "unit": "..."?},
      "acceptance": {"rules": {"<key>": {"<op>": <threshold>, ...}, ...}}?,
      "budget": <int?>,
      "parallelism": <int?>
    },
    "workflow": {
      "name": "...",
      "description": "...",
      "steps": [
        {"step_id": "s1", "operation": "<tool>", "depends_on": [], "inputs": {...}}
      ]
    }?,
    "notes": "short human rationale"
  }

Rules:
- Use only tools that appear in the `tools` list.
- The objective.key MUST match an output field the chosen tools produce.
- Emit ONLY the JSON; no prose.
- If resources are insufficient for the stated goal, still return a best-effort draft
  and describe the mismatch in `notes`.
"""


@dataclass
class DesignResult:
    """Output of :meth:`CampaignDesigner.design`."""

    campaign_json: dict[str, Any]
    workflow_json: dict[str, Any] | None
    notes: str
    raw: ClaudeResponse


class CampaignDesigner:
    """Free text → draft Campaign + WorkflowTemplate.

    Nothing is registered or run here — the scientist reviews the draft
    on the Console and submits it with a second click.  This preserves
    the "goal is immutable once a Campaign starts" invariant.
    """

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
    ) -> None:
        self._lab = lab
        self._transport = transport or ClaudeTransport()

    def design(self, text: str) -> DesignResult:
        user = _describe_design_context(text, self._lab)
        resp = self._transport.call(_DESIGNER_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:draft", "campaign_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        return DesignResult(
            campaign_json=dict(data.get("campaign") or {}),
            workflow_json=dict(data["workflow"]) if data.get("workflow") else None,
            notes=str(data.get("notes") or ""),
            raw=resp,
        )


def _describe_design_context(text: str, lab: Lab | None) -> str:
    lines = ["User goal (verbatim):", text, "", "Tool catalogue:"]
    if lab is not None:
        for decl in lab.tools.list():
            lines.append(
                f"  - {decl.capability} (module {decl.module}) "
                f"resource={decl.resource_kind} inputs={list(decl.inputs.keys()) if decl.inputs else []} "
                f"outputs={list(decl.outputs.keys()) if decl.outputs else []}"
            )
        lines.append("Available resources:")
        for r in lab.resources.list():
            lines.append(f"  - {r.name} kind={r.kind} caps={r.capabilities}")
    else:
        lines.append("  (no Lab context — fall back to minimal stub)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Materialisation helpers — convert designer JSON into typed autolab models.
# ---------------------------------------------------------------------------


def campaign_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Normalise a designer draft into kwargs accepted by :class:`Campaign`.

    Kept as a dict so the server can surface it untouched; the caller
    constructs the real model.  Raises :class:`ValueError` on a
    structurally broken draft.
    """
    if not isinstance(draft, dict) or "name" not in draft:
        raise ValueError("draft campaign must be an object with a 'name' field")
    obj = draft.get("objective") or {}
    if "key" not in obj:
        raise ValueError("draft campaign must declare objective.key")
    # Return a *dict* — Campaign construction is the server's job.
    return draft


def workflow_template_from_draft(draft: dict[str, Any]) -> WorkflowTemplate:
    steps = []
    for s in draft.get("steps") or []:
        steps.append(
            WorkflowStep(
                step_id=str(s["step_id"]),
                operation=str(s["operation"]),
                depends_on=list(s.get("depends_on") or []),
                inputs=dict(s.get("inputs") or {}),
                input_mappings=dict(s.get("input_mappings") or {}),
                produces_sample=bool(s.get("produces_sample") or False),
                destructive=bool(s.get("destructive") or False),
                branch_id=s.get("branch_id"),
                acceptance=_accept_from(s.get("acceptance")),
            )
        )
    return WorkflowTemplate(
        name=str(draft.get("name") or "designed-workflow"),
        description=draft.get("description"),
        steps=steps,
        acceptance=_accept_from(draft.get("acceptance")),
        typical_duration_s=draft.get("typical_duration_s"),
        metadata=dict(draft.get("metadata") or {}),
    )


def _accept_from(raw: Any) -> AcceptanceCriteria | None:
    if not raw:
        return None
    if isinstance(raw, AcceptanceCriteria):
        return raw
    if isinstance(raw, dict) and "rules" in raw:
        return AcceptanceCriteria(rules=dict(raw["rules"]))
    return None


def objective_from(raw: dict[str, Any]) -> Objective:
    return Objective(
        key=str(raw["key"]),
        direction=raw.get("direction", "maximise"),
        target=raw.get("target"),
        unit=raw.get("unit"),
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _safe_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    # Sometimes Claude wraps the JSON in ```json fences; strip them.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def _persist_claim(
    lab: Lab,
    target_record_id: str,
    author_label: str,
    prompt_text: str,
    resp: ClaudeResponse,
    *,
    loose: bool = False,
) -> None:
    """Append an Annotation to the ledger carrying the Claude call.

    ``loose=True`` means the target record id may not exist (it's a
    pseudo-record id used to attach planner/designer claims that aren't
    tied to an Operation Record).  In that case we first ensure a
    placeholder Record exists so the annotation always has a valid
    target, preserving the "every LLM call is a Record" invariant.
    """
    import asyncio

    from autolab.models import Record as _Record

    payload: dict[str, Any] = {
        "role": author_label,
        "model": resp.model,
        "prompt_sha256": resp.prompt_hash,
        "offline": resp.offline,
        "prompt_preview": prompt_text[:800],
        "response_text": resp.text[:4000],
    }

    async def _persist() -> None:
        if loose and lab.ledger.get(target_record_id) is None:
            # Materialise a Record for the pseudo-target so future annotations
            # land cleanly. The Record is marked "completed" so the ledger's
            # append-only invariant still permits annotations.
            session = lab.new_session()
            placeholder = _Record(
                id=target_record_id,
                lab_id=lab.lab_id,
                session_id=session.id,
                operation=f"claude.{author_label}",
                module=f"claude/{author_label}",
                record_status="completed",
                tags=["claude", author_label],
            )
            try:
                await lab.ledger.append(placeholder)
            except Exception:
                # Another concurrent call may have created it.
                pass
        ann = Annotation(
            target_record_id=target_record_id,
            kind="claim",
            body=payload,
            author=f"claude/{author_label}",
        )
        await lab.annotate(ann)

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            task = asyncio.ensure_future(_persist())
            _PENDING_CLAIM_TASKS.add(task)

            def _done(t: asyncio.Task) -> None:
                _PENDING_CLAIM_TASKS.discard(t)
                try:
                    t.result()
                except Exception:
                    pass

            task.add_done_callback(_done)
            return
        asyncio.run(_persist())
    except Exception:
        if not loose:
            raise


__all__ = [
    "CLAUDE_MODEL_DEFAULT",
    "CampaignDesigner",
    "ClaudePlanner",
    "ClaudePolicyProvider",
    "ClaudeResponse",
    "ClaudeTransport",
    "DesignResult",
    "campaign_from_draft",
    "objective_from",
    "workflow_template_from_draft",
]
