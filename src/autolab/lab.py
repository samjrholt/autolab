"""Lab — the long-running service users register Resources, Tools, Campaigns, and
Workflows against.

Today this is an in-process Python facade so the framework is usable
without the FastAPI/WebSocket layer; the same surface will be the
HTTP/WS layer's view of the Lab when that layer is wired up.

A Lab owns:

- the **Ledger** — append-only, hashed, write-ahead Record store
- a **ResourceManager** — named resource instances with state tracking
- a **ToolRegistry** — capability-named YAML declarations + adapters
  *or* Python-first Operation class registrations
- a **WorkflowRegistry** — named :class:`WorkflowTemplate` instances
- an **Orchestrator** — wraps every Operation in the provenance contract
- a **CampaignScheduler** — runs multiple Campaigns concurrently
- an **EventBus** — every Record write publishes here

Restart-safe: a new ``Lab`` pointed at the same ``root`` rehydrates the
ledger automatically (no in-memory state survives a restart, but every
Record does).

Registration patterns
---------------------

Resources::

    lab.register_resource(Resource(
        name="tube-furnace-A",
        kind="tube_furnace",
        capabilities={"max_temp_k": 1400, "atmosphere": "Ar"},
        asset_id="TF-2024-001",
        typical_operation_durations={"sinter": 7200},
    ))

Operations (Python-first, recommended)::

    lab.register_operation(TubeFurnaceSinter)  # derives schema from class

Operations (YAML, for external adapters)::

    lab.register_tool("path/to/tool.yaml")

Workflows::

    lab.register_workflow(smco5_synthesis_template)

Running a Campaign::

    summary = await lab.run_campaign(campaign, planner)

Running a Workflow directly (without a Planner loop)::

    result = await lab.run_workflow("smco5_synthesis", run, ...)

Resolving escalations::

    lab.resolve_escalation(campaign_id, escalation_id, resolution)
"""

from __future__ import annotations

import importlib.metadata
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from autolab.acceptance import GateVerdict
from autolab.campaign import Campaign, CampaignRunner, CampaignSummary
from autolab.events import EventBus
from autolab.models import (
    Annotation,
    EnvironmentSnapshot,
    EscalationResolution,
    Intervention,
    Record,
    Resource,
    Session,
    WorkflowTemplate,
)
from autolab.operations.base import Operation
from autolab.orchestrator import CampaignRun, Orchestrator
from autolab.planners.base import Planner
from autolab.provenance.store import Ledger
from autolab.resources.manager import ResourceManager
from autolab.tools.registry import ToolDeclaration, ToolRegistry
from autolab.workflow import StepHook, WorkflowEngine, WorkflowResult


def _capture_environment(extra_packages: Iterable[str] = ()) -> EnvironmentSnapshot:
    versions: dict[str, str] = {}
    for pkg in {"autolab", "pydantic", "fastapi", *extra_packages}:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            continue
    return EnvironmentSnapshot(package_versions=versions)


class Lab:
    """In-process Lab service. Persistent state lives in the Ledger."""

    def __init__(
        self,
        root: str | Path,
        *,
        lab_id: str | None = None,
        extra_packages_to_record: Iterable[str] = (),
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lab_id = lab_id or f"lab-{uuid.uuid4().hex[:8]}"
        self.ledger = Ledger(self.root / "ledger")
        self.resources = ResourceManager()
        self.tools = ToolRegistry()
        self.events = EventBus()
        self.orchestrator = Orchestrator(
            ledger=self.ledger,
            resources=self.resources,
            tools=self.tools,
            events=self.events,
        )
        self._workflow_engine = WorkflowEngine(self.orchestrator)
        self._workflows: dict[str, WorkflowTemplate] = {}
        self._extra_packages = tuple(extra_packages_to_record)
        # CampaignRunner registry for escalation resolution.
        self._active_runners: dict[str, CampaignRunner] = {}

    # ------------------------------------------------------------------
    # Resource registration
    # ------------------------------------------------------------------

    def register_resource(self, resource: Resource) -> Resource:
        return self.resources.register(resource)

    def register_resources(self, resources: Iterable[Resource]) -> list[Resource]:
        return [self.register_resource(r) for r in resources]

    # ------------------------------------------------------------------
    # Tool / Operation registration
    # ------------------------------------------------------------------

    def register_operation(self, cls: type[Operation]) -> ToolDeclaration:
        """Register an Operation subclass — derives the full declaration from the class.

        This is the Python-first path: no YAML needed. The class's
        ``capability``, ``resource_kind``, ``requires``, ``Inputs``,
        ``Outputs``, and ``typical_duration`` attributes define the
        declaration. The declaration hash is SHA-256 of the derived schema.

        Example::

            class TubeFurnaceSinter(Operation):
                capability    = "sinter"
                resource_kind = "tube_furnace"
                requires      = {"max_temp_k": {">=": 1300}}
                module        = "sinter.v1.0"
                produces_sample = True
                destructive     = True
                typical_duration = 7200  # seconds

                class Inputs(BaseModel):
                    temp_k: float = Field(..., ge=600, le=1300)
                    time_min: float = Field(..., ge=10, le=480)

                class Outputs(BaseModel):
                    grain_size_nm: float

                async def run(self, inputs, ctx): ...

            lab.register_operation(TubeFurnaceSinter)
        """
        return self.tools.register_class(cls)

    def register_tool(self, path: str | Path) -> ToolDeclaration:
        """Register a YAML tool declaration (for external/legacy adapters)."""
        return self.tools.register_path(path)

    def register_tool_dict(self, raw: dict[str, Any]) -> ToolDeclaration:
        return self.tools.register_dict(raw)

    def register_tools(self, paths: Iterable[str | Path]) -> list[ToolDeclaration]:
        return self.tools.register_paths(paths)

    # ------------------------------------------------------------------
    # Workflow registration
    # ------------------------------------------------------------------

    def register_workflow(self, template: WorkflowTemplate) -> WorkflowTemplate:
        """Register a WorkflowTemplate by name for later execution.

        Example::

            from autolab.models import WorkflowTemplate, WorkflowStep

            smco5 = WorkflowTemplate(
                name="smco5_synthesis",
                steps=[
                    WorkflowStep(step_id="weigh",  operation="weighing"),
                    WorkflowStep(step_id="mill",   operation="milling",  depends_on=["weigh"]),
                    WorkflowStep(step_id="sinter", operation="sintering", depends_on=["mill"]),
                    WorkflowStep(step_id="xrd",    operation="xrd",      depends_on=["sinter"]),
                    WorkflowStep(step_id="mag",    operation="magnetometry", depends_on=["sinter"]),
                ],
            )
            lab.register_workflow(smco5)
        """
        self._workflows[template.name] = template
        return template

    def get_workflow(self, name: str) -> WorkflowTemplate:
        if name not in self._workflows:
            raise KeyError(f"workflow {name!r} not registered")
        return self._workflows[name]

    async def run_workflow(
        self,
        name_or_template: str | WorkflowTemplate,
        run: CampaignRun,
        *,
        input_overrides: dict[str, dict[str, Any]] | None = None,
        decision_overrides: dict[str, dict[str, Any]] | None = None,
        upstream_sample: Any = None,
        max_parallel: int | None = None,
        step_hook: StepHook | None = None,
        max_step_retries: int = 2,
    ) -> WorkflowResult:
        """Execute a registered WorkflowTemplate.

        Pass ``step_hook`` to let a Planner react after each step in the
        DAG — e.g. retry a failed sub-step, stop early, or escalate.
        Without a hook, behaviour is unchanged (failed steps skip their
        dependants silently).
        """
        template = (
            self.get_workflow(name_or_template)
            if isinstance(name_or_template, str)
            else name_or_template
        )
        return await self._workflow_engine.run(
            template,
            run,
            input_overrides=input_overrides,
            decision_overrides=decision_overrides,
            upstream_sample=upstream_sample,
            max_parallel=max_parallel,
            step_hook=step_hook,
            max_step_retries=max_step_retries,
        )

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def new_session(self) -> Session:
        """Mint a fresh Session and persist it + its EnvironmentSnapshot.

        Every Record produced in this session carries its ``session_id``
        so replay can look up the exact environment that ran it.
        """
        session = Session(environment=_capture_environment(self._extra_packages))
        self.ledger._register_session_sync(session)
        return session

    # ------------------------------------------------------------------
    # Campaigns
    # ------------------------------------------------------------------

    def start_campaign(
        self,
        campaign: Campaign,
        planner: Planner,
        *,
        session: Session | None = None,
    ) -> CampaignRunner:
        """Build a :class:`CampaignRunner` (does not start it)."""
        session = session or self.new_session()
        runner = CampaignRunner(
            campaign=campaign,
            planner=planner,
            lab=self,
            session=session,
        )
        self._active_runners[campaign.id] = runner
        return runner

    async def run_campaign(
        self,
        campaign: Campaign,
        planner: Planner,
        *,
        session: Session | None = None,
    ) -> CampaignSummary:
        """Build and run a Campaign end-to-end, returning its summary."""
        runner = self.start_campaign(campaign, planner, session=session)
        try:
            return await runner.run()
        finally:
            self._active_runners.pop(campaign.id, None)

    # ------------------------------------------------------------------
    # Escalation resolution
    # ------------------------------------------------------------------

    def resolve_escalation(
        self,
        campaign_id: str,
        escalation_id: str,
        resolution: EscalationResolution,
    ) -> None:
        """Resolve a parked escalation and resume the Campaign.

        Raises ``KeyError`` if the campaign is not currently running or if
        the escalation id is unknown.
        """
        runner = self._active_runners.get(campaign_id)
        if runner is None:
            raise KeyError(f"campaign {campaign_id!r} is not currently active in this Lab")
        runner.resolve_escalation(escalation_id, resolution)

    def pending_escalations(self, campaign_id: str) -> list[Any]:
        """Return unresolved escalations for a running Campaign."""
        runner = self._active_runners.get(campaign_id)
        if runner is None:
            return []
        return runner.pending_escalations()

    # ------------------------------------------------------------------
    # Direct provenance surface
    # ------------------------------------------------------------------

    async def annotate(self, annotation: Annotation) -> Annotation:
        return await self.ledger.annotate(annotation)

    async def record_intervention(self, intervention: Intervention) -> Record:
        """Persist a human Intervention as its own append-only Record."""
        session = self.new_session()
        record = Record(
            lab_id=self.lab_id,
            campaign_id=intervention.campaign_id,
            session_id=session.id,
            operation="human.intervention",
            module="human.v0",
            inputs={"body": intervention.body, "payload": dict(intervention.payload)},
            decision={"author": intervention.author},
            record_status="completed",
            tags=["intervention", "human"],
        )
        return await self.ledger.append(record)

    def records(self, **filters: Any) -> list[Record]:
        return list(self.ledger.iter_records(**filters))

    def verify_ledger(self) -> list[str]:
        return self.ledger.verify_all()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self.ledger.close()

    def __enter__(self) -> Lab:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


__all__ = ["GateVerdict", "Lab"]
