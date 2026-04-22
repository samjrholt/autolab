# Glossary

Canonical terms for the autolab system. Use them consistently in code, prompts, docs, the demo script, and the Console UI. Do not coin synonyms.

If you feel the need for a new term, first check this file. If it isn't here and the concept is load-bearing, add it — don't smuggle it in via a field name.

---

## Core model

**Lab**
The long-running FastAPI service that owns shared resources, registered tools, registered workflows, campaigns, and the ledger. One Lab instance corresponds to one physical or institutional setting (e.g. "Sam's desk," "Max Planck magnetics suite"). Restart-safe; rehydrates from the ledger.

**Campaign**
A goal-directed search inside a Lab, owning a planner, a budget, a set of constraints, and a stream of experiments. Examples: *maximise room-temperature coercivity of Fe-Co-Mn within 80 furnace hours*, *find the L1₀-ordering temperature window*. Campaigns have a Merkle root.

**Experiment**
One attempt inside a campaign — the unit grouped by `group_id` and the unit that produces one dataset row once characterisation is complete. An experiment may span many operations and branch.

**Workflow**
The DAG of operations one experiment runs. Linear synthesis + characterisation is a workflow. A branching sinter-then-quench-or-slow-cool is a workflow. A workflow can be mutated mid-flight by `react()` (add / retry / branch steps).

**Operation**
One atomic step — synthesis, simulation, characterisation, analysis, literature lookup. Each Operation declares a `resource` it needs, has a typed input and output, and produces exactly one primary `Record`. Operations never write records directly; the orchestrator does.

**Planner**
The decision engine for a campaign. Implements `plan(history, resources) → list[ProposedStep]` for batch proposals and `react(record, plan) → Action` for adaptive mid-experiment replanning. LLMs, Bayesian optimisers, heuristics, and humans all live in this slot.

**Resource**
A **named instance** of capacity-limited capability that an Operation needs. Experimental (`arc-furnace-1`, `arc-furnace-2`, `tube-furnace-A`, `squid-1`) or computational (`slurm-partition-gpu`, `dft-licence-pool`). Each instance has a `kind` (the type string an Operation declares — `arc_furnace`, `slurm`, `squid`) and a `capabilities` dict (`{max_temp: 2000, volume_mL: 5}` or `{gpu_count: 4, mem_gb: 80}`).

User-level talk is counts-per-kind ("2 × arc furnace"); the code sees individual Resource instances. An Operation declares its required `kind` plus optional capability requirements; the scheduler acquires one free compatible instance. See [scenarios.md](scenarios.md) #4 and #6 for pressure tests.

**Sample**
A first-class identifier for the thing — physical or digital — that Operations act on and transform. Every Operation that `produces_sample: true` mints a new `sample_id`; every Operation that consumes upstream outputs inherits the upstream `sample_id`(s) into `parent_sample_ids`. Operations can be marked `destructive: true`, which means the sample cannot appear in any downstream Operation after them. This is how the framework tracks "the pellet we milled," "the cast alloy we sintered," "the relaxed structure we passed to DFT," and every re-measurement of the same sample.

**Artefact** is **not** a separate concept — when older design notes say "artefact," they mean "Sample" or "the output of an Operation referenced via `source_record_id`." Use Sample for the thing; use `source_record_id` for the reference.

---

## Data and integrity layer

**Record**
The append-only unit in the ledger. Every Operation, QC verdict, Claim, human intervention, and annotation lands as a Record. Fields (see ideas-foundation §7): identity, what ran, lineage (`parent_ids`, `inputs.source_record_ids`), outcome, decision, quality, integrity, flex (tags + annotations). SHA-256 per record.

Every Record carries `tags: list[str]` and `annotations: list[Annotation]` from day 0. This is the framework's concession to the structured/free-text tension: typed outputs for what we know how to schema, tags and free-text annotations for everything else. See [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md) §3.

**Ledger**
The Lab's append-only record store. SQLite (WAL) + plain `.jsonl` dual-write. Survives crashes. Queryable, indexable, never mutated.

**Session**
One execution context in which Records are produced. Carries the `EnvironmentSnapshot` so every Record can be reproduced.

**EnvironmentSnapshot**
Python version, package versions, git commit, random seeds, platform, hostname. Captured once per Session, linked via `session_id`.

**Annotation**
An append-only post-hoc addition to an existing Record. Retractions, corrections, notes, re-QC verdicts, human commentary. The Annotation itself is a Record; the original is never touched.

**Checksum**
SHA-256 of a Record's canonical serialisation. Verifiable on read.

**Merkle root**
An optional per-Campaign root hash over the Campaign's Record chain. Useful as plumbing (one fixed-size handle for a whole Campaign's integrity state), but **not pitched as a feature** — the cross-lab mergeability story was dropped during the 2026-04-21 ideation pass because practising scientists do not care about cryptographic dataset merge. Per-Record SHA-256 is the integrity primitive that matters day to day.

**Replay**
Byte-for-byte reproduction of a campaign against cached tool outputs. Exposed as `autolab replay <campaign-hash>`. What turns "we logged everything" into "we are reproducible."

---

## Agent and expertise layer

**Principal Agent**
The PI-level Managed Agent. Decomposes a campaign goal into hypotheses and delegates work. Lives at campaign scope.

**Campaign Subagent**
A subagent spawned by the Principal to pursue one hypothesis in isolated context. Visibility into its tool calls is private; only its summary report returns to the Principal.

**Interpretation Operation**
A capability whose adapter calls an LLM (by default Claude Opus 4.7) to read a record or a rendered figure and return a structured Claim. Examples: `pxrd_interpret`, `hysteresis_interpret`, `phase_purity_estimate`, `annotation_extract`. These are registered the same way any other capability is — one `tool.yaml`, one adapter class, one entry in the registry. The `resource` is `claude-opus` (capacity = concurrent calls allowed), so LLM usage is visible to the scheduler and replayable from cache during `autolab replay`. Decision rationale in [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md) §2.

Previously called a "Skill" in earlier design docs; that term is deprecated — see the *Deprecated* section below.

**Capability**
The scientific name of a tool — *what a scientist would call it*. `micromagnetics_hysteresis`, `dft_intrinsics`, `pxrd_measure`, `coercivity_measure`. Capability names are a one-way door, chosen at day 0.

**Tool**
A single capability exposed over the MCP gateway. One YAML declaration file per tool in `autolab/tools/`. Declaration SHA-256 lands in every Record the tool produces.

**Adapter**
The Python code that implements a capability. Wraps an external library (MaMMoS, ubermag, a real VSM driver, a stub) and presents the capability's declared input/output contract. Adapters are autolab-owned — that is how the provenance contract is guaranteed.

**Gateway**
The single MCP server (`autolab/mcp/gateway.py`) that reads the tool registry and exposes every declared capability over MCP. Not many MCP servers. One gateway, many tools.

---

## Decision and quality

**PolicyProvider**
The decision backend a Planner consults when deciding what Action to return from `react()`. `HeuristicPolicyProvider`, `LLMPolicyProvider`, `HumanPolicyProvider` — interchangeable. Receives a **DecisionContext** (the Record that just completed, gate result, Sample history, allowed Actions, budget remaining) and returns an Action.

Keep PolicyProvider separate from Planner: a Planner knows how to *propose* (batch plan) and how to *structure* a reactive decision; the PolicyProvider is where "should we retry, escalate, or ask a human?" actually gets answered. That separation lets an LLM-driven PolicyProvider live on a BO Planner, or a heuristic PolicyProvider pre-filter before an LLM is invoked, without touching the Planner class.

**Subsumption layer**
A cheap heuristic pre-filter in front of an LLM-based Planner. If a heuristic would unambiguously escalate or stop, the LLM call is skipped. Bounds cost and latency honestly.

**Action vocabulary**
The fixed set of values `react()` may return:
- `continue` — proceed with the current plan.
- `accept` — mark a result as meeting the `AcceptanceCriteria`; stop searching this branch.
- `stop` — terminate the Campaign (with reason).
- `add_step` — splice a new Operation into the Workflow.
- `retry_step` — re-run an Operation with different params, reusing upstream Samples where possible (pass `source_record_ids` at the earlier valid step).
- `replan` — discard the remaining plan and rebuild.
- `escalate` — hand off to a higher-tier Planner (Principal, human).
- `branch` — fork the Workflow, pursuing two paths from the same upstream Sample.
- `ask_human` — pause and wait for a human decision recorded as an Intervention (scenario #5).

Every return carries a `reason` string persisted in the Record's `decision` field.

**AcceptanceCriteria**
A structured declaration of what "good enough" looks like for a Campaign or a Workflow step — a rule set evaluated post-Operation against the outputs (e.g. `{"phase_L10_fraction": {">=": 0.8}, "Hc_kA_per_m": {">=": 800}}`). The result is a **gate** (pass / soft-fail / fail) which the Planner's `react()` consumes via the PolicyProvider to emit an Action. Lives on the Campaign or inline on a Workflow step.

**Claim**
A structured diagnosis returned by an Interpretation Operation — *"kink at 0.2 T suggests soft-phase contamination, confidence 70 %, recommended action: raise anneal temperature by 150 °C."* Logged as its own Record with a confidence, never written as a ground-truth field on the measurement. Validation runs link back via `parent_ids`, so the ratio of validated to issued claims becomes a visible metric.

**QC verdict**
A structured result from one of the four QC layers (instrument, process, measurement, data): `pass` / `fail` / `soft-fail` plus reason, severity, and linked action rule.

**Decision grade**
A computed flag on a Record derived from its QC verdict set. A Record without QC is not decision-grade; the Planner must know.

**Intervention**
A human action that changes the Lab's state (edit plan, inject manual result, override a decision, pause / resume). Every intervention is a Record, hashed and linked; no invisible human edits.

**Hook**
A framework-enforced, non-skippable callback that fires around an Operation or a campaign lifecycle event. Fixed set: `pre_operation`, `post_operation`, `pre_campaign`, `post_campaign`, `on_intervention`. Hook code returns values; the framework writes the Record.

---

## Interface layer

**Campaign Console**
The persistent web UI served by the Lab. Shows plan tree, run feed, live physics panels, intervention box, ledger panel, auto-generated report. **Not a chat window.**

**Event stream**
The WebSocket channel over which Records (and plan-tree diffs, agent messages, intervention acks) stream to subscribers. The Console is one subscriber; anything else (Slack, CI, external monitor) plugs in the same way.

---

## Deprecated / do not use

- **"Chat window"** — the surface is the Campaign Console. A scientist running a multi-hour campaign needs persistence, not conversation.
- **"Autonomous"** as a standalone adjective — always qualify ("autonomous within the campaign budget," "operator-in-the-loop autonomous"). Strategic direction is human until the data justifies otherwise.
- **"Lane"** — deprecated shorthand from early matdiscovery notes. Never part of the public model.
- **"Tool" for a library** — `ubermag` is a *library*; `micromagnetics_hysteresis` is a Tool. Do not conflate.
- **"Log"** for the ledger — "log" implies unstructured, mutable, and throwaway. Ledger implies hashed, append-only, and load-bearing. The difference is the product.
- **"Skill"** as an autolab-level abstraction — removed 2026-04-22. What used to be called a Skill (e.g. `hysteresis-interpreter`) is now an **Interpretation Operation**: a capability whose adapter calls Claude. No separate Skill registry, no `SKILL.md` format at the autolab layer. Rationale in [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md) §2. If the Anthropic `SKILL.md` format appears inside the Claude-calling adapter as an implementation detail, that is fine — it just isn't a first-class autolab concept.

---

## Scheduling vocabulary

**Cross-experiment interleaving**
Running Operations from different Experiments of the *same* Campaign concurrently on different Resource instances. Example: Experiment A is in characterisation (SQUID) while Experiment B from the same Campaign starts sintering (tube furnace). The scheduler sees Operations as a single batch across the Campaign's active Experiments and dispatches greedily against free Resources. This is one of the places the framework goes beyond current state of the art.

**Cross-campaign scheduling**
Arbitrating Resource use across multiple Campaigns within one Lab, typically by priority. Campaigns each have their own Orchestrator but share one ResourceManager.

**Lane**
In the Console visualisation, a horizontal strip representing one Resource instance over time — Operations appear as pills that occupy their lane while running. Lane is a **visualisation term**, not a model concept; do not use it in code or schemas.

## Guidance

- When explaining the system quickly, prefer the sequence: **Lab → Campaign → Experiment → Workflow → Operation**. Everything else is detail.
- When explaining the *product*, prefer the three-layer frame: **Brain → Hands → Ledger**.
- Use `workflow` for the logical execution graph; use `physical setup` when discussing replicated hardware.
- Every noun in this glossary should be the *only* word you use for that concept. If you notice code or a prompt drifting toward a synonym, rename it.
