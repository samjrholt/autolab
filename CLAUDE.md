# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state of the repo

The hackathon build kicks off 21 Apr 2026. The repo is scaffolded (Python package + pixi environment + docs tree) but no framework code is written yet. Design documents live under [docs/design/](docs/design/); architecture docs (as they get written) live under [docs/architecture/](docs/architecture/); example-workflow docs live under [docs/examples/](docs/examples/).

Design contract for the forthcoming `autolab` package:

- [docs/design/autolab-ideas-foundation.md](docs/design/autolab-ideas-foundation.md) — the load-bearing design synthesis. Sections to re-read on every major decision: §2 (the five moats), §3 (Operation / Planner abstractions), §6 (provenance), §18 (world-leading checklist), §21 (locked decisions), §21a (Anthropic defaults to disable). Skill references throughout are superseded by 2026-04-22-interpretations-and-metadata.md.
- [docs/design/hackathon-plan.md](docs/design/hackathon-plan.md) — **partially superseded.** §4 (repo layout), §5 (six-day schedule), §10 (risk register), §11 (post-submission follow-through) are still-useful rough drafts. §1 (one-liner), §3 (architecture table), §7 (3-min demo script), and the GMR-sensor framing throughout are **overridden by CLAUDE.md's "Ambition level," "Scope discipline," and "First cool example workflow" sections**. Skill references superseded by 2026-04-22-interpretations-and-metadata.md.
- [docs/design/white-paper-2.md](docs/design/white-paper-2.md) — the thesis. Only touch if the framing changes.
- [docs/design/GLOSSARY.md](docs/design/GLOSSARY.md) — canonical terms. Use these exactly; do not coin synonyms.
- [docs/design/scenarios.md](docs/design/scenarios.md) — real-world scientist-workflow scenarios the framework must handle (pressure tests, not domain contracts).
- [docs/design/2026-04-22-interpretations-and-metadata.md](docs/design/2026-04-22-interpretations-and-metadata.md) — 2026-04-22 framing correction (autonomous lab, not record with agent attached), removal of the Skill abstraction in favour of Interpretation Operations, and the adopted metadata-capture pattern (template-per-capability + tags + annotations + optional LLM post-hoc extractor).
- [docs/design/2026-04-22-competitive-landscape.md](docs/design/2026-04-22-competitive-landscape.md) — survey of ELNs (Benchling, eLabFTW, Chemotion/LabIMotion), provenance standards (PROV, RO-Crate, CWL), ML trackers (MLflow, W&B), and autonomous labs (AlabOS, ChemOS, Coscientist, BayBE, ECL). What to leverage from each, where autolab beats them, and the four positioning one-liners. Consult before writing any marketing prose, the README opening, or the demo voiceover.

Treat these files as the spec. Do not silently "improve" them while coding — if an idea changes, update the doc in the same commit as the code.

## The one-sentence frame

autolab is **an autonomous lab with provenance as its foundation**. Externally it is three layers — **Brain** (Claude Opus 4.7 as Planner and PolicyProvider, reading records and rendered figures), **Hands** (capability-named tools and operations on typed resources, including LLM-backed *Interpretation Operations*), **Ledger** (append-only hashed provenance with tags + annotations on every record). Internally it is five layers: Interface / Orchestration / Expertise / Tools / Provenance. The deliverable of a Campaign is goal-shaped (a material, a trend, a design); the ledger is the substrate that makes the autonomy trustworthy and the evidence compound. Every architectural choice must survive the substitution: *the record is the invariant, the agent is replaceable*. The framework scope is **experimental + computational science**; the current hackathon demo path is **computational-only**. See [docs/design/2026-04-22-interpretations-and-metadata.md](docs/design/2026-04-22-interpretations-and-metadata.md) for the 2026-04-22 framing correction and the removal of the "Skill" abstraction.

## Ambition level: hackathon-scoped, world-leading-measured

This is a 6-day solo build, but the bar is **beyond state of the art, not beyond a weekend project**. Resolve the tension by making the core *conceptually simple* and the *consequences* impressive:

- **Conceptually simple.** A handful of primitives — **Lab** (running service), **Resource** (capacity-limited thing), **Operation** (one atomic step), **Sample** (the physical or digital thing Operations act on), **Planner** (what picks the next step), **Record** (append-only hashed entry), **Action** (what `react()` returns). That is it. A scientist should be able to describe the whole model in one breath.
- **Framework-first; domain-agnostic by construction.** The core knows nothing about magnetism, catalysis, protein design, or data pipelines. The vertical is a set of registered Operations and Tools — it is **not** baked into the framework. We will wire up a magnetism example workflow because Sam's expertise is there, but the framework must not depend on it. "Examples are examples; the framework is the framework."
- **Demo constraint.** The framework is for experimental + computational science, but the hackathon demo is computational-only. Use VM / CPU / GPU / simulator resources in the narrated path. Physical lab resources remain part of the interface shape, not the primary demo story this week.
- **World-leading on four axes, in priority order:**
  1. **`react()` — adaptive mid-experiment replanning.** The #1 beat. A real experimentalist does not follow a fixed plan — they see a surprise in the data and rewrite the plan. No public autonomous-lab framework supports this cleanly; the ones that exist run fixed DAGs inside an experiment. Demo must show it unambiguously.
  2. **Resource-aware, cross-experiment, cross-campaign scheduling with live visualisation.** The demo flex. Operations from different experiments interleave on shared typed resources (arc furnaces, tube furnace, SLURM partition, SQUID, …) while the plan-tree and resource-lane panels update in real time. A scientist watches the scheduler *do work* and recognises their own day. The reference prior art does multi-campaign scheduling but not cross-experiment interleaving within a campaign — this is where we out-build the state of the art.
  3. **Framework-enforced, write-ahead, hashed, append-only provenance, with byte-for-byte replay.** Integrity plumbing that never breaks. Per-record SHA-256 is the integrity primitive; `autolab replay <campaign-id>` is the credibility anchor. (Campaign-level Merkle roots are a nice-to-have plumbing detail — not a pitched feature; scientists don't care about cross-lab cryptographic mergeability.)
  4. **Opus 4.7 vision as `react()`'s sensory input.** The mechanism by which `react()` reads a PXRD pattern or a hysteresis loop rendered as PNG and decides what to do next. Vision is not its own demo beat — it is what makes the `react()` beat feel like a scientist, not a script.
- **Hackathon discipline.** We do not need every feature by Sunday. We need the framework clean, the `react()` loop sharp, the scheduler doing visibly clever things, and *one* cool example workflow running real physics on top. Breadth of the platform is a claim backed by the interface shape; the demo's depth lives in one example.

If a proposed change makes the code more impressive but the concept more tangled, it is the wrong change. If it lands a world-leading beat without adding architectural complexity, it is the right one.

## The Lab is a service, not a script

One big shift from the hackathon-plan CLI framing: **the Lab itself is a long-running FastAPI server.** It is an institution, not an invocation. Consequences for the architecture:

- **One `Lab` instance = one persistent service.** Boot it once; it stays up. Restart-safe (state rehydrates from the ledger).
- **Resources, Tools, Workflows, Campaigns are registered against a running Lab** via REST + WebSocket. The same endpoints the React GUI talks to are the same endpoints the CLI talks to — the CLI is a thin client, not a separate code path.
- **The ledger belongs to the Lab**, not to a campaign invocation. Campaigns come and go; the ledger accumulates. This is what makes the dataset-as-moat story honest.
- **Multi-campaign from day 0.** Campaign is a first-class concept within a Lab, not the top-level entry point. A Lab can host many campaigns sharing resources; the scheduler arbitrates across them.
- **Typical HTTP surface** (names illustrative, not final — confirm during build):
  - `POST /resources` — register a named resource and its capacity.
  - `POST /tools` — register a capability (YAML declaration) and its adapter.
  - `POST /workflows` — register a workflow template (DAG of operations).
  - `POST /campaigns` — start a campaign (goal, planner, constraints, budget).
  - `POST /campaigns/{id}/intervene` — human intervention; body becomes a hashed record.
  - `GET /ledger?campaign=…` — query records.
  - `WS /stream` — subscribe to the event feed (records + agent messages + plan-tree diffs).
- **Consequence for the demo:** the video shows the GUI driving the Lab; the CLI is a bonus for the judges reading the README, not the primary surface.

## Non-negotiable invariants

These are architectural constraints, not preferences. Code that violates them is a bug.

1. **Framework-enforced provenance.** Operations never write records directly — the orchestrator wraps every call and persists a write-ahead record *before* the operation runs. Failures are records with `status: "failed"`, not exceptions. A module must be **incapable** of skipping provenance.
2. **Append-only, hashed, write-ahead.** Every Record gets a SHA-256; Records are never mutated — corrections are new Records with Annotations pointing at what they correct. Dual-write to SQLite (WAL) + `.jsonl`. Campaign-level Merkle roots are plumbing we *may* add, not a headline feature.
3. **The two work-bearing abstractions are Operation and Planner.** Every experimental or computational action is an **Operation** (`run(inputs) → OperationResult`, declares its Resource, declares whether it produces a Sample). Every decision-maker is a **Planner** (`plan(history, resources)` for batch proposals + `react(record, plan)` for mid-experiment adaptation). Their *decisions* can be routed through an interchangeable **PolicyProvider** (heuristic, LLM, human). Do not add a third work-bearing abstraction.
4. **Capability-named tools, not library-named.** `micromagnetics_hysteresis`, not `ubermag_hysteresis`. One-way door — chosen at day 0. One YAML declaration per capability in `autolab/tools/`, one MCP gateway in `autolab/mcp/gateway.py`. Declaration SHA-256 goes into every record.
5. **Diagnoses are claims, not facts.** Interpretation Operations (e.g. `hysteresis_interpret`, `pxrd_interpret`) return claims with confidence and a recommended validation step, logged as their own Claim Records, never written as ground-truth fields on the measurement Record. The validation run links back via `parent_ids`.
6. **Surrogates are never silently substituted.** If a surrogate answered, the record's `module` field says so (e.g. `MicromagneticsSurrogate v0.1`).
7. **Apache-2.0, public from commit 1.** Hackathon rule. No proprietary bundling.
8. **Anthropic defaults we disable** (see §21a): auto-compaction of conversation history, agent-rewritable memory, `bypassPermissions` / tool auto-approval. Every tool call goes through the gateway which logs before it calls.

## Locked decisions (do not relitigate)

From ideas-foundation §21 plus the 2026-04-21 ideation pass:

- **Framework-first.** No vertical is locked into the framework code. The vertical is a *registered set of Operations + Tools* (some of which are Interpretation Operations calling Claude); it can be swapped by editing YAML and wiring an adapter. CLAUDE.md, the Core abstractions in GLOSSARY.md, and scenarios.md stay domain-neutral.
- **Scope: experimental + computational science.** The pitch is autonomous science. Not a general workflow engine, not a coding agent, not a BPMN tool.
- **`react()` is the #1 world-leading axis.** Vision is the mechanism `react()` uses to read rendered figures; it is not its own beat.
- **Resource-aware scheduling + live visualisation is the #2 axis and the demo's visible hero.** The Console shows resource lanes, the plan tree mutating, and cross-experiment interleaving as it happens.
- **Resources are named instances with typed capabilities, not counted pools.** User-level input is "2 × arc furnace, 1 × tube furnace, 1 × SLURM partition"; at the code level these are individual `Resource` objects (`arc-furnace-1`, `arc-furnace-2`, `tube-furnace-A`, `slurm-partition-gpu`) each with a capabilities dict (`{max_temp: 2000, volume_mL: 5}`, `{gpu_count: 4, mem_gb: 80}`). An Operation declares its `resource` type and any capability requirements; the scheduler matches and acquires one free compatible instance.
- **Lab-as-FastAPI-service** (see section above). No one-shot CLI-only mode.
- **Exactly one Campaign subagent** in the demo, visibly context-isolated from the Principal. More looks like theatre.
- **No plugin system this week.** External tools are wrapped by autolab-owned adapters, declared in YAML, exposed through one MCP gateway.
- **Claude-native this week.** Managed Agents, MCP. Provider abstraction (LiteLLM etc.) is v2. Anthropic's `SKILL.md` format is not an autolab-level concept; if it appears inside an Interpretation Operation's adapter as an implementation detail that is fine, but it does not leak into the autolab model.
- **Vision inputs = PNG** of rendered figures (hysteresis loops, PXRD patterns, structure renderings). Opus 4.7 reads the image like a scientist.
- **Dependency rule:** Models ← Store ← Orchestrator ← Dashboard. Operations and Planners depend only on models; an Operation never imports the Orchestrator.
- **`react()` Action vocabulary:** `continue`, `stop`, `add_step`, `retry_step`, `replan`, `escalate`, `branch`, `accept`, `ask_human`. Each carries a `reason` string persisted in the Record's `decision` field. Do not add new Action types without updating [GLOSSARY.md](GLOSSARY.md) first.
- **Interpretation Operation count is not locked.** The exact set depends on the example workflow we pick. Rule of thumb: at most five, biased toward figure/record readers that return a Claim with confidence. Each is a capability with a `tool.yaml` and an adapter, same as any other Operation.
- **PolicyProvider is a distinct abstraction from Planner.** Planner = propose a batch (`plan()`) and structure a reactive decision (`react()`). PolicyProvider = actually decide (`decide(DecisionContext) → Action`). The Planner delegates to the PolicyProvider inside `react()`. Heuristic, LLM, and human PolicyProviders are interchangeable; the Planner does not know or care which is plugged in.
- **AcceptanceCriteria format: dict-of-rules.** Each Campaign and Workflow step carries an optional `AcceptanceCriteria` shaped as `{output_key: {operator: threshold, …}, …}` — e.g. `{"Hc_kA_per_m": {">=": 800}, "phase_purity": {">=": 0.9}}`. Operators supported: `>=`, `<=`, `>`, `<`, `==`, `in`, `not_in`. The evaluator returns `pass` / `soft-fail` / `fail` and a reason string; the `reason` is what the PolicyProvider reads.
- **Console: two panels side by side.** Left = resource-lane Gantt (each Resource instance is a lane; Operations are pills). Right = plan tree (Campaign → Experiments → Operations, with pill status matching the Gantt). Both panels feed off the same WebSocket event stream; they are different projections of the same ledger state. Live physics panels appear as third-row cards below when a relevant Operation completes.
- **Goal mutation is not a framework operation.** A Campaign's objective is immutable for the life of the Campaign. If a scientist wants to change what they're optimising for, they stop the current Campaign and start a new one. No auto-fork, no mutate-and-annotate. This keeps the `react()` action vocabulary closed and the ledger semantics clean.

## First cool example workflow (leaning, not locked)

Per the 2026-04-21 ideation pass, the leading candidate for the "one cool example" the demo runs is a **multiscale hard-magnet pipeline** modelled on the MaMMoS demonstrator chain:

1. **Structure relaxation** via an MLIP (MACE / CHGNet / MatterSim) — cheap fast relax of a candidate crystal structure.
2. **Intrinsic magnetic parameters at 0 K** via `mammos-dft` or a pre-trained `mammos-ai` surrogate — Ms, K1, A_ex.
3. **Temperature-dependent intrinsics** via `mammos-spindynamics` (Kuzmin fit) — Ms(T), K1(T), Tc.
4. **Hysteresis + coercivity Hc** via `mammos-mumag` finite-element micromagnetics on a realistic grain structure.
5. **Optional:** compare predicted Hc against a target, feed back into a Planner proposing the next candidate composition.

Each step is one Operation against a registered Tool. Expensive steps have MaMMoS surrogates via `mammos-ai` or cached runs so the demo stays responsive. This is an *example* — the framework does not depend on any of these packages.

## Open design questions (resolve when they stop being theoretical)

- **Consumables in the Resource model.** Do Resources carry consumable inventory (grams of Sm powder, GPU-hours budget) or just capacity? **Hackathon default: capacity only.** Scenario 6 in [docs/design/scenarios.md](docs/design/scenarios.md) is a pressure test, not a build requirement. Revisit in v1 if a vertical genuinely needs it.

## Planned commands (once the repo is bootstrapped)

Because the Lab is a service, the primary surface is HTTP + WS. The CLI is a thin client over that surface — build in this order:

- `autolab serve` — boot the Lab (FastAPI + WS). Default entry point. Rehydrates state from the ledger on restart.
- `autolab register <resource|tool|workflow> <file.yaml>` — POSTs to a running Lab. Used to stand up an instance from YAML on first boot.
- `autolab campaign start <campaign.yaml>` — POSTs a new campaign to a running Lab.
- `autolab replay <campaign-hash>` — byte-for-byte reproduction from cached tool outputs. Credibility anchor for the demo; runs against the ledger directly (no live Lab required).

Planned stack (pin at commit 1): Python 3.12, `uv` or `hatch`, FastAPI + WebSockets, React/Vite + Tailwind, SQLite (WAL), pydantic, Typer, weasyprint (PDF report), scikit-optimize (BO baseline), ubermag/MaMMoS/pymatgen as pip deps only — no vendored source. Tests via pytest; aim 20–40 total, concentrated on the provenance layer + MCP gateway happy paths.

CI: `.github/workflows/ci.yml` must run lint + tests + frontend build on every push. Tag commits `day-0` … `day-4`, `v1.0.0` on submission.

## Scope discipline

When in doubt, cut. The demo is **three beats** (the hackathon-plan.md draft beats are superseded):

- **Beat 1 — resource orchestration.** Lab is booted with several typed Resource instances (e.g. 2 × compute workers, 1 × GPU / SLURM partition, 1 × micromagnetics VM). User submits a Campaign. The Principal Agent decomposes the goal, spawns a Campaign subagent, and a batch of proposed Operations lands in the scheduler at once. The Console shows resources filling lanes, Operations from different Experiments interleaving, parallelism visible to the eye. *The scheduler is doing clever work, and you can see it.*
- **Beat 2 — the `react()` loop with vision.** An intermediate result (PXRD or hysteresis PNG) completes. An Interpretation Operation (e.g. `hysteresis_interpret`) calls Opus 4.7 on the rendered figure and writes a Claim Record with confidence; the Planner's `react()` consumes the Claim and returns an Action (`add_step` / `branch` / `retry_step` / `ask_human`); the scheduler reshuffles the plan tree live. Unchosen proposals remain in the ledger as breadcrumbs — the reasoning is auditable, not lost.
- **Beat 3 — physics payoff, intervention, auto-report.** The example workflow's multiscale chain runs (MLIP relax → intrinsic → finite-T → Hc). Live panels show structure, Ms(T), loop, and Hc updating as stages complete. A human intervention ("restrict Co > 30 %") lands as a hashed Record and visibly reshuffles the tree. Target met → auto-report renders with the candidate and its recipe.

Anything not serving one of these three beats is v2.

Hard stop: submission 2026-04-26 20:00 EST. No commits after that.

## What to check before recommending from memory or docs

The design docs name specific files, classes, and flags that may not exist yet (most of them don't — this is a pre-code repo). Before telling the user "X does Y," verify the file exists and the symbol is defined. "The plan says X" is not the same as "X is implemented."
