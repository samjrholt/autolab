# 2026-04-22 — Lab-as-service + Console + LLM orchestrator iteration

Status: in progress (auto-mode iteration). Drives the build forward from a
scaffolded Python core into the three layers the demo actually needs —
service, console, and LLM orchestrator — plus time estimation and
documentation. Not a one-shot plan; the iteration adds features until
stopped.

## Goal

Close the gap between the solid Python core already in `src/autolab/` and
the demo surface described in CLAUDE.md and the README:

- A long-running FastAPI + WS service is the primary surface.
- A live, watchable Console is how the demo is watched.
- Claude is the scientist-shaped Planner / PolicyProvider / Designer.
- Time estimation makes the Gantt honest.
- A user can stand up a Lab, add resources, and launch a campaign from
  free text without writing Python.

## Non-goals for this iteration

- Real instruments. Everything runs against simulated Operations.
- A production-grade frontend build pipeline. The Console is a single
  HTML file served by FastAPI: React + Babel from ESM CDN, Tailwind from
  CDN. **Zero build step.** A Vite/Tailwind build can come later without
  changing the server contract.
- Multi-tenant auth. One Lab per process, trusted caller.
- RO-Crate / PROV export surfaces. In the backlog, not in this pass.

## Architecture (this pass)

```
┌────────────────────────────────────────────────────────────────┐
│ Browser — Campaign Console (React/Tailwind SPA, one HTML)      │
│  ├── Gantt panel (resource lanes, ETAs)                        │
│  ├── Plan tree (campaign → experiments → ops, live)            │
│  ├── Ledger feed (latest records, status, checksums)           │
│  ├── Resources + Tools manager (add / view)                    │
│  ├── Campaign launcher (free-text → design preview → submit)   │
│  └── Intervention box (free text → hashed record)              │
└──────────▲────────────────────────────────────▲────────────────┘
           │ REST                               │ WS (events)
┌──────────┴────────────────────────────────────┴────────────────┐
│ autolab.server.app — FastAPI                                   │
│  ├── /status, /resources, /tools, /workflows                   │
│  ├── /campaigns, /campaigns/{id}/*, /campaigns/design          │
│  ├── /ledger  (+ MLflow-style filter DSL)                      │
│  ├── /estimate/eta                                             │
│  ├── /records/{id}/annotate, /intervene                        │
│  └── /events  (WS)                                             │
└──────────┬─────────────────────────────────────────────────────┘
           │
┌──────────┴─────────────────────────────────────────────────────┐
│ Lab (existing) + CampaignScheduler (existing)                  │
│  └── +EstimationEngine (new): per-(op, resource) duration      │
│      model from ledger history + typical_duration_s fallback   │
└──────────┬─────────────────────────────────────────────────────┘
           │
┌──────────┴─────────────────────────────────────────────────────┐
│ autolab.agents.claude (new)                                    │
│  ├── ClaudePolicyProvider — decide() over DecisionContext      │
│  ├── ClaudePlanner       — plan() proposes next batch          │
│  └── CampaignDesigner    — free text → Campaign + Workflow     │
└────────────────────────────────────────────────────────────────┘
```

Every Claude call lands as a `claim` Annotation on the Record that
prompted it; prompt + model id + response are persisted. "Every LLM
call is a Record" from the competitive-landscape doc stays honoured.

## Design decisions (this pass)

1. **One HTML, no bundler.** The Console ships as a Jinja-rendered
   `index.html` that pulls React, React-DOM, Babel-standalone, and
   Tailwind from public CDNs. Components are written in JSX inside one
   `<script type="text/babel">`. Pros: ships today, no node, easy to
   read. Cons: bigger first paint, CDN dependency. Revisited in a later
   iteration; the REST/WS contract does not change.
2. **Server state is the Lab, not a DB layer.** The FastAPI process
   holds the `Lab` instance. Everything persistent lives in the Ledger
   (SQLite WAL + JSONL) that the Lab already owns. Restart-safe by
   construction.
3. **Event fan-out is push-only.** WS clients receive events;
   server-side filtering is simple keyword match by `kind`. The client
   reconciles its own state (last-N records, resource table, plan
   tree). No subscription protocol yet.
4. **EstimationEngine is a read-only overlay.** It reads the Ledger to
   build a per-(operation, resource_name) median-duration table;
   fallback is `ToolDeclaration.typical_duration_s`; fallback-of-
   fallback is a constant. Not persisted — recomputed at boot and
   incrementally as records complete.
5. **Claude integration is optional.** Server boots without an
   `ANTHROPIC_API_KEY`; any endpoint that needs Claude returns 503 with
   a clear message. Tests run offline — Claude providers have an
   `offline=True` mode that uses a scripted canned response for each
   hook.
6. **Free-text Campaign design is a two-step contract.** `POST
   /campaigns/design` returns a *proposed* Campaign + WorkflowTemplate
   JSON plus a human-readable explanation. `POST /campaigns` actually
   submits. The human always approves before anything runs. This
   matches "goal is immutable once a Campaign starts" from CLAUDE.md.
7. **Adding a Resource from the UI = POST /resources with JSON.**
   Backed by the same validation `Lab.register_resource` runs in
   Python. A second form accepts a YAML paste for parity with the CLI.
8. **Docs live under `docs/guides/`** and cover: quickstart, adding a
   Resource, adding an Operation, designing a Campaign in free text,
   architecture overview. Each guide is task-shaped, not reference.

## Invariant preservation

- Operations still never write Records — the Orchestrator does.
- Every Record still hashed, append-only, write-ahead. Server does not
  touch the Ledger directly except through `Lab.ledger`.
- `react()` Action vocabulary stays closed. Claude's PolicyProvider
  emits Actions; it does not invent new ones.
- Campaign objective stays immutable for the life of a Campaign.
- Goal mutation is "stop and start a new Campaign", not an edit.

## What lands in this pass (acceptance-testable)

- `uvicorn autolab.server.app:app` boots; `/status` returns `{}`.
- Console at `/` renders, connects to `/events`, updates live.
- `POST /resources`, `/tools/register`, `/workflows`, `/campaigns` all
  round-trip against an in-memory Lab.
- `GET /ledger?filter=tags.foo='x' and outputs.sensitivity>=1.5`
  returns matching Records.
- `GET /estimate/eta?campaign_id=…` returns per-step ETA projections.
- `POST /campaigns/design` returns a draft Campaign + WorkflowTemplate
  given free text, available tools, and resources — gated on
  `ANTHROPIC_API_KEY`.
- `autolab.agents.claude.ClaudePolicyProvider` plugged into any
  existing Planner drives `react()`; behind it, prompts and responses
  are persisted.
- Example workflow (`examples/superellipse_sensor`) runs through the
  server end-to-end with the Console watching.
- Guides under `docs/guides/` cover the five everyday tasks.

## What is deliberately deferred

- Hysteresis / PXRD / structure physics cards in the Console —
  placeholder panel that renders the most recent Record's `artefacts`
  generically. Domain visualisations come after the core loop is
  watchable.
- RO-Crate / PROV export.
- Segments (LabIMotion-style typed metadata blocks).
- `annotation_extract` Interpretation Operation.
- React/Vite/Tailwind build pipeline.
- Authentication / multi-lab.

## Risks

- Single-process Lab + WS scales to a handful of browser clients — fine
  for the demo, not for production.
- Claude providers depend on network. Tests stub them; the demo path
  tolerates timeouts with a visible error in the Console rather than
  freezing the campaign.
- Parameter-space inference from free text is imperfect — the Designer
  always returns a preview for human approval; nothing runs silently.
