"""Core problem-agnostic data model.

Every term here matches [docs/design/GLOSSARY.md](../../docs/design/GLOSSARY.md).
No domain knowledge of magnetism, catalysis, or any vertical lives in this module.

Design invariants
-----------------

1. **Failure is not binary.** :data:`FailureMode` distinguishes *why* something
   stopped. An instrument crash is not the same as a synthesis that yielded an
   unexpected phase — the former is retried; the latter is a discovery worth
   exploring. :data:`OutcomeClass` captures what *kind* of result a completed
   Record represents, separate from whether the acceptance criteria passed.

2. **Equipment has state.** A furnace is not "free" or "busy" — it may be
   cooling, calibrating, or in maintenance. :class:`ResourceState` gives the
   scheduler enough information to build a Gantt and estimate wait times.

3. **Workflows are first-class.** :class:`WorkflowTemplate` + :class:`WorkflowStep`
   describe reusable DAGs of Operations with typed input wiring. They encode
   the lab's standard operating procedures, not just ad-hoc step lists.

4. **Escalations are records.** A human decision that unblocks a running
   Campaign is an :class:`Escalation` with a hashed :class:`EscalationResolution`
   stored in the ledger — the audit trail covers every intervention.
"""

from __future__ import annotations

import platform
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Resource model — static definition + calibration linkage
# ---------------------------------------------------------------------------


class ResourceState(str, Enum):
    """Runtime state of a physical or computational instrument.

    The scheduler uses this to determine whether an instrument can accept
    a new Operation immediately, needs to wait (e.g., cooling after a
    high-temperature run), or requires human intervention before use.
    """

    IDLE = "idle"
    BUSY = "busy"
    COOLING = "cooling"  # physically unavailable but recovering automatically
    WARMING = "warming"
    CALIBRATING = "calibrating"  # running a calibration procedure
    ERROR = "error"  # requires human intervention to clear
    MAINTENANCE = "maintenance"  # scheduled downtime


class Resource(BaseModel):
    """A named, capacity-limited capability instance.

    ``kind`` is the type string an Operation declares (e.g. ``computer``,
    ``arc_furnace``, ``slurm``). ``capabilities`` is a free-form dict the
    scheduler matches against an Operation's ``requires``.

    Static metadata
    ---------------
    ``asset_id``
        Manufacturer serial number or institutional asset tag. Stamped into
        every Record the instrument produces so measurements can be traced
        back to the exact instrument (useful when two furnaces of the same
        kind give different results).

    ``typical_operation_durations``
        ``{capability_name: seconds}`` — best-guess operation durations used
        by the scheduler to estimate queue wait times and build Gantt charts.
        Not enforced; the actual duration is measured and stored in the Record.

    ``last_calibration_record_id``
        ID of the most recent calibration Record in the ledger.  Updated by
        the Lab every time a calibration Operation completes.  Provides the
        chain of custody: sample → instrument → calibration Record → reference
        standard.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    capabilities: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    asset_id: str | None = None
    typical_operation_durations: dict[str, int] = Field(default_factory=dict)
    last_calibration_record_id: str | None = None


# ---------------------------------------------------------------------------
# Sample model
# ---------------------------------------------------------------------------


class Sample(BaseModel):
    """The thing — physical or digital — Operations transform.

    Minted by Operations declared ``produces_sample=True``. Downstream
    Operations inherit ``parent_sample_ids`` until a new Sample is minted.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: _new_id("sam"))
    created_at: datetime = Field(default_factory=_utc_now)
    parent_sample_ids: list[str] = Field(default_factory=list)
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Action vocabulary (closed set; see GLOSSARY.md)
# ---------------------------------------------------------------------------


class ActionType(str, Enum):
    CONTINUE = "continue"
    ACCEPT = "accept"
    STOP = "stop"
    ADD_STEP = "add_step"
    RETRY_STEP = "retry_step"
    REPLAN = "replan"
    ESCALATE = "escalate"
    BRANCH = "branch"
    ASK_HUMAN = "ask_human"


class Action(BaseModel):
    """A reactive decision returned by a Planner's react()."""

    model_config = ConfigDict(extra="forbid")

    type: ActionType
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Objective — what a Campaign is searching for
# ---------------------------------------------------------------------------


Direction = Literal["maximise", "minimise"]


class Objective(BaseModel):
    """The scalar figure of merit a Campaign drives toward.

    ``key`` is the output field on the completed Record (for example
    ``"sensitivity"`` or ``"Hc_kA_per_m"``). ``direction`` tells the
    Planner whether to seek high or low values.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    direction: Direction = "maximise"
    target: float | None = None
    unit: str | None = None


# ---------------------------------------------------------------------------
# AcceptanceCriteria — dict-of-rules
# ---------------------------------------------------------------------------


GateResult = Literal["pass", "soft_fail", "fail"]


class AcceptanceCriteria(BaseModel):
    """Rule set: ``{output_key: {operator: threshold, ...}, ...}``.

    Supported operators: ``>=``, ``<=``, ``>``, ``<``, ``==``, ``in``,
    ``not_in``.
    """

    model_config = ConfigDict(extra="forbid")

    rules: dict[str, dict[str, Any]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Failure taxonomy — why something stopped / what kind of result it was
# ---------------------------------------------------------------------------


FailureMode = Literal[
    "equipment_failure",  # instrument did not execute — retry is safe
    "process_deviation",  # instrument ran but process conditions drifted
    "measurement_rejection",  # measurement ran but QC deems data unreliable
    "synthesis_deviation",  # ran correctly; product differs from intended
]
"""Why a Record failed or deviated.

``equipment_failure``
    The instrument itself crashed or could not complete the operation
    (power outage, communication error, hardware fault). The sample is
    *unchanged*. Retry is safe.

``process_deviation``
    The instrument ran but the operating conditions drifted during the run
    (e.g., temperature controller failed partway through sintering, gas
    flow was interrupted). The sample's state is uncertain. A human should
    review before retrying.

``measurement_rejection``
    The measurement ran, but QC analysis indicates the data is unreliable
    (weak signal, contaminated sample holder, reference material out of
    spec). The sample is intact. Retry the measurement, not the synthesis.

``synthesis_deviation``
    Everything ran correctly, but the product differs from the intended
    target (wrong phase, unexpected composition). This is *not* a failure
    in the engineering sense — it is a discovery. The Planner should
    consider exploring this branch rather than retrying.
"""

OutcomeClass = Literal[
    "on_target",  # completed, result matches expectation / gate passed
    "off_target",  # completed, result differs from target — scientifically interesting
    "exceptional",  # completed, result significantly exceeds / surprises expectations
]
"""What kind of result a *completed* Record represents.

Orthogonal to ``gate_result``: a gate can fail (acceptance criteria not
met) while the outcome class is ``"off_target"`` rather than a failure.
This distinction is what lets the Planner decide *explore this unexpected
result* vs *mark as failure and retry*.
"""


# ---------------------------------------------------------------------------
# FeatureView — typed, ML-ready view of an Operation's outputs
# ---------------------------------------------------------------------------


FeatureKind = Literal["scalar", "curve", "image", "spectrum", "pointer"]


class Feature(BaseModel):
    """One typed output field on an Operation result."""

    model_config = ConfigDict(extra="allow")

    kind: FeatureKind
    value: Any
    unit: str | None = None


class FeatureView(BaseModel):
    """A bundle of typed Features keyed by name."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, Feature] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# OperationResult — what an Operation.run() returns
# ---------------------------------------------------------------------------


OperationStatus = Literal["completed", "failed", "soft_fail"]


class OperationResult(BaseModel):
    """The structured return value of ``Operation.run()``.

    The orchestrator wraps Operations and persists this as part of the
    Record — Operations never write Records themselves.

    ``failure_mode``
        If the Operation sets this on a non-``completed`` result, the
        Orchestrator stamps it onto the Record. This lets the Operation
        signal "the instrument failed" (``equipment_failure``) vs "the
        process went wrong" (``process_deviation``).

    ``outcome_class``
        If the Operation sets this on a ``completed`` result, the
        Orchestrator stamps it. Useful when an Operation can self-diagnose
        that it produced an unexpected but valid result.
    """

    model_config = ConfigDict(extra="forbid")

    status: OperationStatus = "completed"
    outputs: dict[str, Any] = Field(default_factory=dict)
    features: FeatureView = Field(default_factory=FeatureView)
    error: str | None = None
    new_sample: Sample | None = None
    artefacts: dict[str, str] = Field(default_factory=dict)
    failure_mode: FailureMode | None = None
    outcome_class: OutcomeClass | None = None


# ---------------------------------------------------------------------------
# Environment + Session
# ---------------------------------------------------------------------------


class EnvironmentSnapshot(BaseModel):
    """Reproducibility metadata captured per Session."""

    model_config = ConfigDict(extra="allow")

    python_version: str = Field(default_factory=lambda: sys.version.split()[0])
    platform: str = Field(default_factory=lambda: platform.platform())
    hostname: str = Field(default_factory=lambda: platform.node())
    schema_version: str = SCHEMA_VERSION
    package_versions: dict[str, str] = Field(default_factory=dict)
    git_commit: str | None = None
    seeds: dict[str, int] = Field(default_factory=dict)


class Session(BaseModel):
    """One execution context that produces Records."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: _new_id("ses"))
    started_at: datetime = Field(default_factory=_utc_now)
    environment: EnvironmentSnapshot = Field(default_factory=EnvironmentSnapshot)


# ---------------------------------------------------------------------------
# ProposedStep — Planner.plan() output
# ---------------------------------------------------------------------------


class ProposedStep(BaseModel):
    """One Operation a Planner proposes the orchestrator should run."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: _new_id("prop"))
    operation: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)
    experiment_id: str | None = None
    decision: dict[str, Any] = Field(default_factory=dict)
    acceptance: AcceptanceCriteria | None = None


# ---------------------------------------------------------------------------
# Annotation — append-only addition to a Record
# ---------------------------------------------------------------------------


AnnotationKind = Literal["note", "correction", "retraction", "qc_verdict", "claim"]


class Annotation(BaseModel):
    """Post-hoc append-only addition to an existing Record."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: _new_id("ann"))
    target_record_id: str
    kind: AnnotationKind
    body: dict[str, Any] = Field(default_factory=dict)
    author: str = "system"
    created_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Record — the unit of the ledger
# ---------------------------------------------------------------------------


RecordStatus = Literal[
    "proposed",
    "pending",
    "running",
    "completed",
    "failed",
    "soft_fail",
    "paused",
]


class Record(BaseModel):
    """Append-only ledger unit — see ideas-foundation §7."""

    model_config = ConfigDict(extra="allow")

    # Identity
    id: str = Field(default_factory=lambda: _new_id("rec"))
    schema_version: str = SCHEMA_VERSION
    created_at: datetime = Field(default_factory=_utc_now)
    finalised_at: datetime | None = None

    # Scope
    lab_id: str
    campaign_id: str | None = None
    experiment_id: str | None = None
    session_id: str

    # What ran
    operation: str
    module: str | None = None
    tool_declaration_hash: str | None = None
    skill_hashes: list[str] = Field(default_factory=list)

    # Lineage
    parent_ids: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)
    sample_id: str | None = None
    parent_sample_ids: list[str] = Field(default_factory=list)

    # Resource
    resource_kind: str | None = None
    resource_name: str | None = None
    resource_asset_id: str | None = None  # stamped from Resource.asset_id

    # Lifecycle
    record_status: RecordStatus = "pending"
    duration_ms: int | None = None

    # Outcome
    outputs: dict[str, Any] = Field(default_factory=dict)
    features: FeatureView | None = None
    error: str | None = None

    # Failure taxonomy — orthogonal to record_status
    failure_mode: FailureMode | None = None
    outcome_class: OutcomeClass | None = None

    # Decision
    decision: dict[str, Any] = Field(default_factory=dict)

    # Quality
    qc: list[dict[str, Any]] = Field(default_factory=list)
    decision_grade: bool | None = None
    gate_result: GateResult | None = None

    # Flex
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Integrity
    checksum: str | None = None


# ---------------------------------------------------------------------------
# WorkflowStep + WorkflowTemplate — reusable DAG of Operations
# ---------------------------------------------------------------------------


class WorkflowStep(BaseModel):
    """One node in a :class:`WorkflowTemplate` DAG.

    ``depends_on``
        List of ``WorkflowStep.step_id`` values that must reach
        ``completed`` or ``soft_fail`` status before this step is eligible
        to run. Steps with no dependencies run immediately.

    ``input_mappings``
        Wire the outputs of an upstream step into this step's inputs::

            {"temp_k": "sinter.grain_size_nm"}

        means ``inputs["temp_k"] = outputs["grain_size_nm"]`` from the
        step with ``step_id="sinter"``. Overridden by ``inputs`` if the
        same key appears in both.

    ``branch_id``
        Optional tag grouping parallel branches for visualisation. Steps
        sharing a ``branch_id`` are in the same logical branch of the DAG.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    operation: str
    depends_on: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_mappings: dict[str, str] = Field(default_factory=dict)
    produces_sample: bool = False
    destructive: bool = False
    branch_id: str | None = None
    acceptance: AcceptanceCriteria | None = None


class WorkflowTemplate(BaseModel):
    """A reusable DAG of :class:`WorkflowStep` nodes.

    A WorkflowTemplate encodes a standard operating procedure — the
    sequence (or parallel graph) of Operations needed to run a class of
    experiment. It is registered once with the Lab and can be instantiated
    many times, each instance running in its own Campaign.

    Examples
    --------
    >>> from autolab.models import WorkflowTemplate, WorkflowStep
    >>> smco5_synthesis = WorkflowTemplate(
    ...     name="smco5_synthesis",
    ...     description="Sm-Co permanent magnet synthesis route",
    ...     steps=[
    ...         WorkflowStep(step_id="weigh",    operation="weighing"),
    ...         WorkflowStep(step_id="mill",     operation="milling",     depends_on=["weigh"]),
    ...         WorkflowStep(step_id="sinter",   operation="sintering",   depends_on=["mill"]),
    ...         WorkflowStep(step_id="xrd",      operation="xrd",         depends_on=["sinter"]),
    ...         WorkflowStep(step_id="mag",      operation="magnetometry", depends_on=["sinter"]),
    ...     ],
    ... )
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: _new_id("wfl"))
    name: str
    description: str | None = None
    steps: list[WorkflowStep]
    acceptance: AcceptanceCriteria | None = None
    typical_duration_s: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Escalation — human-in-loop decision that parks a running Campaign
# ---------------------------------------------------------------------------


class Escalation(BaseModel):
    """A pending decision that requires human input before a Campaign can proceed.

    When a :class:`~autolab.planners.base.PolicyProvider` returns
    ``ActionType.ESCALATE``, the :class:`~autolab.campaign.CampaignRunner`
    parks the current step, mints an :class:`Escalation`, and waits.
    The scientist resolves it via ``lab.resolve_escalation(id, resolution)``
    or the HTTP surface ``POST /escalations/{id}/resolve``.

    The escalation and its resolution are both written as Records to the
    ledger so the audit trail is complete.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: _new_id("esc"))
    campaign_id: str
    record_id: str  # the Record that triggered the escalation
    reason: str
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    resolved_at: datetime | None = None


EscalationActionType = Literal["continue", "retry", "stop", "add_step"]


class EscalationResolution(BaseModel):
    """A human's response to an :class:`Escalation`.

    ``action``
        What the Campaign should do next:

        - ``continue`` — proceed to the next planned step as normal.
        - ``retry`` — re-run the step that triggered the escalation,
          optionally with ``retry_inputs`` overrides.
        - ``stop`` — terminate the Campaign gracefully.
        - ``add_step`` — insert an extra step (described in ``extra_step``)
          before continuing.

    ``reason``
        Human explanation, stored in the ledger.
    """

    model_config = ConfigDict(extra="forbid")

    escalation_id: str
    action: EscalationActionType
    reason: str
    retry_inputs: dict[str, Any] = Field(default_factory=dict)
    extra_step: ProposedStep | None = None
    resolved_by: str = "human"


# ---------------------------------------------------------------------------
# Intervention — human action (also recorded as a Record)
# ---------------------------------------------------------------------------


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: _new_id("int"))
    campaign_id: str | None = None
    body: str
    author: str = "human"
    created_at: datetime = Field(default_factory=_utc_now)
    payload: Mapping[str, Any] = Field(default_factory=dict)


__all__ = [
    "SCHEMA_VERSION",
    "AcceptanceCriteria",
    "Action",
    "ActionType",
    "Annotation",
    "AnnotationKind",
    "Direction",
    "EnvironmentSnapshot",
    "Escalation",
    "EscalationActionType",
    "EscalationResolution",
    "FailureMode",
    "Feature",
    "FeatureKind",
    "FeatureView",
    "GateResult",
    "Intervention",
    "Objective",
    "OperationResult",
    "OperationStatus",
    "OutcomeClass",
    "ProposedStep",
    "Record",
    "RecordStatus",
    "Resource",
    "ResourceState",
    "Sample",
    "Session",
    "WorkflowStep",
    "WorkflowTemplate",
]
