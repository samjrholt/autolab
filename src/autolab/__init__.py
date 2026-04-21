"""autolab — a scientific record with an agent attached.

A closed-loop, resource-aware, provenance-first framework for autonomous science.

Core model
----------

.. code-block:: text

    Lab (service)
    ├── ResourceManager — instruments with state-machine awareness
    ├── ToolRegistry    — Python-first or YAML capability declarations
    ├── WorkflowEngine  — DAG execution of WorkflowTemplates
    ├── Orchestrator    — sole writer of Records (provenance contract)
    ├── CampaignScheduler — multi-campaign priority queue
    └── Ledger          — append-only, hashed, dual-write SQLite + JSONL

See ``CLAUDE.md`` at the repo root and ``docs/design/`` for the full
design contract.
"""

from __future__ import annotations

from autolab.acceptance import GateDetail, GateVerdict, evaluate
from autolab.campaign import Campaign, CampaignRunner, CampaignSummary
from autolab.lab import Lab
from autolab.models import (
    AcceptanceCriteria,
    Action,
    ActionType,
    Annotation,
    Direction,
    EnvironmentSnapshot,
    Escalation,
    EscalationActionType,
    EscalationResolution,
    FailureMode,
    Feature,
    FeatureView,
    Intervention,
    Objective,
    OperationResult,
    OutcomeClass,
    ProposedStep,
    Record,
    Resource,
    ResourceState,
    Sample,
    Session,
    WorkflowStep,
    WorkflowTemplate,
)
from autolab.operations.base import Operation, OperationContext
from autolab.planners.base import (
    DecisionContext,
    HeuristicPolicyProvider,
    PlanContext,
    Planner,
    PolicyProvider,
)
from autolab.scheduler import CampaignScheduler, CampaignState, CampaignStatus
from autolab.workflow import StepResult, WorkflowEngine, WorkflowResult

__version__ = "0.0.1"

__all__ = [
    # Acceptance
    "AcceptanceCriteria",
    "GateDetail",
    "GateVerdict",
    "evaluate",
    # Actions
    "Action",
    "ActionType",
    # Campaign
    "Campaign",
    "CampaignRunner",
    "CampaignScheduler",
    "CampaignState",
    "CampaignStatus",
    "CampaignSummary",
    # Context / Planner
    "DecisionContext",
    "HeuristicPolicyProvider",
    "PlanContext",
    "Planner",
    "PolicyProvider",
    # Escalation
    "Escalation",
    "EscalationActionType",
    "EscalationResolution",
    # Lab
    "Lab",
    # Models
    "Annotation",
    "Direction",
    "EnvironmentSnapshot",
    "FailureMode",
    "Feature",
    "FeatureView",
    "Intervention",
    "Objective",
    "OperationResult",
    "OutcomeClass",
    "ProposedStep",
    "Record",
    "Resource",
    "ResourceState",
    "Sample",
    "Session",
    # Operations
    "Operation",
    "OperationContext",
    # Workflow
    "StepResult",
    "WorkflowEngine",
    "WorkflowResult",
    "WorkflowStep",
    "WorkflowTemplate",
]
