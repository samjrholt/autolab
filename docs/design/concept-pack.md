# autolab — Concept Pack

*Canonical technical reference for the autonomous lab platform.
For current build decisions, see [../../CLAUDE.md](../../CLAUDE.md).
For core vocabulary, see [GLOSSARY.md](GLOSSARY.md).
For competitive positioning, see [2026-04-22-competitive-landscape.md](2026-04-22-competitive-landscape.md).*

## Thesis

The most valuable output of an autonomous lab is not any individual discovery. It is the **dataset** — linking inputs → processing → characterisation → properties with full provenance across thousands of experiments, including failures. This dataset does not exist today and cannot be generated computationally, because the properties that matter most depend on processing conditions that can only be explored through experiment.

Whoever builds the infrastructure to generate decision-grade experimental data at scale — with full provenance — has a compounding advantage that cannot be replicated computationally.

### Implications for architecture

The platform is designed around this thesis. The invariant is the data layer — full provenance, decision-grade quality, domain-agnostic schema. Everything else (synthesis methods, characterisation instruments, optimisation algorithms) is a swappable module. **The data layer is the product. The modules are replaceable.**

## What autolab produces

1. A **structured dataset** with full provenance — the primary asset.
2. Optimised candidate materials, process parameters, or designs.
3. A **validated, reproducible workflow** that can be attached to physical or computational setups.
4. Learning artefacts: planner traces, surrogate performance, uncertainty calibration, react() decision logs.

## Core execution model

Five nouns, explained in one breath:

- **Lab** — the environment: operations, resources, provenance store. A long-running service.
- **Campaign** — a search toward an objective. Owns a planner, a budget, acceptance criteria.
- **Experiment** — one attempt inside a campaign. Grouped by `experiment_id`.
- **Workflow** — the DAG of operations an experiment runs.
- **Operation** — one atomic step (synthesis, measurement, simulation, LLM interpretation).

Two decision-makers:

- **Planner** — proposes what to try next (`plan()`) and reacts to intermediate results (`react()`).
- **PolicyProvider** — the actual decision engine inside `react()`. Can be heuristic, LLM, or human. The Planner delegates; it doesn't know which is plugged in.

## Design philosophy: Simple, Intuitive, Robust

### Simple

The framework is thin. It manages the loop, wires modules together, and captures provenance. No elaborate class hierarchies.

**The Operation interface is minimal:**

```
async run(inputs) → OperationResult
```

An Operation declares:
- `capability` — scientist-named (e.g. `sintering`, `xrd`, `magnetometry`)
- `resource_kind` — what equipment it needs (e.g. `furnace`, `magnetometer`)
- `module` — version string stamped into every record

Everything else has sensible defaults. `OperationResult(status="completed", outputs={...})` is enough.

### Intuitive

ASE-style developer experience: sensible defaults, one-line component swapping, uniform interfaces. If it needs a manual, it's too complicated.

The **GUI is the primary surface**. A scientist describes their lab in plain language → Claude proposes resources and operations → the scientist reviews and approves. No YAML, no Python required for the common path.

### Robust

- Provenance is the invariant — it never breaks.
- Failures are data, not exceptions.
- The framework never changes when a module changes.
- Full-stack async; nothing blocks.
- Restart-safe by construction (rehydrates from ledger).

## Architecture

### Four layers

| Layer | Responsibility | Changes when... |
|---|---|---|
| **Provenance** | Record capture, hashing, dual-write (SQLite WAL + JSONL), annotations, lineage | Never (this is the invariant) |
| **Orchestration** | Async loop, resource scheduling, campaign management, failure recovery | Rarely (framework updates) |
| **Operations** | Synthesis, characterisation, simulation, interpretation — all swappable modules | Frequently (new science, new instruments) |
| **Planning** | Batch optimisation, experiment design, adaptive replanning via `react()` | Frequently (new algorithms, LLM advisors, human input) |

**Dependency rule:** Models ← Store ← Orchestrator ← Server/Dashboard. Operations and Planners depend only on models.

### Three nested loops

```
┌─────────────────────────────────────────────────────┐
│  OUTER: Strategic Decisions (human-guided)           │
│  "Which material system? Which composition space?    │
│   When to pivot?"                                    │
│  → Human or LLM via the Campaign objective           │
├─────────────────────────────────────────────────────┤
│  MIDDLE: Campaign Optimisation (Planner)             │
│  "What experiments next? What parameters? How to     │
│   keep equipment busy?"                              │
│  → Planner.plan() proposes batches                   │
│  → Planner.react() adapts mid-experiment             │
├─────────────────────────────────────────────────────┤
│  INNER: Operation Execution (Orchestrator)           │
│  "Run this step, capture provenance, handle          │
│   failures, check acceptance, notify."               │
│  → Resource-aware concurrent execution               │
└─────────────────────────────────────────────────────┘
```

### `react()` — the #1 differentiator

A real experimentalist does not follow a fixed plan. They see a surprise in the data and rewrite the plan. `react()` is where this happens:

1. An Operation completes and produces a Record.
2. The Planner's `react()` is called with the Record and the current plan.
3. The PolicyProvider (heuristic, LLM, or human) decides what to do.
4. The Action vocabulary: `continue`, `stop`, `add_step`, `retry_step`, `replan`, `escalate`, `branch`, `accept`, `ask_human`.
5. The scheduler reshuffles. The Console updates live.

No public autonomous-lab framework supports this cleanly. The ones that exist run fixed DAGs inside an experiment.

## Provenance

### Framework-enforced

The orchestrator wraps every operation call. Operations never write records — the framework does. A module literally **cannot** skip provenance. Failures are captured as records — they're data, not exceptions.

### Write-ahead pattern

Record is created and persisted **before** the operation runs. Survives power failures, OOM kills, hard crashes. Orphaned "running" records are detectable on restart.

### Data integrity

- **Checksums**: SHA-256 on every record. Verifiable on read.
- **Dual-write**: Every record to SQLite (WAL mode) + plain `.jsonl` backup.
- **Data lineage**: Every record references its source records via `parent_ids`. Full traceability.
- **Reproducibility metadata**: `EnvironmentSnapshot` per session (Python version, packages, git commit, seeds). Linked via `session_id`.
- **Schema versioning**: Every record has `schema_version`.

### Immutability + annotations

Records are never modified or deleted. If a result is later found to be flawed, it is annotated — not edited. The correction itself becomes provenance. "Every LLM call is a Record" — Claude's decisions are logged as `claim` Annotations with the hashed prompt, model id, and response text.

## Resource-aware scheduling

Resources are **named instances with typed capabilities**, not counted pools.

- User-level: "I have 2 arc furnaces, a SQUID, and a GPU cluster."
- Code-level: individual `Resource` objects (`arc-furnace-1`, `arc-furnace-2`, `squid-1`, `gpu-cluster`) each with a capabilities dict.
- An Operation declares its `resource_kind` and optional `requires` dict.
- The scheduler matches capabilities, acquires a free compatible instance, and releases on completion.
- Cross-campaign interleaving: operations from different campaigns share the same resource pool. The scheduler arbitrates by priority.

## LLM integration

Three Claude integrations, all optional, all offline-testable:

1. **PolicyProvider** — reads a decision context and returns an Action. Plugs into any Planner's `react()`.
2. **Planner** — proposes experiment batches given objectives, history, and tool catalogue.
3. **Campaign Designer** — free text → draft Campaign + WorkflowTemplate, for human approval.
4. **Lab Setup Assistant** — free text lab description → proposed resources and operations, for human approval.

Every Claude call is persisted as a `claim` Annotation. Offline mode (no API key) uses scripted responses so the server boots and tests pass without credentials.

## The GUI is the primary surface

Everything a scientist needs happens through the Console:

- **Overview** — "is my campaign healthy?" at a glance.
- **Campaign** — watch it unfold, intervene, pause/resume/cancel.
- **Provenance** — searchable ledger, timeline view, exports (RO-Crate, PROV).
- **Settings** — describe your lab in plain language → register resources and operations.
- **New Campaign** — describe what you want to optimise → Claude drafts a plan → approve and start.

The Console is a React app (Vite + Tailwind + framer-motion) served by the FastAPI backend. The REST + WebSocket API that powers the Console is the same API any CLI or script talks to.

## Export and interoperability

- **RO-Crate 1.1** — ELN Consortium `.eln` format. Chemotion, eLabFTW, RSpace, Kadi4Mat all import it.
- **W3C PROV-O** — standard provenance graph format.
- **Verify** — recompute every checksum from the ledger. Zero mismatches = no tampering.
- **Replay** — byte-for-byte reproduction of a campaign from cached tool outputs.

## What is explicitly NOT in scope

- Physical instrument drivers (the Operation interface is the boundary; adapters are user-provided).
- Multi-tenant auth (one Lab per process, trusted caller).
- Mobile-optimised UI (desktop/laptop first).
- Plugin system (adapters are registered at boot; hot-loading is v2).
- Provider abstraction for LLMs (Claude-native this phase; LiteLLM etc. is v2).

## Phased roadmap

### Phase 0 (current): Hackathon demo
- Framework with full provenance, scheduling, `react()`, Claude integration.
- GUI Console as primary surface.
- Computational-only demo (no physical instruments).
- Output: working demo, publishable architecture, video.

### Phase 1: Real instrument adapters
- Wire to actual lab equipment via Operation adapters.
- Gold-standard automation: standardised recipes, repeatability, QC.
- No autonomous experiment selection yet.

### Phase 2: Closed-loop optimisation
- Planner-driven experiment selection.
- Sustained throughput targets.
- Failure detection + recovery.

### Phase 3: Replication + pilots
- Replicated physical setups.
- External pilot labs.
- Standardised reporting + deliverables.
