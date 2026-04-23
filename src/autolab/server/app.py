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
``this-pc`` — the host machine — auto-registered before the mode runs.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
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
    kind: str
    capabilities: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    asset_id: str | None = None
    typical_operation_durations: dict[str, int] = Field(default_factory=dict)


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
    # Optional: an inline workflow to execute deterministically when the planner is "none".
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


class LabSetupRequest(BaseModel):
    text: str
    previous: dict[str, Any] | None = None
    instruction: str | None = None


class LabSetupApplyRequest(BaseModel):
    resources: list[dict[str, Any]] = Field(default_factory=list)
    operations: list[dict[str, Any]] = Field(default_factory=list)


class BootstrapApplyRequest(BaseModel):
    mode: str


class EntityDesignRequest(BaseModel):
    """Iterative-refinement request for per-entity designers (resource / tool / workflow)."""

    text: str = ""
    previous: dict[str, Any] | None = None
    instruction: str | None = None


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
            _Path(__file__).resolve().parents[3]
            / "examples"
            / "superellipse_sensor"
            / "tool.yaml"
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
    from pydantic import BaseModel as _BM

    from autolab.models import OperationResult
    from autolab.models import Resource as _Resource
    from autolab.operations.base import Operation

    class DemoQuadratic(Operation):
        capability = "demo_quadratic"
        resource_kind = "computer"
        module = "demo_quadratic.v1"
        typical_duration = 2

        class Inputs(_BM):
            x: float
            target: float = 0.5

        class Outputs(_BM):
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
    setattr(
        lab,
        "_bootstrap_diagnostics",
        {
            "mode": mode,
            "error": error,
        },
    )


def _apply_bootstrap_mode(lab: Lab, mode: str) -> None:
    _set_bootstrap_diagnostics(lab, mode=mode)
    log.info("bootstrap mode: %r  (cwd=%s, sys.path[0]=%s)", mode, Path.cwd(), sys.path[0] if sys.path else "(empty)")
    if mode in ("none", ""):
        # No default tools, no default workflows. "this-pc" is the only
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
        except Exception as exc:  # noqa: BLE001
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            log.warning("superellipse bootstrap failed (%s) — falling back to empty", exc)
            return
    if mode == "mammos":
        try:
            _bootstrap_mammos(lab)
            return
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            import traceback as _tb
            log.error("sensor_shape_opt bootstrap FAILED — %s\n%s", exc, _tb.format_exc())
        return
    if mode == "all":
        # Register both example bundles so the Console can run either.
        for name, fn in (("superellipse", _bootstrap_superellipse), ("mammos", _bootstrap_mammos)):
            try:
                fn(lab)
            except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            _set_bootstrap_diagnostics(lab, mode=mode, error=str(exc))
            raise
        return
    _set_bootstrap_diagnostics(lab, mode=mode, error=f"unknown bootstrap mode {mode!r}")
    log.warning("unknown AUTOLAB_BOOTSTRAP mode %r — booting empty", mode)


def _auto_register_this_pc(lab: Lab) -> None:
    """Register the host machine as a default ``this-pc`` resource.

    Idempotent: if a resource named ``this-pc`` already exists in the
    ResourceManager (restart case — rehydrated from the ledger), this is a
    no-op. Every fresh Lab boots with exactly one resource so the Console
    is never empty on first run.
    """
    import platform

    existing = {r.name for r in lab.resources.list()}
    if "this-pc" in existing:
        return
    caps: dict[str, Any] = {
        "hostname": platform.node() or "localhost",
        "os": f"{platform.system()} {platform.release()}",
        "cpu_count": os.cpu_count() or 1,
        "python": platform.python_version(),
    }
    lab.register_resource(
        Resource(
            name="this-pc",
            kind="computer",
            capabilities=caps,
            description="The machine autolab is running on. Auto-registered at boot.",
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
        # Cooperative cancellation — never .cancel() a task mid-SQLite-write
        # or Windows raises an access violation in the worker thread.
        for cid, state in list(scheduler._campaigns.items()):
            if state.status in ("running", "paused", "queued"):
                try:
                    await scheduler.cancel(cid)
                except Exception:
                    pass
        # Wait for the scheduler.run() task to finish naturally.
        try:
            await asyncio.wait_for(sched_task, timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            pass
        # Drain any in-flight Claude claim persistence tasks before the Ledger
        # closes — otherwise a SQLite worker thread can race with Lab.close().
        await drain_pending_claims()
        # Now it's safe to tear down the event bridge.
        bridge.cancel()
        try:
            await bridge
        except Exception:
            pass
        lab.close()


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
        "campaigns": scheduler.status(),
        "workflows": [w.model_dump(mode="json") for w in lab._workflows.values()],
        # UI exposes only these two; example bootstraps may register more in
        # the registry but they stay out of the dropdown to keep the MVP focused.
        "planners_available": ["optuna", "claude"],
        "estimation_summary": eng.summary(),
        "claude_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


def _tool_row(decl: Any) -> dict[str, Any]:
    return {
        "name": decl.name,
        "capability": decl.capability,
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


@app.get("/resources")
async def list_resources(request: Request) -> list[dict[str, Any]]:
    return _lab(request).resources.status()


@app.post("/resources")
async def add_resource(body: ResourceRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    try:
        resource = Resource(**body.model_dump())
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


@app.post("/tools/register-yaml")
async def register_yaml_tool(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Register a YAML/JSON tool declaration POSTed as JSON.

    ``name`` defaults to ``capability`` if omitted — both fields refer to the
    same scientist-named identifier; the ToolDeclaration loader requires them.
    """
    lab = _lab(request)
    # Normalise: name and capability are the same identifier in our model.
    if "capability" in body and "name" not in body:
        body = {**body, "name": body["capability"]}
    elif "name" in body and "capability" not in body:
        body = {**body, "capability": body["name"]}
    try:
        decl = lab.register_tool_dict(body)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return _tool_row(decl)


@app.post("/tools/register")
async def register_simple_tool(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Register a Tool from a simple JSON description (no adapter path required).

    Creates a dynamic stub Operation class whose outputs match the declared
    schema.  Meant for the console's Tool builder; scientists can later
    replace the stub with a real adapter by registering a YAML declaration
    at the same capability name after unregistering.
    """
    lab = _lab(request)
    if "capability" not in body:
        raise HTTPException(400, "capability is required")
    if lab.tools.has(body["capability"]):
        raise HTTPException(
            400, f"tool {body['capability']!r} already registered"
        )
    try:
        _register_dynamic_operation(lab, body)
    except Exception as exc:  # noqa: BLE001 — surface a clean error
        raise HTTPException(400, f"failed to register tool: {exc}") from exc
    return {"ok": True, "capability": body["capability"]}


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
    except Exception as exc:  # noqa: BLE001 — surface a clean error
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
            acceptance=(
                AcceptanceCriteria(**body.acceptance) if body.acceptance else None
            ),
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
        )
    if kind == "optuna":
        if "search_space" not in config:
            raise HTTPException(
                400,
                "Optuna planner requires a 'search_space' in planner_config. "
                "Example: {\"operation\": \"my_op\", \"search_space\": {\"x\": "
                "{\"type\": \"float\", \"low\": 0, \"high\": 10}}}",
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
        known = list_planners() + ["claude"]
        raise HTTPException(
            400,
            f"unknown planner {kind!r}. Supported: {sorted(set(known))}",
        ) from None
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"planner {kind!r} config invalid: {exc}") from exc


@app.post("/campaigns")
async def submit_campaign(body: CampaignRequest, request: Request) -> dict[str, Any]:
    lab = _lab(request)
    scheduler = _scheduler(request)
    try:
        campaign = Campaign(
            name=body.name,
            description=body.description,
            objective=Objective(**body.objective),
            acceptance=(AcceptanceCriteria(**body.acceptance) if body.acceptance else None),
            budget=body.budget,
            parallelism=body.parallelism,
        )
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
    if body.autostart:
        # If a scheduler loop is already running, _launch() will pick up the new
        # state on the next tick. But if the user just booted the server, the
        # scheduler.run() task may have already exited (no work). Relaunch if so.
        if state._task is None:
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
    if state.status not in ("queued",):
        # Already started / running / terminal — report current state without error.
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
    result = designer.design(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "campaign": result.campaign_json,
        "workflow": result.workflow_json,
        "notes": result.notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
        "prompt_sha256": result.raw.prompt_hash,
    }


# ---------------------------------------------------------------------------
# Lab setup — LLM-assisted onboarding
# ---------------------------------------------------------------------------


@app.post("/lab/setup")
async def design_lab_setup(body: LabSetupRequest, request: Request) -> dict[str, Any]:
    """Describe your lab in plain language → Claude proposes resources and operations."""
    lab = _lab(request)
    designer = LabSetupDesigner(lab=lab, transport=ClaudeTransport())
    result = designer.design(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "resources": result.resources,
        "operations": result.operations,
        "workflow": result.workflow,
        "notes": result.notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/resources/design")
async def design_resource(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    """Propose (or refine) a single Resource from a natural-language description."""
    lab = _lab(request)
    designer = ResourceDesigner(lab=lab, transport=ClaudeTransport())
    result = designer.design(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "resource": result.resource,
        "notes": result.notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/tools/design")
async def design_tool(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    """Propose (or refine) a single Tool declaration from a natural-language description."""
    lab = _lab(request)
    designer = ToolDesigner(lab=lab, transport=ClaudeTransport())
    result = designer.design(
        body.text,
        previous=body.previous,
        instruction=body.instruction,
    )
    return {
        "tool": result.tool,
        "notes": result.notes,
        "model": result.raw.model,
        "offline": result.raw.offline,
    }


@app.post("/workflows/design")
async def design_workflow(body: EntityDesignRequest, request: Request) -> dict[str, Any]:
    """Propose (or refine) a single WorkflowTemplate from a natural-language description."""
    lab = _lab(request)
    designer = WorkflowDesigner(lab=lab, transport=ClaudeTransport())
    result = designer.design(
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

    return {
        "ok": len(errors) == 0,
        "registered_resources": registered_resources,
        "registered_operations": registered_operations,
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
    except Exception as exc:  # noqa: BLE001
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

    Creates a simple Operation subclass that returns mock outputs matching
    the declared schema. The scientist can later replace this with a real
    adapter that talks to their actual equipment.
    """
    capability = spec["capability"]
    resource_kind = spec.get("resource_kind")
    module = spec.get("module", f"{capability}.stub.v1")
    produces_sample = spec.get("produces_sample", False)
    destructive = spec.get("destructive", False)
    duration = spec.get("typical_duration_s", 5)
    output_schema = spec.get("outputs", {})

    # Build a simple Operation class dynamically
    from autolab.operations.base import Operation, OperationContext

    class DynamicOp(Operation):
        pass

    DynamicOp.capability = capability
    DynamicOp.resource_kind = resource_kind
    DynamicOp.module = module
    DynamicOp.produces_sample = produces_sample
    DynamicOp.destructive = destructive
    DynamicOp.typical_duration = duration

    async def _run(self: Any, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
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

    if not lab.tools.has(capability):
        lab.register_operation(DynamicOp)


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
            try:
                rec = lab.ledger.get(esc.record_id)
                if rec:
                    row["operation"] = rec.operation
                    row["outputs"] = rec.outputs
            except Exception:  # noqa: BLE001
                pass
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
    except Exception as exc:  # noqa: BLE001 — bubble up with a friendly status
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "annotation_id": ann.id}


@app.get("/export/ro-crate")
async def export_ro_crate(
    request: Request, campaign_id: str | None = None
) -> dict[str, Any]:
    from autolab.export import to_ro_crate

    return to_ro_crate(_lab(request), campaign_id=campaign_id)


@app.get("/export/prov")
async def export_prov(
    request: Request, campaign_id: str | None = None
) -> dict[str, Any]:
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
        "bootstrap_mode": diag.get("mode") or os.environ.get("AUTOLAB_BOOTSTRAP", "demo_quadratic (default)"),
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
