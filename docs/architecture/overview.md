# Architecture overview

A top-down tour of how the pieces fit. Read [CLAUDE.md](../../CLAUDE.md)
first for the *why*; this page is the *how*.

## The three external layers

As [white-paper-2.md](../design/white-paper-2.md) frames it, a caller
sees three layers:

1. **Brain** — Claude Opus 4.7 as Planner and PolicyProvider, reading
   Records and rendered figures.
2. **Hands** — Capability-named tools behind one MCP gateway, including
   Interpretation Operations that call Claude to read a figure and
   return a structured Claim.
3. **Ledger** — Append-only, hashed, write-ahead Record store.

## The five internal layers

| Layer | Module(s) | Role |
|---|---|---|
| Interface | [`autolab.server.app`](../../src/autolab/server/app.py), [`static/index.html`](../../src/autolab/server/static/index.html) | FastAPI + WS service, Console SPA. |
| Orchestration | [`autolab.orchestrator`](../../src/autolab/orchestrator.py), [`autolab.scheduler`](../../src/autolab/scheduler.py), [`autolab.workflow`](../../src/autolab/workflow.py), [`autolab.campaign`](../../src/autolab/campaign.py) | Multi-campaign scheduling, provenance contract, DAG execution. |
| Expertise | [`autolab.planners`](../../src/autolab/planners), [`autolab.agents.claude`](../../src/autolab/agents/claude.py) | BO / Optuna / heuristic planners + Claude PolicyProvider, Planner, CampaignDesigner. |
| Tools | [`autolab.tools.registry`](../../src/autolab/tools/registry.py), [`autolab.operations.base`](../../src/autolab/operations/base.py) | Capability-named registry, Python-first Operations, YAML declarations. |
| Provenance | [`autolab.provenance.store`](../../src/autolab/provenance/store.py), [`autolab.models`](../../src/autolab/models.py) | SQLite + JSONL Ledger, typed Records, hashing. |

## Data flow — one Operation step

```
Scientist → POST /campaigns                 (REST)
           │
Server  →  Lab.register_campaign → Scheduler.submit
           │
Scheduler → Campaign.plan()   → Planner   → ProposedStep[]
           │
For each step:
  Orchestrator.run_step:
    1. write-ahead Record{status=pending}         → Ledger
    2. ResourceManager.acquire(kind, requires)    → Resource
    3. Record{status=running, resource_name=…}    → Ledger
    4. Operation.run(inputs, ctx)                 → OperationResult
    5. evaluate acceptance                         → GateVerdict
    6. Record{status=completed, outputs, gate…}   → Ledger
    7. publish event                              → EventBus → WS
           │
Campaign.react()  → Planner.PolicyProvider.decide → Action
           │
           ├─ accept  → Campaign ends.
           ├─ retry_step → re-enqueue with same inputs.
           ├─ escalate → park Campaign, await human resolution.
           └─ continue → next plan() cycle.
```

Every transition (`pending → running → completed/failed`) is a separate
SQLite + JSONL row. The JSONL file is the crash-safe secondary log;
SQLite is the index for fast queries.

## Write invariants (non-negotiable)

1. **Only the Orchestrator writes Records.** Operations return a
   result; the Orchestrator wraps it.
2. **Every Record carries a SHA-256 checksum.** `autolab.ledger.verify_all()`
   recomputes them.
3. **Append-only.** Once a Record is `completed|failed|soft_fail` it
   cannot be re-opened. Corrections land as Annotations.
4. **Write-ahead.** A crash mid-Operation leaves a `pending` or
   `running` breadcrumb, never a missing row.
5. **Tool declaration hash in every Record.** Editing a tool's YAML or
   `Inputs` model changes the hash — provenance-visible.
6. **Claim Records for every LLM call.** Annotations carry the
   model id, hashed prompt, and response.

## Scheduler model

`CampaignScheduler.run()` spawns one `asyncio.Task` per Campaign. The
tasks share the Lab's `ResourceManager`; each Operation that declares a
`resource_kind` competes with every other Operation (in any Campaign)
for a compatible free instance. Priority is an integer on each
Campaign; lower = more urgent.

This is the competitive-landscape doc's beat #2 — cross-experiment
interleaving on shared resources, within and across Campaigns, with the
Console's Gantt as the live projection of what the ResourceManager is
doing.

## Estimation and ETA

`EstimationEngine` (see [`autolab.estimation`](../../src/autolab/estimation.py))
reads the Ledger and builds a per-`(operation, resource_name)` duration
table from measured `duration_ms`. Fallback chain: measured for the
exact pair → measured for the operation on any resource → declared
`typical_duration_s` → a module-level default.

`eta_for_campaign(campaign_id)` sums pending + remaining-running
durations per resource and returns `max(per_resource_sums)` as the
projected finish time. The Console polls this every four seconds for
every running Campaign.

## Claude integration points

| Where | Class | Writes to ledger? |
|---|---|---|
| `Planner.react()` | `ClaudePolicyProvider` | Claim Annotation on the Record that triggered it. |
| `Planner.plan()` | `ClaudePlanner` | Claim Annotation on `planner:<campaign_id>` pseudo-record. |
| `POST /campaigns/design` | `CampaignDesigner` | Claim Annotation on `designer:draft` pseudo-record. |

All three accept `offline=True` (or auto-detect a missing
`ANTHROPIC_API_KEY`) and return deterministic scripted responses so the
test suite runs without credentials.

## Event bus → WebSocket

`autolab.events.EventBus` is a tiny in-process fan-out. The server
subscribes one `asyncio.Queue` at startup and broadcasts every
incoming Event to every connected `/events` WebSocket client. No
per-client filtering; the browser reconciles its own view state.

Event kinds emitted today:

- `record.pending`, `record.running`, `record.completed`, `record.failed`, `record.soft_fail`
- `campaign.started`, `campaign.finished`, `campaign.escalation_required`, `campaign.escalation_resolved`
- `resource.registered`, `resource.unregistered`

## Replayability

`autolab replay <campaign-hash>` (planned CLI entry point) reads the
ledger's frozen Record inputs + `tool_declaration_hash` + session
`EnvironmentSnapshot` and re-runs the Operations against their cached
outputs. The SHA-256 of every replayed Record must match the original.
This is the credibility anchor the competitive landscape doc calls out
as autolab's differentiator against every ELN, tracker, and prior
autonomous-lab framework.
