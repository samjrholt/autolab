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

import ast
import asyncio
import base64
import hashlib
import json
import os
import re
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
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

# claude-opus-4-7 has a 1M-token context window by default (confirmed Anthropic docs 2026-04).
# Override via AUTOLAB_CLAUDE_MODEL env var to switch models without editing code.
CLAUDE_MODEL_DEFAULT: str = os.environ.get("AUTOLAB_CLAUDE_MODEL", "claude-opus-4-7")
_TOOL_LINE_RE = re.compile(
    r"^\s*-\s*(?P<capability>.+?)\s+\(module [^)]+\)\s+resource=(?P<resource>\S+)\s+"
    r"inputs=(?P<inputs>\[[^\]]*\])\s+outputs=(?P<outputs>\[[^\]]*\])\s*$"
)
_RANGE_HINT_RE = re.compile(
    r"\[[^\]]+\]|\bbetween\b|\bfrom\b.+\bto\b|\bsweep\b|\bvary\b|\bscan\b|\bfix(?:ed)?\b"
)

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
    with suppress(TimeoutError, Exception):
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True),
            timeout=timeout,
        )


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
    context_tokens: int | None = None


def _hash_prompt(system: str, user: str, images: list[bytes] | None = None) -> str:
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    for img in images or []:
        h.update(b"\x01")
        h.update(img[:512])  # hash first 512 bytes per image
    return h.hexdigest()


class ClaudeTransport:
    """Thin wrapper over the Anthropic SDK with an offline fallback."""

    def __init__(
        self,
        *,
        model: str = CLAUDE_MODEL_DEFAULT,
        api_key: str | None = None,
        offline: bool | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if offline is None:
            self.offline = key is None or os.environ.get("AUTOLAB_CLAUDE_OFFLINE") == "1"
        else:
            self.offline = offline
        self._api_key = key
        self._client: Any | None = None

    def call(
        self,
        system: str,
        user: str,
        *,
        images: list[bytes] | None = None,
    ) -> ClaudeResponse:
        if self.offline:
            return ClaudeResponse(
                text=_offline_response(system, user),
                model=f"{self.model}/offline",
                prompt_hash=_hash_prompt(system, user, images),
                offline=True,
            )
        if self._client is None:
            import anthropic  # local import — optional dep at runtime

            self._client = anthropic.Anthropic(api_key=self._api_key)
        content = _build_user_content(user, images)
        import anthropic as _anthropic
        _delays = [2, 4, 8]
        for _attempt, _delay in enumerate(_delays + [None]):
            try:
                resp = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": content}],
                )
                break
            except _anthropic.OverloadedError:
                if _delay is None:
                    raise
                import time
                time.sleep(_delay)
        text_parts = [
            b.text for b in resp.content if getattr(b, "type", "text") == "text"
        ]
        ctx_tokens = getattr(getattr(resp, "usage", None), "input_tokens", None)
        return ClaudeResponse(
            text="".join(text_parts),
            model=self.model,
            prompt_hash=_hash_prompt(system, user, images),
            offline=False,
            context_tokens=ctx_tokens,
        )

    async def acall(
        self,
        system: str,
        user: str,
        *,
        images: list[bytes] | None = None,
    ) -> ClaudeResponse:
        """Async version of call() — runs the Anthropic SDK in a thread pool."""
        if self.offline:
            return ClaudeResponse(
                text=_offline_response(system, user),
                model=f"{self.model}/offline",
                prompt_hash=_hash_prompt(system, user, images),
                offline=True,
            )
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        content = _build_user_content(user, images)
        import anthropic as _anthropic
        _delays = [2, 4, 8]
        for _attempt, _delay in enumerate(_delays + [None]):
            try:
                resp = await asyncio.to_thread(
                    self._client.messages.create,
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": content}],
                )
                break
            except _anthropic.OverloadedError:
                if _delay is None:
                    raise
                await asyncio.sleep(_delay)
        text_parts = [
            b.text for b in resp.content if getattr(b, "type", "text") == "text"
        ]
        ctx_tokens = getattr(getattr(resp, "usage", None), "input_tokens", None)
        return ClaudeResponse(
            text="".join(text_parts),
            model=self.model,
            prompt_hash=_hash_prompt(system, user, images),
            offline=False,
            context_tokens=ctx_tokens,
        )


def _build_user_content(
    text: str, images: list[bytes] | None
) -> str | list[dict[str, Any]]:
    """Build the user message content. Returns a plain string if no images."""
    if not images:
        return text
    content: list[dict[str, Any]] = []
    for img_bytes in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(img_bytes).decode("ascii"),
            },
        })
    content.append({"type": "text", "text": text})
    return content


def _offline_response(system: str, user: str) -> str:
    """Scripted response for offline tests.

    Inspects a few keywords in the prompt to return structured JSON that
    the calling agent knows how to parse.  Good enough to boot the
    server and exercise integration tests without real credentials.
    """
    lowered = (system + "\n" + user).lower()
    if "data chat analyst" in lowered:
        return json.dumps(
            {
                "answer": "[offline fallback] Generated a chart from the ledger context.",
                "chart": {
                    "type": "line",
                    "title": "Best score by trial",
                    "subtitle": "Best-so-far objective values from completed ledger records.",
                    "x": "trial",
                    "y": "objective_value",
                    "series_by": "campaign_name",
                    "transform": "best_so_far",
                    "aggregate": "none",
                    "filters": [],
                },
            }
        )
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
        goal_text_raw = user.split("User goal (verbatim):", 1)[-1]
        goal_text_raw = goal_text_raw.split("Tool catalogue:", 1)[0]
        if "Refinement instruction (verbatim):" in user:
            refinement_text_raw = user.split("Refinement instruction (verbatim):", 1)[-1]
            refinement_text_raw = refinement_text_raw.split(
                "Produce a revised proposal that preserves the user's edits where", 1
            )[0]
            goal_text_raw = "\n".join([goal_text_raw, refinement_text_raw])
        goal_text = goal_text_raw.lower()
        if "refinement instruction (verbatim):" in lowered:
            refinement_text = lowered.split("refinement instruction (verbatim):", 1)[-1]
            refinement_text = refinement_text.split(
                "produce a revised proposal that preserves the user's edits where", 1
            )[0]
            goal_text = "\n".join([goal_text, refinement_text])
        tools = _offline_extract_tool_catalogue(user)
        chosen_tool = _offline_select_tool(goal_text, tools)
        objective_key = _offline_select_objective(goal_text_raw, goal_text, chosen_tool, tools)
        has_input_guidance = _offline_has_input_guidance(goal_text, chosen_tool)
        questions: list[str] = []
        if chosen_tool is None:
            questions.append("Which operation or workflow should autolab run?")
        if objective_key is None:
            questions.append("Which output or metric should the campaign optimise?")
        if chosen_tool is not None and chosen_tool["inputs"] and not has_input_guidance:
            questions.append("Which inputs, search ranges, or fixed conditions should define the campaign?")
        if questions:
            return json.dumps(
                {
                    "campaign": {},
                    "workflow": None,
                    "questions": questions,
                    "ready_to_apply": False,
                    "notes": "I need the operation, objective, and campaign conditions before I can draft a defensible campaign.",
                }
            )
        direction = "minimise" if any(word in goal_text for word in ("minimise", "minimize", "reduce", "lower")) else "maximise"
        capability = chosen_tool["capability"] if chosen_tool is not None else "operation"
        objective = objective_key or "objective"
        workflow = None
        if chosen_tool is not None:
            workflow = {
                "name": f"{capability}-workflow".replace("_", "-"),
                "description": f"Run {capability} as the evaluation workflow for this campaign.",
                "steps": [{"step_id": "run", "operation": capability, "depends_on": [], "inputs": {}}],
            }
        return json.dumps(
            {
                "campaign": {
                    "name": f"{capability}-{objective}".replace("_", "-"),
                    "description": f"[offline fallback] campaign draft for {capability}",
                    "objective": {"key": objective, "direction": direction},
                    "budget": 16,
                    "parallelism": 1,
                },
                "workflow": workflow,
                "questions": [],
                "ready_to_apply": True,
                "notes": "Anthropic API key not configured; returning a generic offline draft.",
            }
        )
    if "lab setup" in lowered or "lab_setup_designer" in lowered:
        scientist_text = lowered.split("scientist description (verbatim):", 1)[-1]
        scientist_text = scientist_text.split("already registered", 1)[0]
        if "slurm" in scientist_text or "login node" in scientist_text:
            return json.dumps(
                {
                    "resources": [
                        {
                            "name": "slurm-login",
                            "kind": "computer",
                            "backend": "slurm",
                            "connection": {},
                            "tags": {"scheduler": "slurm", "role": "login_node"},
                            "capabilities": {"scheduler": "slurm", "role": "login_node"},
                            "description": "Slurm login/submit host. Connection details are still needed before autolab can run anything.",
                        }
                    ],
                    "operations": [],
                    "workflow": None,
                    "questions": [
                        "What SSH alias or hostname should autolab use for the login node?",
                        "What remote working directory may autolab create job folders in?",
                        "How should Python be activated on the server (module load, conda, pixi, venv, or system python)?",
                        "What Slurm partition/account/time limit and CPU/GPU/memory request should jobs use?",
                        "Where is the script or repo to run, and what command should launch it?",
                        "What outputs should autolab collect, and what smoke-test command proves the setup works?",
                    ],
                    "ready_to_apply": False,
                    "notes": "A Slurm login node is only a Resource. I still need the connection and invocation details before proposing runnable capabilities.",
                }
            )
        vague_setup = (
            "set up a lab" in scientist_text
            or "setup a lab" in scientist_text
            or "new lab" in scientist_text
        ) and not any(
            term in scientist_text
            for term in (
                "host",
                "computer",
                "script",
                "instrument",
                "furnace",
                "xrd",
                "magnet",
                "simulation",
                "simulator",
                "equipment",
                "server",
                "slurm",
                "websocket",
            )
        )
        if vague_setup:
            return json.dumps(
                {
                    "resources": [],
                    "operations": [],
                    "workflow": None,
                    "questions": [
                        "What equipment or compute resources should autolab use?",
                        "What operation should the lab be able to run first?",
                        "What output should be optimised or checked?",
                    ],
                    "ready_to_apply": False,
                    "notes": "I need concrete resources, operations, and desired outputs before I can register a useful setup.",
                }
            )
        return json.dumps(
            {
                "resources": [
                    {
                        "name": "local-workstation",
                        "kind": "computer",
                        "backend": "local",
                        "connection": {"working_dir": ".autolab-work"},
                        "tags": {"role": "workstation"},
                        "capabilities": {"backend": "local", "connection": {"working_dir": ".autolab-work"}},
                        "description": "Local workstation for running scripts and simulations.",
                        "typical_operation_durations": {"run_simulation": 5},
                    },
                ],
                "operations": [
                    {
                        "capability": "run_simulation",
                        "resource_kind": "computer",
                        "description": "Run a local simulation script and collect a numeric score.",
                        "inputs": {"x": "float"},
                        "outputs": {"score": "float"},
                        "produces_sample": False,
                        "destructive": False,
                        "typical_duration_s": 5,
                    }
                ],
                "workflow": {
                    "name": "simulation-workflow",
                    "description": "Run the local simulation and record the score.",
                    "steps": [
                        {"step_id": "simulate", "operation": "run_simulation", "depends_on": []}
                    ],
                },
                "questions": [],
                "ready_to_apply": True,
                "notes": "Offline setup draft generated from the lab description.",
            }
        )
    if "resource designer" in lowered or "resource_designer" in lowered:
        scientist_text = lowered.split("scientist description (verbatim):", 1)[-1]
        if "slurm" in scientist_text or "login node" in scientist_text:
            return json.dumps(
                {
                    "name": "slurm-login",
                    "kind": "computer",
                    "backend": "slurm",
                    "connection": {},
                    "tags": {"scheduler": "slurm", "role": "login_node"},
                    "capabilities": {"scheduler": "slurm", "role": "login_node"},
                    "description": "Slurm login/submit host. Connection details are required before it can run capabilities.",
                    "questions": [
                        "What SSH alias or hostname should autolab use?",
                        "What remote working directory may autolab use?",
                        "What Slurm partition/account/time/resources should jobs request?",
                        "What smoke-test command should prove the login node works?",
                    ],
                    "ready_to_apply": False,
                    "notes": "This is not ready to register as runnable until the connection and smoke-test details are known.",
                }
            )
        return json.dumps(
            {
                "name": "resource-1",
                "kind": "computer",
                "capabilities": {},
                "description": "[offline] scripted resource stub",
                "questions": [],
                "ready_to_apply": True,
                "notes": "Offline fallback — set ANTHROPIC_API_KEY for a real proposal.",
            }
        )
    if "tool designer" in lowered or "tool_designer" in lowered:
        return json.dumps(
            {
                "capability": "example_capability",
                "resource_kind": "computer",
                "module": "example.stub.v1",
                "description": "[offline] scripted tool stub",
                "inputs": {},
                "outputs": {"score": "float"},
                "produces_sample": False,
                "destructive": False,
                "typical_duration_s": 5,
                "questions": [],
                "ready_to_apply": True,
                "notes": "Offline fallback — set ANTHROPIC_API_KEY for a real proposal.",
            }
        )
    if "workflow designer" in lowered or "workflow_designer" in lowered:
        return json.dumps(
            {
                "name": "offline-workflow",
                "description": "[offline] scripted workflow stub",
                "steps": [],
                "notes": "Offline fallback — set ANTHROPIC_API_KEY for a real proposal.",
            }
        )
    return "{}"


def _offline_extract_tool_catalogue(user: str) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    in_catalogue = False
    for line in user.splitlines():
        stripped = line.strip()
        if stripped == "Tool catalogue:":
            in_catalogue = True
            continue
        if not in_catalogue:
            continue
        if stripped == "Available resources:":
            break
        match = _TOOL_LINE_RE.match(line)
        if not match:
            continue
        try:
            inputs = ast.literal_eval(match.group("inputs"))
            outputs = ast.literal_eval(match.group("outputs"))
        except (ValueError, SyntaxError):
            inputs = []
            outputs = []
        tools.append(
            {
                "capability": str(match.group("capability")).strip(),
                "resource_kind": str(match.group("resource")).strip(),
                "inputs": [str(value) for value in inputs or []],
                "outputs": [str(value) for value in outputs or []],
            }
        )
    return tools


def _offline_normalise_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _offline_mentions_identifier(text: str, identifier: str) -> bool:
    if not identifier:
        return False
    normalised_text = f" {_offline_normalise_identifier(text)} "
    aliases = {
        identifier,
        identifier.replace("_", " "),
        identifier.replace("-", " "),
    }
    return any(f" {_offline_normalise_identifier(alias)} " in normalised_text for alias in aliases)


def _offline_select_tool(goal_text: str, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    for tool in tools:
        if _offline_mentions_identifier(goal_text, tool["capability"]):
            return tool
    return None


def _offline_select_objective(
    goal_text_raw: str,
    goal_text: str,
    chosen_tool: dict[str, Any] | None,
    tools: list[dict[str, Any]],
) -> str | None:
    candidate_outputs = chosen_tool["outputs"] if chosen_tool is not None else [
        output for tool in tools for output in tool["outputs"]
    ]
    for output in candidate_outputs:
        if _offline_mentions_identifier(goal_text, output):
            return output
    generic_match = re.search(
        r"\b(?:maximise|maximize|minimise|minimize|optimise|optimize)\s+([A-Za-z0-9_]+)",
        goal_text_raw,
        flags=re.IGNORECASE,
    )
    if generic_match:
        return generic_match.group(1)
    if chosen_tool is not None and len(chosen_tool["outputs"]) == 1 and any(
        word in goal_text
        for word in ("maximise", "maximize", "minimise", "minimize", "optimise", "optimize")
    ):
        return chosen_tool["outputs"][0]
    return None


def _offline_has_input_guidance(goal_text: str, chosen_tool: dict[str, Any] | None) -> bool:
    if chosen_tool is None or not chosen_tool["inputs"]:
        return False
    if any(_offline_mentions_identifier(goal_text, name) for name in chosen_tool["inputs"]):
        return True
    return bool(_RANGE_HINT_RE.search(goal_text))


# ---------------------------------------------------------------------------
# Ledger-context helpers (Tasks 2 & 3)
# ---------------------------------------------------------------------------

_MAX_ARRAY_DISPLAY = 50
_MAX_CONTEXT_IMAGES = 5


def _truncate_value(v: Any, max_array: int = _MAX_ARRAY_DISPLAY) -> Any:
    """Truncate lists > max_array to [first5…last5] (N total)."""
    if isinstance(v, list) and len(v) > max_array:
        head = v[:5]
        tail = v[-5:]
        return head + [f"... ({len(v)} total) ..."] + tail
    if isinstance(v, dict):
        return {k: _truncate_value(val, max_array) for k, val in v.items()}
    return v


def _record_short_hash(record: Any) -> str:
    """First 6 hex chars of the record checksum, prefixed 0x."""
    cs = getattr(record, "checksum", None) or ""
    return f"0x{cs[:6]}" if cs else "0x??????"


def _serialise_record(record: Any) -> str:
    """Compact single-record text block (≤ ~1 KB)."""
    short_hash = _record_short_hash(record)
    ts = ""
    created = getattr(record, "created_at", None)
    if created is not None:
        ts = getattr(created, "isoformat", lambda: str(created))()[:19]

    inputs_trunc = _truncate_value(getattr(record, "inputs", {}) or {})
    outputs_trunc = {
        k: ("<png path>" if str(k).endswith("_png") or str(k).endswith("_image") else v)
        for k, v in (_truncate_value(getattr(record, "outputs", {}) or {})).items()
    }

    parts = [
        f"[Record {short_hash}]",
        f"  operation : {getattr(record, 'operation', '?')}",
        f"  status    : {getattr(record, 'record_status', '?')}",
        f"  timestamp : {ts}",
        f"  inputs    : {json.dumps(inputs_trunc, default=str)[:400]}",
        f"  outputs   : {json.dumps(outputs_trunc, default=str)[:400]}",
    ]
    fm = getattr(record, "failure_mode", None)
    if fm:
        parts.append(f"  failure   : {fm}")
    dec = getattr(record, "decision", None)
    if dec:
        parts.append(f"  decision  : {json.dumps(dec, default=str)[:200]}")
    return "\n".join(parts)


def _has_png_output(record: Any) -> bool:
    outputs = getattr(record, "outputs", None) or {}
    return any(str(k).endswith("_png") or str(k).endswith("_image") for k in outputs)


def _load_png_bytes(record: Any) -> bytes | None:
    """Read the first PNG/image output path from a record, return bytes."""
    outputs = getattr(record, "outputs", None) or {}
    for k, v in outputs.items():
        if (str(k).endswith("_png") or str(k).endswith("_image")) and isinstance(v, str):
            try:
                p = Path(v)
                if p.exists():
                    return p.read_bytes()
            except (OSError, ValueError):
                pass
    return None


def _build_ledger_context(
    lab: Any,
    campaign_id: str,
    current_record: Any,
) -> tuple[str, list[bytes]]:
    """Fetch all campaign records and build a text block + image list.

    Returns (ledger_text, image_bytes_list).
    Images are collected from the triggering record first (always), then
    from the most recent figure-bearing records up to _MAX_CONTEXT_IMAGES.
    """
    try:
        records = list(lab.ledger.iter_records())
    except Exception:  # noqa: BLE001
        return "", []

    if not records:
        return "", []

    n_current = sum(1 for r in records if getattr(r, "campaign_id", None) == campaign_id)
    n_prior = len(records) - n_current
    text_lines = [
        f"=== Lab Ledger ({len(records)} records: {n_prior} from prior runs, "
        f"{n_current} from current campaign {campaign_id}) ===\n"
    ]
    for rec in records:
        text_lines.append(_serialise_record(rec))
    ledger_text = "\n".join(text_lines)

    # Only attach images when the triggering record is itself figure-bearing.
    # Non-visual decisions (material lookup, intervention, equipment failures)
    # do not benefit from prior hysteresis PNGs and would just bloat tokens.
    image_bytes: list[bytes] = []
    current_png = _load_png_bytes(current_record)
    if current_png is not None:
        image_bytes.append(current_png)
        figure_records = [
            r for r in reversed(records)
            if _has_png_output(r)
            and getattr(r, "id", None) != getattr(current_record, "id", None)
        ]
        for r in figure_records:
            if len(image_bytes) >= _MAX_CONTEXT_IMAGES:
                break
            png = _load_png_bytes(r)
            if png is not None:
                image_bytes.append(png)

    return ledger_text, image_bytes


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

_LEDGER_CITATION_PREAMBLE = """\
You have access to the full prior history of this lab as structured records below.
Each record has a short hash identifier (e.g. 0x4a2c).
When your reasoning is informed by a specific prior record, CITE ITS HASH INLINE,
e.g. "Record 0x4a2c showed the same shoulder after the 1450 \u00b0C anneal."
Cite liberally. If no prior record is relevant, say so and reason from first principles.
Any rendered figures attached as images correspond to the most recent figure-bearing records;
analyse them like a scientist reading their own lab notebook.

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
        images: list[bytes] = []
        system = _POLICY_SYSTEM

        if self._lab is not None:
            ledger_text, images = _build_ledger_context(
                self._lab, context.campaign_id, context.record
            )
            if ledger_text:
                system = _LEDGER_CITATION_PREAMBLE + ledger_text + "\n\n" + _POLICY_SYSTEM

        resp = self._transport.call(system, user, images=images or None)

        if self._lab is not None:
            _persist_claim(self._lab, context.record.id, "policy_provider", user, resp)
            if resp.context_tokens is not None:
                try:
                    from autolab.events import Event
                    self._lab.events.publish(Event(
                        kind="context_tokens",
                        payload={
                            "campaign_id": context.campaign_id,
                            "record_id": context.record.id,
                            "context_tokens": resp.context_tokens,
                            "model": resp.model,
                        },
                    ))
                except Exception:  # noqa: BLE001
                    pass

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
            f"fmode={r.failure_mode}"
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
- When a "Search space bounds" section is present, `inputs` MUST contain ONLY the
  search-space parameter names (one entry per parameter), with values inside the
  declared bounds or `choices`. Do NOT add extra fields from the tool schema —
  the campaign fills those in itself. The `decision` object is for free-form
  rationale only, not for parameter values.
- When no Search space bounds section is present, `inputs` MUST respect the
  tool's input schema directly.
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
        operation: str | None = None,
        search_space: dict[str, dict[str, Any]] | None = None,
        batch_size: int = 1,
        fixed_inputs: dict[str, Any] | None = None,
        input_routing: dict[str, str] | None = None,
    ) -> None:
        super().__init__(policy=policy or ClaudePolicyProvider(lab=lab, transport=transport))
        self._lab = lab
        self._transport = transport or ClaudeTransport()
        self._fallback = fallback
        self._operation = operation
        self._search_space = dict(search_space or {})
        self._batch_size = max(1, int(batch_size))
        self._fixed_inputs = dict(fixed_inputs or {})
        self._input_routing = dict(input_routing or {})

    def plan(self, context: PlanContext) -> list[ProposedStep]:
        user = _describe_plan_context(
            context,
            self._lab,
            operation=self._operation,
            search_space=self._search_space,
            fixed_inputs=self._fixed_inputs,
            batch_size=self._batch_size,
            input_routing=self._input_routing,
        )
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
                op = str(item.get("operation") or self._operation)
                inputs = dict(self._fixed_inputs)
                inputs.update(dict(item.get("inputs") or {}))
            except (KeyError, TypeError):
                continue
            if self._operation:
                # For workflow-backed campaigns the planner must target the
                # tunable workflow step. If Claude names an upstream dependency
                # in its JSON, keep the campaign on the configured target.
                op = self._operation
            inputs = _normalise_planner_inputs(inputs, self._search_space)
            if inputs is None:
                continue
            step_inputs: dict[str, dict[str, Any]] | None = None
            if self._input_routing:
                step_inputs = {}
                for name, target in self._input_routing.items():
                    if name in inputs:
                        step_inputs.setdefault(target, {})[name] = inputs.pop(name)
            out.append(
                ProposedStep(
                    operation=op,
                    inputs=inputs,
                    step_inputs=step_inputs,
                    decision={
                        "planner": self.name,
                        "method": "llm",
                        "rationale": str(item.get("decision") or data.get("reason") or "")[:400],
                    },
                )
            )
            if len(out) >= min(self._batch_size, context.remaining_budget or self._batch_size):
                break
        if not out and self._fallback is not None:
            return self._fallback.plan(context)
        return out


def _describe_plan_context(
    ctx: PlanContext,
    lab: Lab | None,
    *,
    operation: str | None = None,
    search_space: dict[str, dict[str, Any]] | None = None,
    fixed_inputs: dict[str, Any] | None = None,
    batch_size: int = 1,
    input_routing: dict[str, str] | None = None,
) -> str:
    lines = [
        "Objective:",
        f"  key={ctx.objective.key} direction={ctx.objective.direction} target={ctx.objective.target}",
    ]
    if ctx.acceptance and ctx.acceptance.rules:
        lines.append(f"Acceptance rules: {json.dumps(ctx.acceptance.rules)}")
    lines.append(f"Remaining budget: {ctx.remaining_budget}")
    lines.append(f"Requested batch size: {batch_size}")
    if operation:
        lines.extend(
            [
                "Optimizer target:",
                f"  operation={operation}",
                "  Return proposals for this operation only.",
            ]
        )
    if search_space:
        lines.append("Search space bounds:")
        for name, spec in search_space.items():
            lines.append(f"  - {name}: {json.dumps(spec, default=str)}")
    if input_routing:
        lines.append("Parameter routing (which workflow step receives each search-space param):")
        for name, target in input_routing.items():
            lines.append(f"  - {name} -> step_id={target}")
    if fixed_inputs:
        lines.append(f"Fixed inputs: {json.dumps(fixed_inputs, default=str)}")
    if lab is not None:
        lines.append("Available tools:")
        for decl in lab.tools.list():
            lines.append(
                f"  - {decl.capability} (resource={decl.resource_kind}) "
                f"inputs={json.dumps(decl.inputs or {}, default=str)} "
                f"outputs={json.dumps(decl.outputs or {}, default=str)}"
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


def _normalise_planner_inputs(
    inputs: dict[str, Any],
    search_space: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Validate and coerce LLM-proposed inputs against optional bounds."""
    if not search_space:
        return inputs
    out = dict(inputs)
    for name, spec in search_space.items():
        if name not in out:
            return None
        kind = spec.get("type", "float")
        value = out[name]
        if kind == "categorical":
            choices = list(spec.get("choices") or [])
            if value not in choices:
                return None
            continue
        try:
            low = float(spec["low"])
            high = float(spec["high"])
            numeric = float(value)
        except (KeyError, TypeError, ValueError):
            return None
        numeric = min(max(numeric, low), high)
        out[name] = round(numeric) if kind == "int" else numeric
    return out


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
    "questions": [
      "Which metric should be optimised?"
    ],
    "ready_to_apply": false,
    "notes": "short human rationale"
  }

Rules:
- Use only tools that appear in the `tools` list.
- The objective.key MUST match an output field the chosen tools produce.
- If required information is missing, ask concise questions in `questions`,
  set `ready_to_apply` false, and leave `campaign` empty or partial.
- Required campaign information is: operation/capability to run, objective
  metric, and enough inputs or search dimensions to define the search.
- Emit ONLY the JSON; no prose.
- If resources are insufficient for the stated goal, still return a best-effort draft
  and describe the mismatch in `notes`.
"""


@dataclass
class DesignResult:
    """Output of :meth:`CampaignDesigner.design`."""

    campaign_json: dict[str, Any]
    workflow_json: dict[str, Any] | None
    questions: list[str]
    ready_to_apply: bool
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

    def design(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> DesignResult:
        user = _describe_design_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = self._transport.call(_DESIGNER_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:draft", "campaign_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        return DesignResult(
            campaign_json=dict(data.get("campaign") or {}),
            workflow_json=dict(data["workflow"]) if data.get("workflow") else None,
            questions=[str(q) for q in data.get("questions") or []],
            ready_to_apply=bool(data.get("ready_to_apply", True)),
            notes=str(data.get("notes") or ""),
            raw=resp,
        )

    async def adesign(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> DesignResult:
        user = _describe_design_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = await self._transport.acall(_DESIGNER_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:draft", "campaign_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        return DesignResult(
            campaign_json=dict(data.get("campaign") or {}),
            workflow_json=dict(data["workflow"]) if data.get("workflow") else None,
            questions=[str(q) for q in data.get("questions") or []],
            ready_to_apply=bool(data.get("ready_to_apply", True)),
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
            with suppress(Exception):
                await lab.ledger.append(placeholder)
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
                with suppress(Exception):
                    t.result()

            task.add_done_callback(_done)
            return
        asyncio.run(_persist())
    except Exception:
        if not loose:
            raise


_LAB_SETUP_SYSTEM = """You are the Lab Setup Assistant for an autonomous science lab
framework called autolab. A scientist is describing their lab equipment and what
they want to do. Propose the resources and operations they should register.

Reply with a single compact JSON object:

  {
    "resources": [
      {
        "name": "tube-furnace-A",
        "kind": "furnace",
        "backend": "local|ssh_exec|slurm|websocket|mcp|custom",
        "connection": {"host": "ssh-alias-or-host", "remote_root": "~/.autolab-work"},
        "tags": {"max_temp_k": 1400},
        "capabilities": {"max_temp_k": 1400, "atmosphere": ["Ar", "N2"]},
        "description": "Tube furnace in bay 1"
      }
    ],
    "operations": [
      {
        "capability": "sintering",
        "resource_kind": "furnace",
        "description": "Sinter a pellet at a target temperature and time",
        "inputs": {"composition": "dict", "temperature": "float", "time_hours": "float"},
        "outputs": {"phases": "list", "grain_size_nm": "float", "density": "float"},
        "produces_sample": true,
        "destructive": true,
        "typical_duration_s": 7200
      }
    ],
    "workflow": {
      "name": "suggested-workflow",
      "description": "...",
      "steps": [
        {"step_id": "s1", "operation": "weighing", "depends_on": []},
        {"step_id": "s2", "operation": "sintering", "depends_on": ["s1"]}
      ]
    },
    "questions": [
      "What temperature range should the furnace support?"
    ],
    "ready_to_apply": false,
    "notes": "Short rationale for the scientist"
  }

Rules:
- Use scientist-friendly capability names (weighing, sintering, xrd, magnetometry — not library names).
- If required information is missing, ask concise questions in `questions`,
  set `ready_to_apply` false, and only include proposals you can defend from
  the scientist's description.
- Required setup information is: concrete resources, the first operation(s) to
  run, and the outputs those operations produce.
- Resources describe where/how work happens. Use backend + connection + tags:
  local, ssh_exec, slurm (SSH submit host), websocket, mcp, or custom.
- For a server, Slurm partition, WebSocket instrument, MCP endpoint, or vendor
  API, do not mark ready_to_apply true until the connection, invocation shape,
  outputs, and a smoke-test are known.
- A Slurm login node alone is not a runnable capability. Ask for SSH alias/host,
  remote workdir, Python/environment activation, sbatch/srun details, script or
  repo path, expected outputs, and a smoke-test command.
- A WebSocket instrument alone is not a runnable capability. Ask for URL,
  protocol/messages, auth source if any, command to send, response schema,
  output mapping, and a smoke-test message.
- Resource names should be specific instances (tube-furnace-A, squid-1, xrd-1).
- Resource kinds should be generic categories (furnace, magnetometer, diffractometer, balance, ball_mill, computer).
- Each operation should map to exactly one real lab step a scientist would recognise.
- Include a suggested workflow if the steps form a natural sequence.
- Be practical: only propose what the scientist described. Don't invent equipment they didn't mention.
- Emit ONLY the JSON; no prose.
"""


@dataclass
class LabSetupResult:
    """Output of :meth:`LabSetupDesigner.design`."""

    resources: list[dict[str, Any]]
    operations: list[dict[str, Any]]
    workflow: dict[str, Any] | None
    questions: list[str]
    ready_to_apply: bool
    notes: str
    raw: ClaudeResponse


class LabSetupDesigner:
    """Free text → proposed resources, operations, and workflow for a lab.

    Same propose → approve → submit pattern as the CampaignDesigner.
    Nothing is registered here — the scientist reviews the proposal and
    selects what to apply.
    """

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
    ) -> None:
        self._lab = lab
        self._transport = transport or ClaudeTransport()

    def design(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> LabSetupResult:
        user = _describe_setup_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = self._transport.call(_LAB_SETUP_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "setup:draft", "lab_setup_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        return LabSetupResult(
            resources=list(data.get("resources") or []),
            operations=list(data.get("operations") or []),
            workflow=dict(data["workflow"]) if data.get("workflow") else None,
            questions=[str(q) for q in data.get("questions") or []],
            ready_to_apply=bool(data.get("ready_to_apply", True)),
            notes=str(data.get("notes") or ""),
            raw=resp,
        )

    async def adesign(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> LabSetupResult:
        user = _describe_setup_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = await self._transport.acall(_LAB_SETUP_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "setup:draft", "lab_setup_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        return LabSetupResult(
            resources=list(data.get("resources") or []),
            operations=list(data.get("operations") or []),
            workflow=dict(data["workflow"]) if data.get("workflow") else None,
            questions=[str(q) for q in data.get("questions") or []],
            ready_to_apply=bool(data.get("ready_to_apply", True)),
            notes=str(data.get("notes") or ""),
            raw=resp,
        )


def _describe_setup_context(text: str, lab: Lab | None) -> str:
    lines = ["Scientist description (verbatim):", text, ""]
    if lab is not None:
        existing_resources = lab.resources.list()
        existing_tools = lab.tools.list()
        if existing_resources:
            lines.append("Already registered resources:")
            for r in existing_resources:
                lines.append(f"  - {r.name} kind={r.kind} caps={r.capabilities}")
        if existing_tools:
            lines.append("Already registered tools:")
            for t in existing_tools:
                lines.append(f"  - {t.capability} (module {t.module}) resource={t.resource_kind}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-entity designers — Resource / Tool / Workflow
#
# Each follows the same propose → refine → apply pattern.  Callers pass
# ``previous`` (the last proposal, possibly edited by the user) and
# ``instruction`` (a short refinement note like "make it 1600 K") to iterate.
# Offline fallbacks return minimal stubs keyed off the prompt so tests boot
# without credentials.
# ---------------------------------------------------------------------------


def _append_refinement(
    user: str,
    previous: dict[str, Any] | None,
    instruction: str | None,
) -> str:
    """Tack a "previous proposal + instruction" block onto a designer prompt."""
    parts = [user, ""]
    if previous:
        parts.append("Previous proposal (with any edits the user made):")
        try:
            parts.append(json.dumps(previous, indent=2, default=str)[:4000])
        except (TypeError, ValueError):
            parts.append(str(previous)[:4000])
    if instruction:
        parts.append("")
        parts.append("Refinement instruction (verbatim):")
        parts.append(instruction)
        parts.append("")
        parts.append(
            "Produce a revised proposal that preserves the user's edits where "
            "reasonable and addresses the refinement instruction."
        )
    return "\n".join(parts)


_RESOURCE_SYSTEM = """You are the Resource Designer for an autonomous science lab
framework called autolab. A scientist is describing ONE piece of lab equipment or
compute they want to register as a Resource. Propose a single resource.

Reply with a single compact JSON object:

  {
    "name": "tube-furnace-A",
    "kind": "furnace",
    "backend": "local|ssh_exec|slurm|websocket|mcp|custom",
    "connection": {"host": "ssh alias, websocket URL, or endpoint"},
    "tags": {"max_temp_k": 1400},
    "capabilities": {"max_temp_k": 1400, "atmosphere": "Ar"},
    "description": "Tube furnace in bay 1",
    "questions": [],
    "ready_to_apply": true,
    "notes": "Short rationale"
  }

Rules:
- name = a specific instance name (tube-furnace-A, slurm-gpu-partition, squid-1).
- kind = generic category (furnace, tube_furnace, arc_furnace, magnetometer,
  xrd, balance, slurm_partition, computer, vm, gpu_node, custom).
- capabilities = structured dict of numeric/string fields relevant to the kind.
- backend + connection describe how autolab reaches it. For WebSocket equipment,
  include the URL/protocol details in connection once known.
- If connection or smoke-test details are missing for a remote/server/instrument,
  add questions and set ready_to_apply false.
- Emit ONLY the JSON; no prose.
"""


@dataclass
class ResourceProposal:
    """Output of :meth:`ResourceDesigner.design`."""

    resource: dict[str, Any]
    notes: str
    questions: list[str]
    ready_to_apply: bool
    raw: ClaudeResponse


class ResourceDesigner:
    """Free text → proposed Resource (one at a time), with iterative refinement."""

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
    ) -> None:
        self._lab = lab
        self._transport = transport or ClaudeTransport()

    def design(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> ResourceProposal:
        user = _describe_resource_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = self._transport.call(_RESOURCE_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:resource", "resource_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        notes = str(data.pop("notes", "") or "")
        questions = [str(q) for q in data.pop("questions", []) or []]
        ready_to_apply = bool(data.pop("ready_to_apply", not questions))
        return ResourceProposal(
            resource=dict(data),
            notes=notes,
            questions=questions,
            ready_to_apply=ready_to_apply,
            raw=resp,
        )

    async def adesign(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> ResourceProposal:
        user = _describe_resource_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = await self._transport.acall(_RESOURCE_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:resource", "resource_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        notes = str(data.pop("notes", "") or "")
        questions = [str(q) for q in data.pop("questions", []) or []]
        ready_to_apply = bool(data.pop("ready_to_apply", not questions))
        return ResourceProposal(
            resource=dict(data),
            notes=notes,
            questions=questions,
            ready_to_apply=ready_to_apply,
            raw=resp,
        )


def _describe_resource_context(text: str, lab: Lab | None) -> str:
    lines = [
        "You are the Resource Designer.",
        "",
        "Scientist description (verbatim):",
        text,
        "",
    ]
    if lab is not None:
        existing = lab.resources.list()
        if existing:
            lines.append("Already registered resources (avoid duplicating names):")
            for r in existing:
                lines.append(f"  - {r.name} kind={r.kind} caps={r.capabilities}")
    return "\n".join(lines)


_TOOL_SYSTEM = """You are the Capability Designer for an autonomous science lab framework
called autolab. A scientist is describing ONE capability they want to
register. Propose a single YAML-equivalent JSON declaration.

Reply with a single compact JSON object:

  {
    "capability": "sintering",
    "resource_kind": "furnace",
    "adapter": "dynamic|shell_command|custom",
    "module": "sintering.stub.v1",
    "description": "Sinter a pellet at a target temperature and time",
    "inputs":  {"composition": "dict", "temperature_k": "float", "time_h": "float"},
    "outputs": {"phases": "list", "grain_size_nm": "float", "density": "float"},
    "resource_requirements": {"max_temp_k": {">=": 1400}},
    "produces_sample": true,
    "destructive": true,
    "typical_duration_s": 7200,
    "notes": "Short rationale"
  }

Rules:
- capability = scientist-friendly verb (sintering, magnetometry, xrd, hysteresis_interpret).
- resource_kind = the generic resource category this capability binds to.
- inputs/outputs = map of name -> coarse type string (float, int, bool, list, dict, str).
- If the user describes an executable command, set adapter to shell_command and
  include command_template, timeout_seconds, and declared_outputs when known.
- If required invocation details are missing, return a partial proposal in notes
  and ask for the missing details in the surrounding lab setup flow rather than
  pretending a mock is runnable.
- Emit ONLY the JSON; no prose.
"""


@dataclass
class ToolProposal:
    """Output of :meth:`ToolDesigner.design`."""

    tool: dict[str, Any]
    notes: str
    questions: list[str]
    ready_to_apply: bool
    raw: ClaudeResponse


class ToolDesigner:
    """Free text → proposed Tool YAML dict, with iterative refinement."""

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
    ) -> None:
        self._lab = lab
        self._transport = transport or ClaudeTransport()

    def design(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> ToolProposal:
        user = _describe_tool_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = self._transport.call(_TOOL_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:tool", "tool_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        notes = str(data.pop("notes", "") or "")
        questions = [str(q) for q in data.pop("questions", []) or []]
        ready_to_apply = bool(data.pop("ready_to_apply", not questions))
        return ToolProposal(
            tool=dict(data),
            notes=notes,
            questions=questions,
            ready_to_apply=ready_to_apply,
            raw=resp,
        )

    async def adesign(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> ToolProposal:
        user = _describe_tool_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = await self._transport.acall(_TOOL_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:tool", "tool_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        notes = str(data.pop("notes", "") or "")
        questions = [str(q) for q in data.pop("questions", []) or []]
        ready_to_apply = bool(data.pop("ready_to_apply", not questions))
        return ToolProposal(
            tool=dict(data),
            notes=notes,
            questions=questions,
            ready_to_apply=ready_to_apply,
            raw=resp,
        )


def _describe_tool_context(text: str, lab: Lab | None) -> str:
    lines = [
        "You are the Tool Designer.",
        "",
        "Scientist description (verbatim):",
        text,
        "",
    ]
    if lab is not None:
        resources = lab.resources.list()
        tools = lab.tools.list()
        if resources:
            lines.append("Available resource kinds (pick one):")
            kinds = sorted({r.kind for r in resources})
            for k in kinds:
                lines.append(f"  - {k}")
        if tools:
            lines.append("Already registered tools (avoid duplicating capability names):")
            for t in tools:
                lines.append(f"  - {t.capability} resource={t.resource_kind}")
    return "\n".join(lines)


_WORKFLOW_SYSTEM = """You are the Workflow Designer for an autonomous science lab
framework called autolab. A scientist is describing ONE workflow (a sequence or
small DAG of Operations) they want to register. Propose a single WorkflowTemplate.

Reply with a single compact JSON object:

  {
    "name": "synthesise-and-measure",
    "description": "Sinter a pellet then characterise it.",
    "steps": [
      {
        "step_id": "s1",
        "operation": "sintering",
        "depends_on": [],
        "inputs": {"temperature_k": 1600, "time_h": 4, "atmosphere": "O2"},
        "produces_sample": true,
        "destructive": true
      },
      {
        "step_id": "s2",
        "operation": "xrd",
        "depends_on": ["s1"],
        "inputs": {}
      }
    ],
    "acceptance": {"rules": {"phase_purity": {">=": 0.9}}},
    "notes": "Short rationale"
  }

Rules:
- Use ONLY operations that appear in the `tools` list of the context block.
- Each step_id MUST be unique within the workflow.
- `depends_on` references earlier step_ids; empty = start of the DAG.
- Emit ONLY the JSON; no prose.
"""


@dataclass
class WorkflowProposal:
    """Output of :meth:`WorkflowDesigner.design`."""

    workflow: dict[str, Any]
    notes: str
    raw: ClaudeResponse


class WorkflowDesigner:
    """Free text → proposed WorkflowTemplate, with iterative refinement."""

    def __init__(
        self,
        *,
        lab: Lab | None = None,
        transport: ClaudeTransport | None = None,
    ) -> None:
        self._lab = lab
        self._transport = transport or ClaudeTransport()

    def design(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> WorkflowProposal:
        user = _describe_workflow_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = self._transport.call(_WORKFLOW_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:workflow", "workflow_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        notes = str(data.pop("notes", "") or "")
        return WorkflowProposal(workflow=dict(data), notes=notes, raw=resp)

    async def adesign(
        self,
        text: str,
        *,
        previous: dict[str, Any] | None = None,
        instruction: str | None = None,
    ) -> WorkflowProposal:
        user = _describe_workflow_context(text, self._lab)
        if previous or instruction:
            user = _append_refinement(user, previous, instruction)
        resp = await self._transport.acall(_WORKFLOW_SYSTEM, user)
        if self._lab is not None:
            _persist_claim(self._lab, "designer:workflow", "workflow_designer", user, resp, loose=True)
        data = _safe_json(resp.text) or {}
        notes = str(data.pop("notes", "") or "")
        return WorkflowProposal(workflow=dict(data), notes=notes, raw=resp)


def _describe_workflow_context(text: str, lab: Lab | None) -> str:
    lines = [
        "You are the Workflow Designer.",
        "",
        "Scientist description (verbatim):",
        text,
        "",
    ]
    if lab is not None:
        tools = lab.tools.list()
        resources = lab.resources.list()
        if tools:
            lines.append("Registered tools (available operations):")
            for t in tools:
                lines.append(
                    f"  - {t.capability} (resource={t.resource_kind}) "
                    f"inputs={list(t.inputs.keys()) if t.inputs else []} "
                    f"outputs={list(t.outputs.keys()) if t.outputs else []}"
                )
        if resources:
            lines.append("Registered resources:")
            for r in resources:
                lines.append(f"  - {r.name} kind={r.kind}")
    return "\n".join(lines)


__all__ = [
    "CLAUDE_MODEL_DEFAULT",
    "CampaignDesigner",
    "ClaudePlanner",
    "ClaudePolicyProvider",
    "ClaudeResponse",
    "ClaudeTransport",
    "DesignResult",
    "LabSetupDesigner",
    "LabSetupResult",
    "ResourceDesigner",
    "ResourceProposal",
    "ToolDesigner",
    "ToolProposal",
    "WorkflowDesigner",
    "WorkflowProposal",
    "campaign_from_draft",
    "objective_from",
    "workflow_template_from_draft",
]
