"""FastAPI + WebSocket surface for the Lab service.

Usage::

    uvicorn autolab.server.app:app --reload --port 8000

Or via the pixi task::

    pixi run serve

Design
------

- One FastAPI process owns one :class:`~autolab.Lab` in
  ``app.state.lab`` and one :class:`~autolab.CampaignScheduler` in
  ``app.state.scheduler``.  The scheduler's ``run()`` task is launched
  as a background coroutine at startup.
- The Lab's :class:`~autolab.events.EventBus` is bridged to every
  connected WebSocket.  Every Record lifecycle transition, every
  Campaign start/finish, every escalation fans out as one JSON message
  on ``/events``.
- REST handlers mutate the Lab through its own methods; they never
  touch the ledger directly.  This keeps the "Operations never write
  Records" invariant intact.
- The Console is a built frontend bundle served at ``/`` from
    ``src/autolab/server/static``. The source lives in ``frontend/`` and
    can be rebuilt without changing the FastAPI contract.

Persistence
-----------

The ``AUTOLAB_ROOT`` env var (default ``./.autolab-runs/default``)
points at the directory the Ledger writes into.  Restart-safe by
construction — a new process pointed at the same directory rehydrates
from SQLite.

Test bootstrap
--------------

``AUTOLAB_BOOTSTRAP`` env var (default ``"mammos"``) selects a bootstrap
bundle. ``"mammos"`` (default) is the MVP demo — the 6-step MaMMoS
sensor demonstrator (composition → relaxed structure → intrinsic
magnetic parameters → finite-T parameters → sensor mesh → hysteresis
loop → figure of merit) running real ``mammos-*`` / ``ubermag`` /
``OOMMF`` backends inside a separate WSL pixi environment. See
``examples/mammos_sensor/README.md`` for WSL setup; the VM resource
is probed on boot and its capabilities reflect which backends are
installed. Other modes: ``"demo_quadratic"`` (trivial stub),
``"superellipse"`` (older single-stage sensor example), ``"all"``
(registers superellipse + mammos), ``"shell_command"`` (local
subprocess backend), ``"add_demo"`` / ``"wsl_demo"`` /
``"wsl_ssh_demo"`` (older toy examples), ``"none"`` (boot empty),
or any ``module:function`` dotted path called with the Lab as its
only argument.

Regardless of mode, every Lab boots with one default resource:
``local-computer`` - the host running autolab - auto-registered before the mode runs.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import sys
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from autolab import query
from autolab.acceptance import evaluate as evaluate_gate
from autolab.agents.claude import (
    CampaignDesigner,
    ClaudePlanner,
    ClaudePolicyProvider,
    ClaudeTransport,
    LabSetupDesigner,
    ResourceDesigner,
    ToolDesigner,
    WorkflowDesigner,
    drain_pending_claims,
)
from autolab.agents.claude import _safe_json as _safe_claude_json
from autolab.campaign import Campaign
from autolab.estimation import EstimationEngine
from autolab.events import Event, EventBus
from autolab.lab import Lab
from autolab.models import (
    AcceptanceCriteria,
    Annotation,
    EscalationResolution,
    Intervention,
    Objective,
    OperationResult,
    ProposedStep,
    Resource,
    WorkflowStep,
    WorkflowTemplate,
)
from autolab.planners.base import Planner
from autolab.planners.registry import build as build_planner
from autolab.planners.registry import list_planners
from autolab.scheduler import CampaignScheduler

log = logging.getLogger("autolab.server")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ResourceRequest(BaseModel):
    name: str
    kind: str | None = None
    backend: str | None = None
    connection: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    asset_id: str | None = None
    typical_operation_durations: dict[str, int] = Field(default_factory=dict)
    host: str | None = None
    user: str | None = None
    port: int | None = None
    remote_root: str | None = None
    working_dir: str | None = None


class WorkflowRequest(BaseModel):
    name: str
    description: str | None = None
    steps: list[dict[str, Any]]
    acceptance: dict[str, Any] | None = None
    typical_duration_s: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignRequest(BaseModel):
    name: str
    description: str | None = None
    objective: dict[str, Any]
    acceptance: dict[str, Any] | None = None
    budget: int | None = 16
    parallelism: int = 1
    priority: int = 50
    planner: str = "heuristic"  # "heuristic", "bo", "optuna", "claude", or a custom factory name
    planner_config: dict[str, Any] = Field(default_factory=dict)
    use_claude_policy: bool = False
    # Optional inline workflow for workflow-backed campaigns. The planner
    # proposes the tunable step; CampaignRunner executes the full DAG.
    workflow: dict[str, Any] | None = None
    # When False, the campaign is registered in "queued" state but no task
    # is launched. The caller (typically the Console) starts it later via
    # POST /campaigns/{id}/start. Default True preserves the existing
    # one-click-submit behaviour.
    autostart: bool = True


class EscalationResolutionRequest(BaseModel):
    action: str
    reason: str
    retry_inputs: dict[str, Any] = Field(default_factory=dict)
    extra_step: dict[str, Any] | None = None


class AnnotationRequest(BaseModel):
    note: str
    tags: list[str] = Field(default_factory=list)
    author: str = "human"


class InterventionRequest(BaseModel):
    body: str
    author: str = "human"
    payload: dict[str, Any] = Field(default_factory=dict)


class DesignRequest(BaseModel):
    text: str
    previous: dict[str, Any] | None = None
    instruction: str | None = None


class AnalysisRequest(BaseModel):
    prompt: str
    campaign_ids: list[str] | None = None
    limit: int = Field(default=500, ge=1, le=5000)


class LabSetupRequest(BaseModel):
    text: str
    previous: dict[str, Any] | None = None
    instruction: str | None = None


class LabSetupApplyRequest(BaseModel):
    resources: list[dict[str, Any]] = Field(default_factory=list)
    operations: list[dict[str, Any]] = Field(default_factory=list)
    workflow: dict[str, Any] | None = None


class BootstrapApplyRequest(BaseModel):
    mode: str


class EntityDesignRequest(BaseModel):
    """Iterative-refinement request for per-entity designers (resource / tool / workflow)."""

    text: str = ""
    previous: dict[str, Any] | None = None
    instruction: str | None = None


class CapabilitySmokeTestRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(_json_safe(message))
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)


def _json_safe(msg: Any) -> Any:
    """Round-trip through orjson to coerce datetimes / sets etc."""
    return json.loads(json.dumps(msg, default=str))


# ---------------------------------------------------------------------------
# Bootstrap: demo stub so the UI has something to show immediately.
# ---------------------------------------------------------------------------


def _bootstrap_superellipse(lab: Lab) -> None:
    """Real-physics bootstrap: the superellipse-sensor example.

    Registers one `computer` Resource and the `superellipse_hysteresis`
    capability.  The adapter uses a surrogate when ubermag is not
    installed (the default) — the Record's `module` field says which
    backend actually ran.  Provenance-visible, not silent.
    """
    import sys
    from pathlib import Path as _Path

    from autolab.models import Resource as _Resource

    # `examples/` lives at the repo root, not inside the installed `autolab`
    # package. Make it importable so the Tool YAML's adapter path resolves.
    repo_root = _Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    if not any(r.name == "pc-1" for r in lab.resources.list()):
        lab.register_resource(
            _Resource(
                name="pc-1",
                kind="computer",
                capabilities={"cores_gte": 1, "has_oommf": False},
                description="Local workstation — runs the superellipse surrogate.",
                typical_operation_durations={"superellipse_hysteresis": 4},
            )
        )
    if not lab.tools.has("superellipse_hysteresis"):
        # The YAML declaration lives in the example directory; we register
        # it against the running Lab so provenance sees the same hash the
        # CLI-driven run would produce.
        yaml_path = (
            _Path(__file__).resolve().parents[3] / "examples" / "superellipse_sensor" / "tool.yaml"
        )
        lab.register_tool(yaml_path)


def _bootstrap_mammos(lab: Lab) -> None:
    """Full MaMMoS demonstrator — 6 Operations + Workflow + VM resource."""
    import sys
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from examples.mammos_sensor.server_bootstrap import bootstrap as _mammos_boot

    _mammos_boot(lab)


def _bootstrap_demo_quadratic(lab: Lab) -> None:
    """Trivial stub Operation. Opt-in only — not wired into the default Console
    viz routing. Use for clicking around when the real adapters are unavailable.
    """
    from pydantic import BaseModel as PydanticBaseModel

    from autolab.models import Resource as _Resource
    from autolab.operations.base import Operation

    class DemoQuadratic(Operation):
        capability = "demo_quadratic"
        resource_kind = "computer"
        module = "demo_quadratic.v1"
        typical_duration = 2

        class Inputs(PydanticBaseModel):
            x: float
            target: float = 0.5

        class Outputs(PydanticBaseModel):
            score: float

        async def run(self, inputs: dict[str, Any]) -> OperationResult:
            import random

            await asyncio.sleep(0.4 + random.random() * 0.6)
            x = float(inputs.get("x", 0.0))
            target = float(inputs.get("target", 0.5))
            score = -((x - target) ** 2) + 1.0
            return OperationResult(
                status="completed",
                outputs={"score": score, "x": x},
            )

    if not any(r.name == "pc-1" for r in lab.resources.list()):
        lab.register_resource(
            _Resource(
                name="pc-1",
                kind="computer",
                capabilities={"cores_gte": 4},
                description="Local workstation (stub tool).",
                typical_operation_durations={"demo_quadratic": 2},
            )
        )
    if not lab.tools.has("demo_quadratic"):
        lab.register_operation(DemoQuadratic)


def _bootstrap_shell_command(lab: Lab) -> None:
    """Register the ``shell_command`` Capability + a ``local`` Resource.

    Gives the user a full round-trip — write-ahead record, remote workdir
    open/run/fetch, record finalisation — without any external deps. The
    demo Workflow runs ``echo hostname && uname -a`` and collects the
    stdout into a Record, exercising the same RemoteWorkdir lifecycle a
    real ssh_exec run would use.
    """
    from autolab.models import Resource as _Resource
    from autolab.tools.adapters.shell_command import ShellCommand

    if not any(r.kind == "local" for r in lab.resources.list()):
        lab.register_resource(
            _Resource(
                name="local-worker",
                kind="local",
                capabilities={"backend": "local", "has_shell": True},
                description="Local subprocess backend — runs any shell_command Operation.",
                typical_operation_durations={"shell_command": 1},
            )
        )
    if not lab.tools.has("shell_command"):
        lab.register_operation(ShellCommand)


def _register_annotation_extract(lab: Lab) -> None:
    """Register the `annotation_extract` Interpretation Op and wire
    the Lab + ClaudeTransport into its OperationContext via a pre-hook.
    Idempotent — safe to call on every bootstrap.
    """
    from autolab.agents.claude import ClaudeTransport
    from autolab.operations.interpretation import AnnotationExtract

    if lab.tools.has("annotation_extract"):
        return
    lab.register_operation(AnnotationExtract)
    transport = ClaudeTransport()

    async def _inject(ctx: Any, _state: Any) -> None:
        if ctx.operation == "annotation_extract":
            ctx.metadata.setdefault("lab", lab)
            ctx.metadata.setdefault("claude", transport)

    lab.orchestrator.add_pre_hook(_inject)


def _ensure_repo_on_path() -> None:
    """Add the repo root to sys.path so that `examples.*` is always importable.

    When the server is launched via `pixi run serve` the working directory is
    the repo root, but it may not be on sys.path.  Adding it here means
    AUTOLAB_BOOTSTRAP=add_demo (and any dotted-path bootstrap) works without
    requiring the caller to set PYTHONPATH manually.
    """
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def _set_bootstrap_diagnostics(lab: Lab, *, mode: str, error: str | None = None) -> None:
    lab._bootstrap_diagnostics = {  # type: ignore[attr-defined]
        "mode": mode,
        "error": error,
    }


def _apply_bootstrap_mode(lab: Lab, mode: str) -> None:
    _set_bootstrap_diagnostics(lab, mode=mode)
    log.info(
        "bootstrap mode: %r  (cwd=%s, sys.path[0]=%s)",
        mode,
        Path.cwd(),
        sys.path[0] if sys.path else "(empty)",
    )
    if mode in ("none", ""):
        # No default capabilities, no default workflows. "local-computer" is the only
        # default resource and is registered by _auto_register_this_pc()
        # before this function runs. Demos register their own entities
        # on top via POST /bootstraps/apply — and they do it narrowly, so
        # they don't pollute the Lab with capabilities they don't use.
        return
    # No automatic annotation_extract registration. Bootstraps that need it
    # opt in by calling _register_annotation_extract(lab) from their body.
    if mode == "superellipse":
        try:
            _bootstrap_superellipse(lab)
            return
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            log.warning("superellipse bootstrap failed (%s) — falling back to empty", exc)
            return
    if mode == "mammos":
        try:
            _bootstrap_mammos(lab)
            return
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            log.warning("mammos bootstrap failed (%s) — falling back to empty", exc)
            return
    if mode == "sensor_shape_opt":
        try:
            from examples.mammos_sensor.sensor_shape_opt_bootstrap import (
                bootstrap as _sensor_shape_boot,
            )

            _sensor_shape_boot(lab)
            log.info(
                "sensor_shape_opt bootstrap OK — tools=%s workflows=%s",
                [d.capability for d in lab.tools.list()],
                list(lab._workflows.keys()),
            )
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            import traceback as _tb

            log.error("sensor_shape_opt bootstrap FAILED — %s\n%s", exc, _tb.format_exc())
        return
    if mode == "all":
        # Register both example bundles so the Console can run either.
        for name, fn in (("superellipse", _bootstrap_superellipse), ("mammos", _bootstrap_mammos)):
            try:
                fn(lab)
            except Exception as exc:
                log.warning("%s bootstrap failed (%s)", name, exc)
        return
    if mode == "demo_quadratic":
        _bootstrap_demo_quadratic(lab)
        return
    if mode == "shell_command":
        _bootstrap_shell_command(lab)
        return
    if mode == "add_demo":
        try:
            from examples.add_demo.bootstrap import bootstrap as _add_demo_boot

            _add_demo_boot(lab)
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            log.warning("add_demo bootstrap failed (%s)", exc)
        return
    if mode == "wsl_ssh_demo":
        try:
            from examples.wsl_ssh_demo.bootstrap import bootstrap as _wsl_ssh_boot

            _wsl_ssh_boot(lab)
            log.info(
                "wsl_ssh_demo bootstrap OK — resources=%s tools=%s workflows=%s",
                [r.name for r in lab.resources.list()],
                [d.capability for d in lab.tools.list()],
                list(lab._workflows.keys()),
            )
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            import traceback as _tb

            log.error("wsl_ssh_demo bootstrap FAILED — %s\n%s", exc, _tb.format_exc())
        return
    if mode == "wsl_demo":
        try:
            from examples.wsl_demo.bootstrap import bootstrap as _wsl_demo_boot

            _wsl_demo_boot(lab)
            log.info(
                "wsl_demo bootstrap OK — resources=%s tools=%s workflows=%s",
                [r.name for r in lab.resources.list()],
                [d.capability for d in lab.tools.list()],
                list(lab._workflows.keys()),
            )
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            import traceback as _tb

            log.error("wsl_demo bootstrap FAILED — %s\n%s", exc, _tb.format_exc())
        return
    # Custom dotted path module:function
    if ":" in mode:
        mod_name, attr = mode.split(":", 1)
        module = importlib.import_module(mod_name)
        fn = getattr(module, attr)
        try:
            fn(lab)
        except Exception as exc:
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            raise
        return
    _set_bootstrap_diagnostics(lab, mode=mode, error=f"unknown bootstrap mode {mode!r}")
    log.warning("unknown AUTOLAB_BOOTSTRAP mode %r — booting empty", mode)


def _auto_register_this_pc(lab: Lab) -> None:
    """Register the host machine as a generic default local Resource.

    Idempotent: if a resource named ``local-computer`` already exists in the
    ResourceManager (restart case — rehydrated from the ledger), this is a
    no-op. Every fresh Lab boots with exactly one resource so the Console
    is never empty on first run.
    """
    existing = {r.name for r in lab.resources.list()}
    if "local-computer" in existing:
        return
    caps: dict[str, Any] = {
        "backend": "local",
        "connection": {"working_dir": ".autolab-work"},
        "tags": {"role": "autolab_host"},
        "cpu_count": os.cpu_count() or 1,
    }
    lab.register_resource(
        Resource(
            name="local-computer",
            kind="computer",
            capabilities=caps,
            description="Local computer running the autolab service. Auto-registered at boot.",
        )
    )


def _bootstrap(lab: Lab) -> None:
    _ensure_repo_on_path()
    _auto_register_this_pc(lab)
    mode = os.environ.get("AUTOLAB_BOOTSTRAP", "none")
    _apply_bootstrap_mode(lab, mode)


# ---------------------------------------------------------------------------
# Event bridge: Lab events → WebSocket broadcast.
# ---------------------------------------------------------------------------


async def _event_bridge(events: EventBus, ws_manager: ConnectionManager) -> None:
    q = events.subscribe()
    try:
        while True:
            ev = await q.get()
            msg = {
                "kind": ev.kind,
                "timestamp": ev.timestamp.isoformat(),
                "payload": ev.payload,
            }
            await ws_manager.broadcast(msg)
    except asyncio.CancelledError:
        return
    finally:
        events.unsubscribe(q)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load .env unless running under pytest (tests expect a clean environment).
    if "pytest" not in sys.modules:
        from dotenv import load_dotenv

        load_dotenv()  # loads .env from cwd if present
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-24s  %(message)s",
        datefmt="%H:%M:%S",
    )
    root = os.environ.get("AUTOLAB_ROOT", "./.autolab-runs/default")
    lab = Lab(root)
    _bootstrap(lab)
    scheduler = CampaignScheduler(lab)
    ws_manager = ConnectionManager()

    app.state.lab = lab
    app.state.scheduler = scheduler
    app.state.ws = ws_manager

    bridge = asyncio.create_task(_event_bridge(lab.events, ws_manager), name="event-bridge")
    sched_task = asyncio.create_task(scheduler.run(), name="scheduler-run")
    app.state._tasks = [bridge, sched_task]

    log.info("autolab server ready — ledger at %s", Path(root).resolve())
    try:
        yield
    finally:
        log.info("autolab server shutting down...")
        # Close all WebSocket connections first — give clients a chance to disconnect cleanly.
        await ws_manager.broadcast(
            {"kind": "server.shutdown", "timestamp": datetime.now(UTC).isoformat()}
        )
        await asyncio.sleep(0.1)  # Brief window for clients to acknowledge.

        # Cooperative cancellation of running campaigns.
        for cid, state in list(scheduler._campaigns.items()):
            if state.status in ("running", "paused", "queued"):
                with suppress(Exception):
                    await scheduler.cancel(cid)

        # Give the scheduler a bounded time to finish naturally.
        with suppress(TimeoutError, Exception):
            await asyncio.wait_for(sched_task, timeout=5.0)

        # Drain any in-flight Claude claim persistence before ledger closes.
        with suppress(TimeoutError, Exception):
            await asyncio.wait_for(drain_pending_claims(), timeout=3.0)

        # Forcefully cancel the event bridge.
        bridge.cancel()
        with suppress(Exception):
            await asyncio.wait_for(asyncio.shield(bridge), timeout=1.0)

        # Close the lab (flushes SQLite, closes connections).
        lab.close()
        log.info("autolab server shutdown complete")


app = FastAPI(title="autolab", lifespan=lifespan)


def _lab(request: Request) -> Lab:
    return request.app.state.lab


def _scheduler(request: Request) -> CampaignScheduler:
    return request.app.state.scheduler


def _ws_mgr(request: Request) -> ConnectionManager:
    return request.app.state.ws


# ---------------------------------------------------------------------------
# Static console
# ---------------------------------------------------------------------------


_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_file = _STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            "<h1>autolab</h1><p>Console not built. Is <code>src/autolab/server/static/index.html</code> present?</p>",
            status_code=500,
        )
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Status / introspection
# ---------------------------------------------------------------------------


@app.get("/status")
async def status(request: Request) -> dict[str, Any]:
    lab = _lab(request)
    scheduler = _scheduler(request)
    eng = EstimationEngine(lab)
    records = list(lab.ledger.iter_records())
    escalations = [
        esc.model_dump(mode="json")
        for cid in scheduler._campaigns
        for esc in lab.pending_escalations(cid)
    ]
    counts = {"completed": 0, "failed": 0, "pending": 0, "running": 0, "soft_fail": 0}
    for r in records:
        if r.record_status in counts:
            counts[r.record_status] += 1
    return {
        "lab_id": lab.lab_id,
        "root": str(lab.root.resolve()),
        "record_counts": counts,
        "total_records": len(records),
        "resources": lab.resources.status(),
        "tools": [_tool_row(d) for d in lab.tools.list()],
        "capabilities": [_tool_row(d) for d in lab.tools.list()],
        "campaigns": scheduler.status(),
        "escalations": escalations,
        "workflows": [w.model_dump(mode="json") for w in lab._workflows.values()],
        # UI exposes only these two; example bootstraps may register more in
        # the registry but they stay out of the dropdown to keep the MVP focused.
        "planners_available": ["optuna", "claude"],
        "estimation_summary": eng.summary(),
        "claude_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


def _tool_row(decl: Any) -> dict[str, Any]:
    raw = getattr(decl, "raw", {}) or {}
    return {
        "name": decl.name,
        "capability": decl.capability,
        "description": raw.get("description"),
        "version": decl.version,
        "resource_kind": decl.resource_kind,
        "requires": decl.requires,
        "inputs": decl.inputs,
        "outputs": decl.outputs,
        "module": decl.module,
        "produces_sample": decl.produces_sample,
        "destructive": decl.destructive,
        "declaration_hash": decl.declaration_hash,
        "typical_duration_s": decl.typical_duration_s,
    }


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


def _normalise_resource_request(body: ResourceRequest) -> Resource:
    """Convert user-facing Resource fields into the storage-compatible model."""
    raw = body.model_dump(exclude_none=True)
    backend = raw.pop("backend", None)
    connection = dict(raw.pop("connection", {}) or {})
    tags = dict(raw.pop("tags", {}) or {})
    capabilities = dict(raw.pop("capabilities", {}) or {})

    for key in ("host", "user", "port", "remote_root", "working_dir"):
        if key in raw:
            connection[key] = raw.pop(key)

    if backend:
        capabilities["backend"] = backend
    if connection:
        capabilities["connection"] = connection
    if tags:
        capabilities["tags"] = tags
        capabilities.update({k: v for k, v in tags.items() if k not in capabilities})

    kind = raw.pop("kind", None) or _infer_resource_kind(backend, capabilities)
    return Resource(
        name=raw["name"],
        kind=kind,
        capabilities=capabilities,
        description=raw.get("description"),
        asset_id=raw.get("asset_id"),
        typical_operation_durations=raw.get("typical_operation_durations", {}),
    )


def _infer_resource_kind(backend: str | None, capabilities: dict[str, Any]) -> str:
    scheduler = str(capabilities.get("scheduler") or "").lower()
    if backend == "slurm" or scheduler == "slurm":
        return "computer"
    if backend in {"local", "ssh_exec", "websocket", "mcp", "custom"}:
        return "computer"
    return "computer"


@app.get("/resources")
async def list_resources(request: Request) -> list[dict[str, Any]]:
    return _lab(request).resources.status()


@app.post("/resources")
async def add_resource(body: ResourceRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    try:
        resource = _normalise_resource_request(body)
        lab.register_resource(resource)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(400, str(exc)) from exc
    lab.events.publish_sync_safe = None  # type: ignore[attr-defined]
    # publish an event so the Console refreshes.
    from autolab.events import Event

    lab.events.publish(Event(kind="resource.registered", payload={"name": resource.name}))
    return {"ok": True, "name": resource.name}


@app.delete("/resources/{name}")
async def remove_resource(name: str, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    try:
        lab.resources.unregister(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    from autolab.events import Event

    lab.events.publish(Event(kind="resource.unregistered", payload={"name": name}))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@app.get("/tools")
async def list_tools(request: Request) -> list[dict[str, Any]]:
    return [_tool_row(d) for d in _lab(request).tools.list()]


@app.get("/capabilities")
async def list_capabilities(request: Request) -> list[dict[str, Any]]:
    return await list_tools(request)


def _normalise_capability_spec(body: dict[str, Any]) -> dict[str, Any]:
    spec = dict(body)
    if "capability" in spec and "name" not in spec:
        spec["name"] = spec["capability"]
    elif "name" in spec and "capability" not in spec:
        spec["capability"] = spec["name"]
    if "resource_kind" in spec and "resource" not in spec:
        spec["resource"] = spec["resource_kind"]
    if "resource" in spec and "resource_kind" not in spec:
        spec["resource_kind"] = spec["resource"]
    if "resource_requirements" in spec and "requires" not in spec:
        spec["requires"] = spec["resource_requirements"]
    if "requires" in spec and "resource_requirements" not in spec:
        spec["resource_requirements"] = spec["requires"]
    spec.setdefault("adapter", "dynamic")
    return spec


def _is_dynamic_capability(spec: dict[str, Any]) -> bool:
    adapter = str(spec.get("adapter") or "").lower()
    return adapter in {"dynamic", "dynamic_stub", "shell_command", "command"} or bool(
        spec.get("command_template")
    )


@app.post("/tools/register-yaml")
async def register_yaml_tool(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Register a YAML/JSON tool declaration POSTed as JSON.

    ``name`` defaults to ``capability`` if omitted — both fields refer to the
    same scientist-named identifier; the ToolDeclaration loader requires them.
    """
    lab = _lab(request)
    body = _normalise_capability_spec(body)
    try:
        if _is_dynamic_capability(body):
            _register_dynamic_operation(lab, body)
            decl = lab.tools.get(body["capability"])
        else:
            decl = lab.register_tool_dict(body)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc
    lab.events.publish(Event(kind="capability.registered", payload={"capability": decl.capability}))
    return _tool_row(decl)


@app.post("/capabilities/register")
async def register_capability(body: dict[str, Any], request: Request) -> dict[str, Any]:
    return await register_yaml_tool(body, request)


@app.post("/tools/register")
async def register_simple_tool(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Register a Tool from a simple JSON description (no adapter path required).

    Creates a dynamic stub Operation class whose outputs match the declared
    schema.  Meant for the console's Tool builder; scientists can later
    replace the stub with a real adapter by registering a YAML declaration
    at the same capability name after unregistering.
    """
    lab = _lab(request)
    body = _normalise_capability_spec(body)
    if "capability" not in body:
        raise HTTPException(400, "capability is required")
    if lab.tools.has(body["capability"]):
        raise HTTPException(400, f"tool {body['capability']!r} already registered")
    try:
        _register_dynamic_operation(lab, body)
    except Exception as exc:
        raise HTTPException(400, f"failed to register tool: {exc}") from exc
    lab.events.publish(
        Event(kind="capability.registered", payload={"capability": body["capability"]})
    )
    return {"ok": True, "capability": body["capability"]}


@app.post("/capabilities/{name}/smoke-test")
async def smoke_test_capability(
    name: str, body: CapabilitySmokeTestRequest, request: Request
) -> dict[str, Any]:
    """Run one capability through the orchestrator and return its Record."""
    lab = _lab(request)
    if not lab.tools.has(name):
        raise HTTPException(404, f"capability {name!r} is not registered")
    import uuid

    from autolab.orchestrator import CampaignRun

    session = lab.new_session()
    run = CampaignRun(
        lab_id=lab.lab_id,
        campaign_id=f"smoke-{uuid.uuid4().hex[:8]}",
        session=session,
    )
    step = ProposedStep(
        operation=name,
        inputs=dict(body.inputs),
        decision={"triggered_by": "smoke_test"},
    )
    rec, gate = await lab.orchestrator.run_step(step, run)
    return {
        "ok": rec.record_status == "completed",
        "record_id": rec.id,
        "record": rec.model_dump(mode="json"),
        "outputs": rec.outputs,
        "gate": gate.result if gate else None,
    }


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


@app.get("/workflows")
async def list_workflows(request: Request) -> list[dict[str, Any]]:
    lab = _lab(request)
    return [w.model_dump(mode="json") for w in lab._workflows.values()]


class WorkflowRunRequest(BaseModel):
    campaign_id: str | None = None  # optional grouping; new one minted if absent
    input_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    max_parallel: int | None = None


@app.post("/workflows/{name}/run")
async def run_workflow(name: str, body: WorkflowRunRequest, request: Request) -> dict[str, Any]:
    """Execute a registered WorkflowTemplate directly (no Planner loop).

    Each step is a full Orchestrator-wrapped Operation with hashed
    provenance. Returns the per-step outcomes.
    """
    lab = _lab(request)
    if name not in lab._workflows:
        raise HTTPException(404, f"workflow {name!r} not registered")
    import uuid

    from autolab.orchestrator import CampaignRun

    session = lab.new_session()
    cid = body.campaign_id or f"wf-{uuid.uuid4().hex[:10]}"
    run = CampaignRun(lab_id=lab.lab_id, campaign_id=cid, session=session)
    try:
        result = await lab.run_workflow(
            name,
            run,
            input_overrides=body.input_overrides,
            max_parallel=body.max_parallel,
        )
    except Exception as exc:
        raise HTTPException(500, f"workflow failed: {exc!r}") from exc
    return {
        "ok": result.completed,
        "campaign_id": cid,
        "workflow": name,
        "steps": [
            {
                "step_id": s.step_id,
                "record_id": s.record.id,
                "status": s.record.record_status,
                "operation": s.record.operation,
                "gate": s.gate.result if s.gate else None,
            }
            for s in result.steps
        ],
        "skipped": result.skipped_step_ids,
    }


@app.post("/workflows")
async def register_workflow(body: WorkflowRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    try:
        steps = [WorkflowStep(**s) for s in body.steps]
        tmpl = WorkflowTemplate(
            name=body.name,
            description=body.description,
            steps=steps,
            acceptance=(AcceptanceCriteria(**body.acceptance) if body.acceptance else None),
            typical_duration_s=body.typical_duration_s,
            metadata=body.metadata,
        )
        lab.register_workflow(tmpl)
    except ValidationError as exc:
        raise HTTPException(400, exc.errors()) from exc
    return tmpl.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


def _make_planner(lab: Lab, kind: str, config: dict[str, Any], *, claude_policy: bool) -> Planner:
    """Build a Planner for a campaign submission.

    The UI exposes exactly two planners (``optuna`` and ``claude``); any other
    name only works if it was explicitly registered by an example bootstrap
    (e.g. ``add_demo_optuna``). Unknown names return a helpful 400.
    """
    policy = None
    if claude_policy:
        policy = ClaudePolicyProvider(lab=lab, transport=ClaudeTransport())
    kind = (kind or "").lower().strip()
    if kind == "claude":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                400,
                "Claude planner selected but ANTHROPIC_API_KEY is not set. "
                "Add it to your .env and restart the server.",
            )
        return ClaudePlanner(
            lab=lab,
            transport=ClaudeTransport(),
            policy=policy,
            operation=config.get("operation"),
            search_space=config.get("search_space"),
            batch_size=int(config.get("batch_size") or 1),
            fixed_inputs=dict(config.get("fixed_inputs") or {}),
            input_routing=dict(config.get("input_routing") or {}),
        )
    if kind == "optuna":
        if "search_space" not in config:
            raise HTTPException(
                400,
                "Optuna planner requires a 'search_space' in planner_config. "
                'Example: {"operation": "my_op", "search_space": {"x": '
                '{"type": "float", "low": 0, "high": 10}}}',
            )
        try:
            return build_planner("optuna", config)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, f"Optuna planner config invalid: {exc}") from exc
    # Fall through: accept any other *registered* planner (example bootstraps
    # may register their own). Raise a friendly 400 if unknown.
    try:
        return build_planner(kind, config)
    except KeyError:
        known = [*list_planners(), "claude"]
        raise HTTPException(
            400,
            f"unknown planner {kind!r}. Supported: {sorted(set(known))}",
        ) from None
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"planner {kind!r} config invalid: {exc}") from exc


def _available_tool_names(lab: Lab) -> list[str]:
    return sorted(declaration.name for declaration in lab.tools.list())


def _available_workflow_names(lab: Lab) -> list[str]:
    return sorted(lab._workflows.keys())


def _resolve_submitted_workflow(lab: Lab, raw: dict[str, Any] | None) -> WorkflowTemplate | None:
    if not raw:
        return None
    workflow_name = str(raw.get("name") or "").strip()
    if "steps" not in raw:
        if workflow_name and workflow_name in lab._workflows:
            return lab._workflows[workflow_name]
        available = ", ".join(_available_workflow_names(lab)) or "none registered"
        raise HTTPException(
            400,
            f"workflow {workflow_name!r} is not registered and no inline steps were provided. "
            f"Available workflows: {available}.",
        )
    try:
        return WorkflowTemplate(**raw)
    except ValidationError as exc:
        raise HTTPException(400, exc.errors()) from exc


def _operation_outputs(lab: Lab, operation_names: set[str]) -> set[str]:
    output_keys: set[str] = set()
    for operation_name in operation_names:
        if not lab.tools.has(operation_name):
            continue
        output_keys.update((lab.tools.get(operation_name).outputs or {}).keys())
    return output_keys


def _campaign_submission_issues(
    lab: Lab,
    *,
    workflow: WorkflowTemplate | None,
    planner_config: dict[str, Any],
    objective_key: str | None,
) -> list[str]:
    issues: list[str] = []
    available_tools = _available_tool_names(lab)
    available_tools_text = ", ".join(available_tools) or "none registered"
    workflow_operations: set[str] = set()

    if workflow is not None:
        workflow_operations = {step.operation for step in workflow.steps}
        missing_operations = sorted(
            operation for operation in workflow_operations if not lab.tools.has(operation)
        )
        if missing_operations:
            issues.append(
                "Workflow uses unregistered capabilities "
                f"{missing_operations}. Available capabilities: {available_tools_text}."
            )

        step_ids = {step.step_id for step in workflow.steps}
        for step in workflow.steps:
            for input_name, reference in step.input_mappings.items():
                source_step_id, separator, output_key = str(reference).partition(".")
                if not separator or not source_step_id or not output_key:
                    issues.append(
                        f"Workflow step {step.step_id!r} maps input {input_name!r} "
                        f"from invalid reference {reference!r}; use step_id.output_key."
                    )
                elif source_step_id not in step_ids:
                    issues.append(
                        f"Workflow step {step.step_id!r} maps input {input_name!r} "
                        f"from unknown step {source_step_id!r}."
                    )

    planner_operation = str(planner_config.get("operation") or "").strip()
    if planner_operation:
        if workflow is not None and planner_operation not in workflow_operations:
            workflow_ops_text = ", ".join(sorted(workflow_operations)) or "none"
            issues.append(
                f"Planner target operation {planner_operation!r} is not in workflow "
                f"{workflow.name!r}. Workflow operations: {workflow_ops_text}."
            )
        elif workflow is None and not lab.tools.has(planner_operation):
            issues.append(
                f"Planner target operation {planner_operation!r} is not registered. "
                f"Available capabilities: {available_tools_text}."
            )

    if objective_key:
        if workflow is not None:
            candidate_outputs = _operation_outputs(lab, workflow_operations)
        elif planner_operation and lab.tools.has(planner_operation):
            candidate_outputs = _operation_outputs(lab, {planner_operation})
        else:
            candidate_outputs = _operation_outputs(lab, set(available_tools))
        if candidate_outputs and objective_key not in candidate_outputs:
            outputs_text = ", ".join(sorted(candidate_outputs))
            issues.append(
                f"Objective key {objective_key!r} is not produced by the selected "
                f"capability/workflow. Available outputs: {outputs_text}."
            )

    return issues


def _campaign_validation_question(issues: list[str]) -> str:
    joined = " ".join(issues).lower()
    if "unregistered" in joined or "not registered" in joined:
        return "Which registered capability or workflow should autolab use instead?"
    if "objective key" in joined:
        return "Which output metric from the registered tools should autolab optimise?"
    return "Which operation, workflow, objective metric, and search inputs should define this campaign?"


def _notes_with_validation(notes: str, issues: list[str]) -> str:
    suffix = "Cannot apply yet: " + " ".join(issues)
    if not notes:
        return suffix
    if suffix in notes:
        return notes
    return f"{notes} {suffix}"


@app.post("/campaigns")
async def submit_campaign(body: CampaignRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    scheduler = _scheduler(request)
    try:
        workflow = _resolve_submitted_workflow(lab, body.workflow)
        objective = Objective(**body.objective)
        issues = _campaign_submission_issues(
            lab,
            workflow=workflow,
            planner_config=body.planner_config,
            objective_key=objective.key,
        )
        if issues:
            raise HTTPException(400, " ".join(issues))
        campaign = Campaign(
            name=body.name,
            description=body.description,
            objective=objective,
            acceptance=(AcceptanceCriteria(**body.acceptance) if body.acceptance else None),
            budget=body.budget,
            parallelism=body.parallelism,
            workflow=workflow,
        )
    except HTTPException:
        raise
    except ValidationError as exc:
        raise HTTPException(400, exc.errors()) from exc

    planner = _make_planner(
        lab,
        body.planner,
        body.planner_config,
        claude_policy=body.use_claude_policy,
    )
    await scheduler.submit(campaign, planner, priority=body.priority)
    state = scheduler._campaigns[campaign.id]
    if body.autostart and state._task is None:
        # If a scheduler loop is already running, _launch() will pick up the new
        # state on the next tick. But if the user just booted the server, the
        # scheduler.run() task may have already exited (no work). Relaunch if so.
        scheduler._launch(state)
    # autostart=False → leave the campaign in "queued" status. The Console
    # starts it later via POST /campaigns/{id}/start.
    return {
        "ok": True,
        "campaign_id": campaign.id,
        "name": campaign.name,
        "status": state.status,
    }


@app.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str, request: Request) -> dict[str, Any]:
    """Kick off a campaign that was submitted with ``autostart=false``.

    A campaign created via ``POST /campaigns`` with ``autostart=false`` sits
    in ``status="queued"`` until someone calls this endpoint. Idempotent:
    calling it on an already-running campaign is a no-op.
    """
    scheduler = _scheduler(request)
    try:
        state = scheduler._get(campaign_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    terminal = {"failed", "completed", "cancelled", "stopped"}
    if state.status in terminal:
        return {"ok": True, "campaign_id": campaign_id, "status": state.status}
    if state.status not in ("queued",):
        # Already running — idempotent, return current state.
        return {"ok": True, "campaign_id": campaign_id, "status": state.status}
    if state._task is None:
        scheduler._launch(state)
    return {"ok": True, "campaign_id": campaign_id, "status": state.status}


@app.get("/campaigns")
async def list_campaigns(request: Request) -> list[dict[str, Any]]:
    return _scheduler(request).status()


@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, request: Request) -> dict[str, Any]:
    scheduler = _scheduler(request)
    try:
        state = scheduler._get(campaign_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "campaign_id": state.campaign.id,
        "name": state.campaign.name,
        "priority": state.priority,
        "status": state.status,
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
        "objective": state.campaign.objective.model_dump(),
        "budget": state.campaign.budget,
        "error": state.error,
        "summary": state.summary.model_dump(mode="json") if state.summary else None,
    }


@app.get("/campaigns/{campaign_id}/report", response_class=HTMLResponse)
async def campaign_report(campaign_id: str, request: Request) -> HTMLResponse:
    """Return a self-contained HTML report for the campaign."""
    import base64
    from html import escape

    lab = _lab(request)
    scheduler = _scheduler(request)

    # Fetch campaign state (404 if unknown)
    try:
        state = scheduler._get(campaign_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    campaign = state.campaign

    # Fetch all records for this campaign
    all_records = list(lab.ledger.iter_records(campaign_id=campaign_id))

    # ------------------------------------------------------------------
    # Find the "best" completed record (highest objective value, else last)
    # ------------------------------------------------------------------
    obj_key = campaign.objective.key if campaign.objective else None
    best_record = None
    best_val: float | None = None
    for r in all_records:
        if r.record_status == "completed" and r.outputs:
            v = r.outputs.get(obj_key) if obj_key else None
            if isinstance(v, (int, float)) and (best_val is None or v > best_val):
                best_val = v
                best_record = r
    if best_record is None and all_records:
        best_record = next(
            (r for r in reversed(all_records) if r.record_status == "completed"), all_records[-1]
        )

    # ------------------------------------------------------------------
    # Decision-chain records (records with a decision field)
    # ------------------------------------------------------------------
    decision_records = [r for r in all_records if getattr(r, "decision", None)]

    # ------------------------------------------------------------------
    # Find the last hysteresis PNG across all completed records
    # ------------------------------------------------------------------
    def _find_png(records):  # type: ignore[return]
        for rec in reversed(records):
            if rec.outputs:
                for k, v in rec.outputs.items():
                    if ("png" in k or "image" in k) and isinstance(v, str):
                        p = Path(v)
                        if p.exists():
                            return p
        return None

    png_path = _find_png(all_records)
    png_data_uri = ""
    if png_path:
        try:
            png_b64 = base64.b64encode(png_path.read_bytes()).decode()
            png_data_uri = f"data:image/png;base64,{png_b64}"
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Acceptance criteria
    # ------------------------------------------------------------------
    ac_rows = ""
    if campaign.acceptance_criteria:
        for output_key, rules in (campaign.acceptance_criteria or {}).items():
            for op, threshold in rules.items():
                actual = (
                    best_record.outputs.get(output_key, "—")
                    if best_record and best_record.outputs
                    else "—"
                )
                ac_rows += (
                    f"<tr><td>{escape(str(output_key))}</td>"
                    f"<td>{escape(str(op))} {escape(str(threshold))}</td>"
                    f"<td>{escape(str(actual))}</td></tr>\n"
                )

    # ------------------------------------------------------------------
    # Best-candidate outputs table
    # ------------------------------------------------------------------
    best_rows = ""
    if best_record and best_record.outputs:
        for k, v in list(best_record.outputs.items())[:20]:
            if "png" in k or "image" in k:
                continue
            best_rows += f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>\n"

    # ------------------------------------------------------------------
    # Decision chain table
    # ------------------------------------------------------------------
    decision_rows = ""
    for r in decision_records[:20]:
        d = r.decision or {}
        action = d.get("action", "—") if isinstance(d, dict) else str(d)
        reason = d.get("reason", "—") if isinstance(d, dict) else "—"
        short = ("0x" + r.checksum[:6]) if r.checksum else r.id[:8]
        decision_rows += (
            f"<tr><td><code>{escape(short)}</code></td>"
            f"<td>{escape(r.operation or '—')}</td>"
            f"<td>{escape(str(action))}</td>"
            f"<td style='max-width:400px;word-break:break-word'>{escape(str(reason)[:300])}</td></tr>\n"
        )

    # ------------------------------------------------------------------
    # Campaign hash (checksum of last record, as a proxy)
    # ------------------------------------------------------------------
    campaign_hash = ""
    if all_records:
        campaign_hash = all_records[-1].checksum or ""

    name = escape(campaign.name or campaign.id)
    goal_text = escape(campaign.description or campaign.name or obj_key or "—")
    status_text = escape(state.status)
    planner_text = escape(campaign.planner_name if hasattr(campaign, "planner_name") else "—")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>autolab report — {name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 32px 24px; color: #1a1a2e; background: #f8f9fa; }}
  h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 4px; color: #111; }}
  h2 {{ font-size: 15px; font-weight: 600; margin: 28px 0 8px; color: #2c3e50; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 6px 8px; background: #e9ecef; font-weight: 600; color: #444; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
  code {{ font-family: monospace; background: rgba(245,158,11,.15); padding: 1px 4px; border-radius: 3px; color: #b45309; }}
  .meta {{ font-size: 12px; color: #888; margin-top: 2px; }}
  .hysteresis {{ margin: 12px 0; }}
  .hysteresis img {{ max-width: 100%; border-radius: 6px; border: 1px solid #ddd; }}
  footer {{ margin-top: 48px; font-size: 11px; color: #aaa; border-top: 1px solid #eee; padding-top: 12px; }}
</style>
</head>
<body>
<h1>{name}</h1>
<div class="meta">Status: <strong>{status_text}</strong> · Planner: {planner_text}</div>

<h2>Goal</h2>
<p style="margin:0;font-size:13px">{goal_text}</p>

<h2>Acceptance criteria</h2>
{"<table><tr><th>Output</th><th>Criterion</th><th>Actual (best)</th></tr>" + ac_rows + "</table>" if ac_rows else "<p style='font-size:13px;color:#888'>None specified.</p>"}

<h2>Winning candidate</h2>
{"<table><tr><th>Output key</th><th>Value</th></tr>" + best_rows + "</table>" if best_rows else "<p style='font-size:13px;color:#888'>No completed records yet.</p>"}

<h2>Hysteresis loop</h2>
{"<div class='hysteresis'><img src='" + png_data_uri + "' alt='Hysteresis loop'/></div>" if png_data_uri else "<p style='font-size:13px;color:#888'>No figure available.</p>"}

<h2>Decision chain</h2>
{"<table><tr><th>Record</th><th>Operation</th><th>Action</th><th>Reason</th></tr>" + decision_rows + "</table>" if decision_rows else "<p style='font-size:13px;color:#888'>No reactive decisions recorded.</p>"}

<footer>
  autolab · campaign <code>{escape(campaign_id)}</code>
  {"· ledger anchor <code>" + escape(campaign_hash[:16]) + "…</code>" if campaign_hash else ""}
</footer>
</body>
</html>"""

    return HTMLResponse(html)


@app.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, request: Request) -> dict[str, Any]:
    await _scheduler(request).pause(campaign_id)
    return {"ok": True}


@app.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, request: Request) -> dict[str, Any]:
    await _scheduler(request).resume(campaign_id)
    return {"ok": True}


@app.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign(campaign_id: str, request: Request) -> dict[str, Any]:
    await _scheduler(request).cancel(campaign_id)
    return {"ok": True}


@app.post("/campaigns/{campaign_id}/intervene")
async def intervene(
    campaign_id: str, body: InterventionRequest, request: Request
) -> dict[str, Any]:
    lab = _lab(request)
    inter = Intervention(
        campaign_id=campaign_id,
        body=body.body,
        author=body.author,
        payload=body.payload,
    )
    rec = await lab.record_intervention(inter)
    return {"ok": True, "record_id": rec.id}


# ---------------------------------------------------------------------------
# Campaign designer (Claude)
# ---------------------------------------------------------------------------


@app.post("/campaigns/design")
async def design_campaign(body: DesignRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    designer = CampaignDesigner(lab=lab, transport=ClaudeTransport())
    result = await designer.adesign(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    questions = list(result.questions)
    ready_to_apply = result.ready_to_apply
    notes = result.notes
    if result.campaign_json:
        validation_issues: list[str] = []
        try:
            workflow = _resolve_submitted_workflow(lab, result.workflow_json)
            objective_key = (result.campaign_json.get("objective") or {}).get("key")
            validation_issues = _campaign_submission_issues(
                lab,
                workflow=workflow,
                planner_config=dict(result.campaign_json.get("planner_config") or {}),
                objective_key=str(objective_key) if objective_key else None,
            )
        except HTTPException as exc:
            validation_issues = [str(exc.detail)]
        if validation_issues:
            ready_to_apply = False
            notes = _notes_with_validation(notes, validation_issues)
            question = _campaign_validation_question(validation_issues)
            if question not in questions:
                questions.append(question)
    return {
        "campaign": result.campaign_json,
        "workflow": result.workflow_json,
        "questions": questions,
        "ready_to_apply": ready_to_apply,
        "notes": notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
        "prompt_sha256": result.raw.prompt_hash,
    }


# ---------------------------------------------------------------------------
# Data Chat designer (Claude)
# ---------------------------------------------------------------------------


_ANALYSIS_SYSTEM = """You are the Data Chat analyst for autolab, an autonomous
science lab. A scientist asks about campaign ledger records.
Return ONLY one compact JSON object:

{
  "answer": "one short interpretation grounded in the rows and values you used",
  "chart": {
    "type": "line|scatter|bar",
    "title": "short title",
    "subtitle": "short subtitle",
    "x": "field path",
    "y": "field path",
    "series_by": "field path",
    "transform": "none|best_so_far",
    "aggregate": "none|mean|max|min|count",
    "filters": [{"field": "field path", "op": "eq|ne|exists", "value": "optional"}]
  }
}

Use only fields listed in the context. Useful generic fields include:
trial, objective_value, duration_s, campaign_name, planner, operation,
record_status, created_at, inputs.<name>, outputs.<name>, decision.<name>.
For convergence or objective requests, prefer x=trial, y=objective_value,
series_by=campaign_name, transform=best_so_far. For failure questions, prefer
type=bar, x=campaign_name, aggregate=count, and filter record_status to failed
if that field exists. If objective_value is not
available, choose a field from potential_objective_fields. For runtime
requests, prefer type=bar, x=campaign_name, y=duration_s, aggregate=mean.
Never mention unavailable fields."""


@app.post("/analysis/query")
async def query_analysis(body: AnalysisRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    scheduler = _scheduler(request)
    all_records = list(lab.ledger.iter_records())
    if body.campaign_ids:
        allowed = set(body.campaign_ids)
        all_records = [r for r in all_records if r.campaign_id in allowed]
    all_records = all_records[-body.limit :]
    campaigns = {state.campaign.id: state for state in scheduler._campaigns.values()}
    rows = _analysis_rows(all_records, campaigns)
    context = _analysis_context(body.prompt, rows, campaigns)
    transport = ClaudeTransport(max_tokens=900)
    resp = await transport.acall(_ANALYSIS_SYSTEM, context)
    data = _safe_claude_json(resp.text) or {}
    spec = _normalise_analysis_spec(data.get("chart") or {}, rows)
    chart = _materialise_analysis_chart(spec, rows)
    answer = str(data.get("answer") or chart.get("subtitle") or "Generated from ledger records.")
    return {
        "answer": answer,
        "chart": chart,
        "spec": spec,
        "model": resp.model,
        "offline": resp.offline,
        "prompt_sha256": resp.prompt_hash,
    }


def _analysis_rows(records: list[Any], campaigns: dict[str, Any]) -> list[dict[str, Any]]:
    ordered = sorted(records, key=lambda r: r.created_at)
    record_counts: dict[str, int] = {}
    objective_counts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for rec in ordered:
        state = campaigns.get(rec.campaign_id or "")
        campaign = state.campaign if state is not None else None
        objective_key = campaign.objective.key if campaign is not None else None
        cid = rec.campaign_id or ""
        record_counts[cid] = record_counts.get(cid, 0) + 1
        outputs = dict(rec.outputs or {})
        decision = dict(rec.decision or {})
        trial_number = decision.get("trial_number")
        if isinstance(trial_number, int):
            trial = trial_number + 1
        elif objective_key and _analysis_number(outputs.get(objective_key)) is not None:
            objective_counts[cid] = objective_counts.get(cid, 0) + 1
            trial = objective_counts[cid]
        else:
            trial = record_counts[cid]
        rows.append(
            {
                "record_id": rec.id,
                "campaign_id": rec.campaign_id,
                "campaign_name": campaign.name if campaign is not None else rec.campaign_id,
                "planner": decision.get("planner") or "planner",
                "objective_key": objective_key,
                "objective_direction": (
                    campaign.objective.direction if campaign is not None else "maximise"
                ),
                "objective_value": (
                    _analysis_number(outputs.get(objective_key)) if objective_key else None
                ),
                "trial": trial,
                "operation": rec.operation,
                "record_status": rec.record_status,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
                "duration_s": (
                    float(rec.duration_ms) / 1000.0 if rec.duration_ms is not None else None
                ),
                "inputs": dict(rec.inputs or {}),
                "outputs": outputs,
                "decision": decision,
                "metadata": dict(rec.metadata or {}),
            }
        )
    return rows


def _analysis_context(
    prompt: str,
    rows: list[dict[str, Any]],
    campaigns: dict[str, Any],
) -> str:
    field_counts: dict[str, int] = {}
    for row in rows:
        for field in _analysis_available_fields(row):
            field_counts[field] = field_counts.get(field, 0) + 1
    campaign_rows = []
    for state in campaigns.values():
        c = state.campaign
        campaign_rows.append(
            {
                "campaign_id": c.id,
                "name": c.name,
                "description": c.description,
                "objective": c.objective.model_dump(mode="json"),
                "status": state.status,
            }
        )
    sample_rows = [_analysis_compact_row(r) for r in rows if r.get("record_status") == "completed"][
        -12:
    ]
    payload = {
        "scientist_prompt": prompt,
        "campaigns": campaign_rows,
        "available_fields": sorted(field_counts),
        "potential_objective_fields": _potential_objective_fields(sorted(field_counts)),
        "record_count": len(rows),
        "completed_record_count": sum(1 for r in rows if r.get("record_status") == "completed"),
        "sample_rows": sample_rows,
    }
    return json.dumps(payload, default=str)[:12000]


def _potential_objective_fields(fields: list[str]) -> list[str]:
    hints = ("objective", "score", "fom", "hmax", "sensitivity", "yield", "accuracy", "loss")
    out = []
    for field in fields:
        lowered = field.lower()
        if lowered.startswith("outputs.") and any(hint in lowered for hint in hints):
            out.append(field)
    return out


def _analysis_available_fields(row: dict[str, Any]) -> list[str]:
    fields = [
        "record_id",
        "campaign_id",
        "campaign_name",
        "planner",
        "objective_key",
        "objective_direction",
        "objective_value",
        "trial",
        "operation",
        "record_status",
        "created_at",
        "duration_s",
    ]
    for root in ("inputs", "outputs", "decision", "metadata"):
        for key, value in (row.get(root) or {}).items():
            if isinstance(value, str | int | float | bool) or value is None:
                fields.append(f"{root}.{key}")
    return fields


def _analysis_compact_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = {k: row.get(k) for k in _analysis_available_fields(row) if "." not in k}
    for root in ("inputs", "outputs", "decision"):
        values = {}
        for key, value in (row.get(root) or {}).items():
            if isinstance(value, str | int | float | bool) or value is None:
                values[key] = value
        if values:
            compact[root] = values
    return compact


def _normalise_analysis_spec(spec: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    available = {field for row in rows for field in _analysis_available_fields(row)}
    chart_type = str(spec.get("type") or "line").lower()
    if chart_type not in {"line", "scatter", "bar"}:
        chart_type = "line"
    x_field = str(spec.get("x") or "trial")
    y_field = str(spec.get("y") or "objective_value")
    if x_field not in available:
        x_field = "trial"
    if y_field not in available:
        y_field = _first_numeric_field(rows) or "objective_value"
    elif not any(_analysis_number(_analysis_value(row, y_field)) is not None for row in rows):
        y_field = _first_numeric_field(rows) or y_field
    series_by = str(spec.get("series_by") or "campaign_name")
    if series_by not in available:
        series_by = "campaign_name"
    transform = str(spec.get("transform") or "none").lower()
    if transform not in {"none", "best_so_far"}:
        transform = "none"
    aggregate = str(spec.get("aggregate") or ("mean" if chart_type == "bar" else "none")).lower()
    if aggregate not in {"none", "mean", "max", "min", "count"}:
        aggregate = "none"
    filters = spec.get("filters") if isinstance(spec.get("filters"), list) else []
    return {
        "type": chart_type,
        "title": str(spec.get("title") or "Ledger analysis")[:120],
        "subtitle": str(spec.get("subtitle") or "")[:240],
        "x": x_field,
        "y": y_field,
        "series_by": series_by,
        "transform": transform,
        "aggregate": aggregate,
        "filters": filters[:6],
    }


def _materialise_analysis_chart(spec: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    filtered = [row for row in rows if _analysis_row_matches(row, spec.get("filters") or [])]
    series = (
        _analysis_bar_series(filtered, spec)
        if spec["type"] == "bar"
        else _analysis_point_series(filtered, spec)
    )
    return {
        "type": spec["type"],
        "title": spec["title"],
        "subtitle": spec["subtitle"],
        "x_label": spec["x"],
        "y_label": spec["y"],
        "series": series,
    }


def _analysis_point_series(
    rows: list[dict[str, Any]], spec: dict[str, Any]
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        x = _analysis_value(row, spec["x"])
        y = _analysis_number(_analysis_value(row, spec["y"]))
        if x is None or y is None:
            continue
        label = str(_analysis_value(row, spec["series_by"]) or "series")
        groups.setdefault(label, []).append({"x": x, "y": y, "row": row})
    out = []
    for idx, (label, points) in enumerate(groups.items()):
        points = sorted(points, key=lambda p: _analysis_sort_value(p["x"]))
        if spec.get("transform") == "best_so_far":
            direction = str(points[0]["row"].get("objective_direction") or "maximise")
            best: float | None = None
            for point in points:
                point["raw_y"] = float(point["y"])
                value = float(point["y"])
                if best is None or (value < best if direction == "minimise" else value > best):
                    best = value
                point["y"] = best
        out.append(
            {
                "label": label,
                "color": _ANALYSIS_COLORS[idx % len(_ANALYSIS_COLORS)],
                "points": [
                    {
                        "x": p["x"],
                        "y": p["y"],
                        "record_id": p["row"].get("record_id"),
                        "tooltip": _analysis_tooltip(
                            p["row"], spec, p["x"], p["y"], p.get("raw_y")
                        ),
                    }
                    for p in points
                ],
            }
        )
    return out


def _analysis_bar_series(rows: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = {}
    for row in rows:
        label = str(_analysis_value(row, spec["x"]) or "value")
        if spec.get("aggregate") == "count":
            groups.setdefault(label, []).append(1.0)
            continue
        value = _analysis_number(_analysis_value(row, spec["y"]))
        if value is not None:
            groups.setdefault(label, []).append(value)
    points = []
    for label, values in groups.items():
        aggregate = spec.get("aggregate")
        if aggregate == "max":
            y = max(values)
        elif aggregate == "min":
            y = min(values)
        elif aggregate == "count":
            y = float(len(values))
        else:
            y = sum(values) / len(values)
        points.append({"x": label, "y": y, "tooltip": f"{label}: {y:.5g}"})
    return [{"label": spec["y"], "color": _ANALYSIS_COLORS[0], "points": points}]


def _analysis_row_matches(row: dict[str, Any], filters: list[Any]) -> bool:
    for raw in filters:
        if not isinstance(raw, dict):
            continue
        field = str(raw.get("field") or "")
        op = str(raw.get("op") or "eq")
        expected = raw.get("value")
        value = _analysis_value(row, field)
        if op == "exists" and value is None:
            return False
        if op == "eq" and value != expected:
            return False
        if op == "ne" and value == expected:
            return False
    return True


def _analysis_value(row: dict[str, Any], field: str) -> Any:
    aliases = {
        "objective": "objective_value",
        "campaign": "campaign_name",
        "duration": "duration_s",
    }
    current: Any = row
    for part in aliases.get(field, field).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _analysis_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n and n not in {float("inf"), float("-inf")} else None


def _analysis_sort_value(value: Any) -> Any:
    numeric = _analysis_number(value)
    if numeric is not None:
        return numeric
    if isinstance(value, str):
        with suppress(ValueError):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    return str(value)


def _first_numeric_field(rows: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for row in rows:
        for field in _analysis_available_fields(row):
            if _analysis_number(_analysis_value(row, field)) is not None:
                counts[field] = counts.get(field, 0) + 1
    if not counts:
        return None
    objective_like = _potential_objective_fields(list(counts))
    if objective_like:
        return max(objective_like, key=lambda field: counts.get(field, 0))
    return max(counts, key=counts.get)


def _analysis_tooltip(
    row: dict[str, Any], spec: dict[str, Any], x: Any, y: Any, raw_y: Any = None
) -> str:
    base = f"{row.get('campaign_name')} | {row.get('operation')} | {spec['x']}={x}"
    try:
        if raw_y is not None and abs(float(y) - float(raw_y)) > 1e-9:
            return f"{base} | max={y:.5g} (raw={float(raw_y):.5g})"
    except (ValueError, TypeError):
        pass
    return f"{base} | {spec['y']}={y:.5g}"


_ANALYSIS_COLORS = ["#c96342", "#6b8fd6", "#7fd67f", "#e8b062", "#d66666", "#b58bd9"]


# ---------------------------------------------------------------------------
# Lab setup — LLM-assisted onboarding
# ---------------------------------------------------------------------------


@app.post("/lab/setup")
async def design_lab_setup(body: LabSetupRequest, request: Request) -> dict[str, Any]:
    """Describe your lab in plain language → Claude proposes resources and operations."""
    lab = _lab(request)
    designer = LabSetupDesigner(lab=lab, transport=ClaudeTransport())
    result = await designer.adesign(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "resources": result.resources,
        "operations": result.operations,
        "workflow": result.workflow,
        "questions": result.questions,
        "ready_to_apply": result.ready_to_apply,
        "notes": result.notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/resources/design")
async def design_resource(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    """Propose (or refine) a single Resource from a natural-language description."""
    lab = _lab(request)
    designer = ResourceDesigner(lab=lab, transport=ClaudeTransport())
    result = await designer.adesign(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "resource": result.resource,
        "notes": result.notes,
        "questions": result.questions,
        "ready_to_apply": result.ready_to_apply,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/tools/design")
async def design_tool(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    """Propose (or refine) a single Tool declaration from a natural-language description."""
    lab = _lab(request)
    designer = ToolDesigner(lab=lab, transport=ClaudeTransport())
    result = await designer.adesign(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "tool": result.tool,
        "notes": result.notes,
        "questions": result.questions,
        "ready_to_apply": result.ready_to_apply,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/capabilities/design")
async def design_capability(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    return await design_tool(body, request)


@app.post("/workflows/design")
async def design_workflow(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    """Propose (or refine) a single WorkflowTemplate from a natural-language description."""
    lab = _lab(request)
    designer = WorkflowDesigner(lab=lab, transport=ClaudeTransport())
    result = await designer.adesign(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "workflow": result.workflow,
        "notes": result.notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/lab/setup/apply")
async def apply_lab_setup(body: LabSetupApplyRequest, request: Request) -> dict[str, Any]:
    """Apply a reviewed lab setup proposal — register resources and operations."""
    lab = _lab(request)
    registered_resources = []
    registered_operations = []
    registered_workflows = []
    errors = []

    for r in body.resources:
        try:
            resource = Resource(
                name=r["name"],
                kind=r["kind"],
                capabilities=r.get("capabilities", {}),
                description=r.get("description", ""),
                typical_operation_durations=r.get("typical_operation_durations", {}),
            )
            lab.register_resource(resource)
            registered_resources.append(r["name"])
            from autolab.events import Event

            lab.events.publish(Event(kind="resource.registered", payload={"name": resource.name}))
        except Exception as exc:
            errors.append(f"resource {r.get('name', '?')}: {exc}")

    for op in body.operations:
        try:
            _register_dynamic_operation(lab, op)
            registered_operations.append(op["capability"])
        except Exception as exc:
            errors.append(f"operation {op.get('capability', '?')}: {exc}")

    if body.workflow:
        try:
            steps = [WorkflowStep(**s) for s in body.workflow.get("steps", [])]
            workflow = WorkflowTemplate(
                name=body.workflow["name"],
                description=body.workflow.get("description"),
                steps=steps,
                acceptance=(
                    AcceptanceCriteria(**body.workflow["acceptance"])
                    if body.workflow.get("acceptance")
                    else None
                ),
                typical_duration_s=body.workflow.get("typical_duration_s"),
                metadata=body.workflow.get("metadata", {}),
            )
            lab.register_workflow(workflow)
            registered_workflows.append(workflow.name)
            lab.events.publish(Event(kind="workflow.registered", payload={"name": workflow.name}))
        except Exception as exc:
            errors.append(f"workflow {body.workflow.get('name', '?')}: {exc}")

    return {
        "ok": len(errors) == 0,
        "registered_resources": registered_resources,
        "registered_operations": registered_operations,
        "registered_workflows": registered_workflows,
        "errors": errors,
    }


@app.post("/bootstraps/apply")
async def apply_bootstrap(body: BootstrapApplyRequest, request: Request) -> dict[str, Any]:
    """Apply a named bootstrap to a running Lab without restarting the server.

    This is intentionally idempotent for the built-in example bundles: each
    bootstrap is responsible for skipping entities that are already registered.
    """
    lab = _lab(request)
    _ensure_repo_on_path()
    before_resources = {r.name for r in lab.resources.list()}
    before_capabilities = {d.capability for d in lab.tools.list()}
    before_workflows = set(lab._workflows.keys())
    try:
        _apply_bootstrap_mode(lab, body.mode)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    after_resources = {r.name for r in lab.resources.list()}
    after_capabilities = {d.capability for d in lab.tools.list()}
    after_workflows = set(lab._workflows.keys())

    for name in sorted(after_resources - before_resources):
        lab.events.publish(Event(kind="resource.registered", payload={"name": name}))
    for capability in sorted(after_capabilities - before_capabilities):
        lab.events.publish(Event(kind="tool.registered", payload={"capability": capability}))
    for workflow in sorted(after_workflows - before_workflows):
        lab.events.publish(Event(kind="workflow.registered", payload={"name": workflow}))

    return {
        "ok": True,
        "bootstrap_mode": body.mode,
        "resources": [r.name for r in lab.resources.list()],
        "capabilities": [d.capability for d in lab.tools.list()],
        "workflows": list(lab._workflows.keys()),
        "bootstrap_error": getattr(lab, "_bootstrap_diagnostics", {}).get("error"),
    }


def _register_dynamic_operation(lab: Lab, spec: dict[str, Any]) -> None:
    """Register a dynamically defined Operation from a setup proposal.

    ``adapter=dynamic`` creates an explicit mock. ``adapter=shell_command`` or
    ``command_template`` creates a runnable command-backed capability.
    """
    spec = _normalise_capability_spec(spec)
    capability = spec["capability"]
    resource_kind = spec.get("resource_kind")
    module = spec.get("module", f"{capability}.stub.v1")
    produces_sample = spec.get("produces_sample", False)
    destructive = spec.get("destructive", False)
    duration = spec.get("typical_duration_s", 5)
    output_schema = spec.get("outputs", {})
    requires = spec.get("requires", {}) or {}
    adapter = str(spec.get("adapter") or "dynamic").lower()
    command_template = spec.get("command_template") or spec.get("command")
    declared_outputs = list(spec.get("declared_outputs") or [])
    default_env = dict(spec.get("env") or {})
    default_cwd = spec.get("cwd") or spec.get("working_dir")
    default_timeout = spec.get("timeout_seconds")

    # Build a simple Operation class dynamically
    from pydantic import create_model

    from autolab.operations.base import Operation, OperationContext

    class DynamicOp(Operation):
        pass

    DynamicOp.capability = capability
    DynamicOp.resource_kind = resource_kind
    DynamicOp.requires = dict(requires)
    DynamicOp.module = module
    DynamicOp.produces_sample = produces_sample
    DynamicOp.destructive = destructive
    DynamicOp.typical_duration = duration
    DynamicOp.Inputs = create_model(  # type: ignore[attr-defined]
        f"{capability.title().replace('_', '')}Inputs",
        **{name: (Any, None) for name in dict(spec.get("inputs", {}) or {})},
    )
    DynamicOp.Outputs = create_model(  # type: ignore[attr-defined]
        f"{capability.title().replace('_', '')}Outputs",
        **{name: (Any, None) for name in output_schema},
    )

    async def _run(self: Any, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
        if adapter in {"shell_command", "command"} or command_template:
            from autolab.tools.adapters.shell_command import ShellCommand

            command = inputs.get("command") or _render_command_template(
                str(command_template or ""), inputs
            )
            if not command:
                return OperationResult(
                    status="failed",
                    outputs={
                        "reason": "command-backed capability needs `command` or `command_template`"
                    },
                )
            shell_inputs = {
                "command": command,
                "cwd": inputs.get("cwd") or default_cwd,
                "env": {**default_env, **dict(inputs.get("env") or {})},
                "timeout_seconds": inputs.get("timeout_seconds", default_timeout),
                "declared_outputs": inputs.get("declared_outputs", declared_outputs),
            }
            return await ShellCommand().run(shell_inputs, context)

        import random

        await asyncio.sleep(0.3 + random.random() * 0.4)
        # Generate stub outputs matching the declared schema
        outputs: dict[str, Any] = {}
        for key, typ in output_schema.items():
            typ_str = str(typ).lower()
            if "float" in typ_str or "number" in typ_str:
                outputs[key] = round(random.uniform(0.1, 100.0), 3)
            elif "int" in typ_str:
                outputs[key] = random.randint(1, 100)
            elif "bool" in typ_str:
                outputs[key] = random.choice([True, False])
            elif "list" in typ_str or "array" in typ_str:
                outputs[key] = []
            elif "dict" in typ_str or "object" in typ_str:
                outputs[key] = {}
            else:
                outputs[key] = f"stub-{key}"
        return OperationResult(status="completed", outputs=outputs)

    DynamicOp.run = _run
    DynamicOp.__name__ = f"DynamicOp_{capability}"
    DynamicOp.__qualname__ = DynamicOp.__name__
    DynamicOp.__abstractmethods__ = frozenset()

    if not lab.tools.has(capability):
        lab.register_operation(DynamicOp)


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_command_template(template: str, inputs: dict[str, Any]) -> str:
    if not template:
        return ""
    values = _SafeFormatDict({k: _format_command_value(v) for k, v in inputs.items()})
    return template.format_map(values)


def _format_command_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value)


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------


@app.get("/escalations")
async def list_escalations(request: Request) -> list[dict[str, Any]]:
    lab = _lab(request)
    scheduler = _scheduler(request)
    out: list[dict[str, Any]] = []
    for cid in scheduler._campaigns:
        for esc in lab.pending_escalations(cid):
            row: dict[str, Any] = {
                "id": esc.id,
                "campaign_id": esc.campaign_id,
                "record_id": esc.record_id,
                "reason": esc.reason,
                "context": esc.context,
            }
            # Attach the triggering record's outputs for image preview
            with suppress(Exception):
                rec = lab.ledger.get(esc.record_id)
                if rec:
                    row["operation"] = rec.operation
                    row["outputs"] = rec.outputs
            out.append(row)
    return out


@app.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str, body: EscalationResolutionRequest, request: Request
) -> dict[str, Any]:
    lab = _lab(request)
    scheduler = _scheduler(request)
    extra = None
    if body.extra_step:
        extra = ProposedStep(**body.extra_step)
    resolution = EscalationResolution(
        escalation_id=escalation_id,
        action=body.action,  # type: ignore[arg-type]
        reason=body.reason,
        retry_inputs=body.retry_inputs,
        extra_step=extra,
    )
    # Find which campaign owns it.
    for cid in scheduler._campaigns:
        pending = lab.pending_escalations(cid)
        if any(e.id == escalation_id for e in pending):
            lab.resolve_escalation(cid, escalation_id, resolution)
            return {"ok": True}
    raise HTTPException(404, f"escalation {escalation_id!r} not found")


# ---------------------------------------------------------------------------
# Ledger / records
# ---------------------------------------------------------------------------


@app.get("/ledger")
async def ledger(
    request: Request,
    campaign_id: str | None = None,
    experiment_id: str | None = None,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=5000),
    filter: str | None = None,
) -> dict[str, Any]:
    lab = _lab(request)
    records = list(
        lab.ledger.iter_records(
            campaign_id=campaign_id,
            experiment_id=experiment_id,
            status=status,
        )
    )
    if filter:
        try:
            records = query.apply(records, filter)
        except query.QueryError as exc:
            raise HTTPException(400, f"bad filter: {exc}") from exc
    total = len(records)
    # Latest first for the console.
    records = list(reversed(records))[:limit]
    return {
        "total": total,
        "records": [r.model_dump(mode="json") for r in records],
    }


@app.get("/records/{record_id}")
async def get_record(record_id: str, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    rec = lab.ledger.get(record_id)
    if rec is None:
        raise HTTPException(404, f"record {record_id!r} not found")
    anns = lab.ledger.annotations(record_id)
    return {
        "record": rec.model_dump(mode="json"),
        "history": [r.model_dump(mode="json") for r in lab.ledger.history(record_id)],
        "annotations": [a.model_dump(mode="json") for a in anns],
    }


@app.post("/records/{record_id}/extract")
async def extract_annotations(record_id: str, request: Request) -> dict[str, Any]:
    """Run the `annotation_extract` Interpretation Op on a Record's notes.

    Produces a new Claim-style Record with tags + extracted structured
    facts + confidence. The call itself is a Record, so every extraction
    is auditable.
    """
    lab = _lab(request)
    if not lab.tools.has("annotation_extract"):
        raise HTTPException(503, "annotation_extract not registered on this Lab")
    import uuid

    from autolab.orchestrator import CampaignRun

    session = lab.new_session()
    run = CampaignRun(
        lab_id=lab.lab_id,
        campaign_id=f"extract-{uuid.uuid4().hex[:8]}",
        session=session,
    )
    step = ProposedStep(
        operation="annotation_extract",
        inputs={"target_record_id": record_id},
        decision={"triggered_by": "http"},
    )
    rec, gate = await lab.orchestrator.run_step(step, run)
    return {
        "ok": rec.record_status == "completed",
        "record_id": rec.id,
        "outputs": rec.outputs,
        "gate": gate.result if gate else None,
    }


@app.post("/records/{record_id}/annotate")
async def annotate_record(
    record_id: str, body: AnnotationRequest, request: Request
) -> dict[str, Any]:
    lab = _lab(request)
    ann = Annotation(
        target_record_id=record_id,
        kind="note",
        body={"note": body.note, "tags": body.tags},
        author=body.author,
    )
    try:
        await lab.annotate(ann)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "annotation_id": ann.id}


@app.get("/export/ro-crate")
async def export_ro_crate(request: Request, campaign_id: str | None = None) -> dict[str, Any]:
    from autolab.export import to_ro_crate

    return to_ro_crate(_lab(request), campaign_id=campaign_id)


@app.get("/export/prov")
async def export_prov(request: Request, campaign_id: str | None = None) -> dict[str, Any]:
    from autolab.export import to_prov

    return to_prov(_lab(request), campaign_id=campaign_id)


@app.get("/samples/{sample_id}/history")
async def sample_history(sample_id: str, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    records = lab.ledger.sample_history(sample_id)
    return {
        "sample_id": sample_id,
        "lineage": lab.ledger.sample_lineage(sample_id),
        "records": [r.model_dump(mode="json") for r in records],
    }


@app.get("/verify")
async def verify(request: Request) -> dict[str, Any]:
    lab = _lab(request)
    bad = lab.verify_ledger()
    return {"ok": not bad, "bad_record_ids": bad}


@app.get("/debug/bootstrap")
async def debug_bootstrap(request: Request) -> dict[str, Any]:
    """Human-readable summary of what got registered at startup.
    Visit http://localhost:8000/debug/bootstrap if the UI shows empty library.
    """
    lab = _lab(request)
    diag = getattr(lab, "_bootstrap_diagnostics", {})
    return {
        "bootstrap_mode": diag.get("mode")
        or os.environ.get("AUTOLAB_BOOTSTRAP", "demo_quadratic (default)"),
        "bootstrap_error": diag.get("error"),
        "cwd": str(Path.cwd()),
        "examples_on_path": any("autolab" in p for p in sys.path),
        "resources": [r.name for r in lab.resources.list()],
        "capabilities": [d.capability for d in lab.tools.list()],
        "workflows": list(lab._workflows.keys()),
        "hint": (
            "If resources/capabilities/workflows are empty, check server startup logs "
            "for 'bootstrap FAILED' messages. Common cause: AUTOLAB_BOOTSTRAP env var "
            "not passed through to the server process."
        ),
    }


# ---------------------------------------------------------------------------
# ETAs / estimation
# ---------------------------------------------------------------------------


@app.get("/estimate/summary")
async def estimate_summary(request: Request) -> list[dict[str, Any]]:
    return EstimationEngine(_lab(request)).summary()


@app.get("/estimate/eta")
async def estimate_eta(request: Request, campaign_id: str) -> dict[str, Any]:
    return EstimationEngine(_lab(request)).eta_for_campaign(campaign_id)


@app.post("/estimate/workflow")
async def estimate_workflow(body: dict[str, Any], request: Request) -> dict[str, Any]:
    ops = list(body.get("operations") or [])
    hint = body.get("resource_hint")
    return EstimationEngine(_lab(request)).eta_for_workflow(ops, resource_hint=hint)


# ---------------------------------------------------------------------------
# Acceptance preview — for the designer UI.
# ---------------------------------------------------------------------------


@app.post("/acceptance/preview")
async def acceptance_preview(body: dict[str, Any]) -> dict[str, Any]:
    rules = (body.get("rules") or {}) if isinstance(body.get("rules"), dict) else {}
    outputs = body.get("outputs") or {}
    crit = AcceptanceCriteria(rules=rules)
    verdict = evaluate_gate(crit, outputs)
    return {
        "result": verdict.result,
        "reason": verdict.reason,
        "details": {
            k: {
                "passed": d.passed,
                "operator": d.operator,
                "threshold": d.threshold,
                "actual": d.actual,
                "reason": d.reason,
            }
            for k, d in verdict.details.items()
        },
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/events")
async def events_ws(ws: WebSocket) -> None:
    mgr: ConnectionManager = ws.app.state.ws
    await mgr.connect(ws)
    try:
        # Send an initial hello so the client knows it's connected.
        await ws.send_json({"kind": "hello", "payload": {"ok": True}})
        while True:
            # We accept pings / arbitrary messages to keep the socket alive;
            # server-side push is the primary flow.
            try:
                msg = await ws.receive_text()
            except WebSocketDisconnect:
                break
            if msg == "ping":
                await ws.send_json({"kind": "pong", "payload": {}})
    finally:
        await mgr.disconnect(ws)


# ---------------------------------------------------------------------------
# Health / root
# ---------------------------------------------------------------------------


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"


@app.exception_handler(HTTPException)
async def _httpexc_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )
