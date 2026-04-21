# autolab — Ideas Foundation

**Purpose.** This is the synthesis document for the hackathon build. It captures every idea worth preserving from `ai-lab-software/matdiscovery`, `white-paper-2.md`, `concept-pack.md`, `demo-plan.md`, and the architecture decisions — and rephrases them as *ideas*, not code. The hackathon rebuild writes fresh code from scratch, but every design choice below has been battle-tested in the existing framework and should inform the new one.

**What this document is not.** It is not an implementation spec, not a line-by-line port, and not a status report. The new `autolab` repo uses these ideas as design input only.

> **2026-04-22 update.** The "Skill" abstraction has been removed from the autolab model. Every reference below to `Skills`, `SKILL.md`, or individual named Skills (`hysteresis-interpreter`, `phase-diagnoser`, etc.) is superseded by **Interpretation Operations** — capabilities whose adapters call Claude and return Claim Records. See [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md) §2 for the rationale. Treat "Skill" in this doc as shorthand for "Interpretation Operation" when reading for continued context.

---

## 1. The thesis — why this matters

Eras are defined by materials. The AI prediction revolution has happened (GNoME, MatterGen, MACE, CHGNet). The synthesis and data revolution has not. This is the next decade.

The prediction problem answers *could this crystal exist?* The useful question is *will this material do what I need?* — and the answer is set by **microstructure and processing**, not crystal structure. No atomic model captures that. No simulation is ground truth. Every ML potential is trained on approximations of reality. Experiment is the only ground truth.

The bottleneck is not better models. It is **decision-grade experimental data with full provenance**, including failures — which does not exist in any database today. Whoever builds the infrastructure to generate this compounds an advantage no prediction model can catch.

For the hackathon: **build the brain and the memory of that infrastructure, running against a real multiscale simulation stack, so the architecture is demonstrably correct the moment a real instrument is bolted on.** That is the story.

---

## 2. The moat — five ideas that together are the product

1. **Full provenance is the asset.** The platform's output is not any material it finds — it is the dataset it generates: `composition → processing → structure → properties` with failures included and every parameter, environment state, and reasoning step captured. This dataset does not exist. It is the moat.
2. **Processing is first-class.** Every autonomous lab before this one optimises composition and treats processing as a nuisance. Magnets and superconductors fail under that assumption. Microstructure — and therefore processing — is the first-class variable.
3. **Failures are data, not exceptions.** Architecturally enforced. Failed runs are records with `status: "failed"` and a reason. The Planner sees them in history. Over time the negative space becomes the most valuable part of the corpus.
4. **The lab must distrust itself.** Closed loops amplify errors. QC is not a post-hoc layer; it is enforced by the framework. Every record carries QC verdicts. A result without QC is not decision-grade.
5. **The data layer is the invariant.** Synthesis methods, characterisation instruments, planners, optimisers — all swappable modules. The provenance schema is the thing you never break. This makes the platform material-agnostic and instrument-agnostic by construction.

One-liner: *We are not building the best simulator. We are building the infrastructure that plugs in the best available model, captures everything that happens, and swaps it out when something better comes along. The platform is the product. The models are replaceable.*

---

## 2a. The three-layer mental model (audience-facing)

The five moats in §2 and the five-layer architecture in §5 are the *internal* design. To anyone outside the project — judges, scientists, investors — autolab is three things:

1. **Brain** — Claude Opus 4.7 with a handful of Skills. Decides and interprets.
2. **Hands** — Tools that run the science. Simulation today, real instruments tomorrow.
3. **Ledger** — An append-only, hashed, replayable scientific record. **The product.**

**Rule of communication.** Every external explanation — demo script, README opening, grant pitch, first sentence of every conversation — maps onto these three layers. The elaborate design is what makes the three-layer story honest; it is not what we lead with.

**Rule of scope.** Any feature that does not obviously belong to Brain, Hands, or Ledger is a v2 problem.

**The final framing.** *autolab is a scientific record with an agent attached.* The record is the invariant. The agent is replaceable. Every architectural decision downstream should survive that substitution.

---

## 3. The two abstractions that carry the architecture

Every entity in the system is either an **Operation** or a **Planner**. This is the keystone idea.

- **Operation** — anything that transforms, measures, or analyses. Synthesis, XRD, SQUID, anneal, SEM, DFT, micromagnetic simulation — all the same type. Async `run(inputs) → OperationResult`. Each operation declares its `resource` and exposes `extract_features(result)` for ML-ready views.
- **Planner** — anything that decides what to do next. BO, GA, TPE, random, heuristic, LLM, human — all the same type. Two methods: `plan(history, resources)` for batch proposals and `react(record, plan)` for adaptive mid-experiment replanning.

**Why this is the right keystone:**
- One interface for every experimental or computational action makes everything composable.
- One interface for every decision-maker means classical optimisers, LLMs, and humans live in the same slot and can be A/B compared on identical footing.
- `react()` is the world-leading move. No other autonomous-lab framework supports adaptive mid-experiment replanning. It is the thing that makes the agent an *experimentalist* and not a script runner.

**Action vocabulary for `react()`:** `continue`, `stop`, `add_step`, `retry_step`, `replan`, `escalate`, `branch`. Each returns with a reason string that lives in provenance.

**Subsumption layers for policy providers.** Heuristic providers can pre-filter before an LLM is called — if a heuristic would unambiguously escalate or stop, skip the model call. This bounds cost, bounds latency, and is honest about where cheap rules beat expensive reasoning.

**One tool call ≠ one operation record.** An Operation is a scientific action with a provenance record. An LLM tool call is a mechanical event. A single Operation may issue many tool calls; a single tool call may spawn many child Operations. The record graph uses `parent_ids` to capture this fan-out cleanly. Keep the two concepts separate in code and in conversation.

---

## 4. Workflow as data

A workflow is a list of `{operation, depends_on}` entries. Linear is a special case. Parallel characterisation is a special case. Reprocessing (re-anneal, re-measure) is a special case. Everything that looks like "more complex orchestration" is just another adjacency list.

The orchestrator reads the DAG, runs operations in dependency order, parallelises where it can, and emits provenance records as it goes. Adding a new step is a line of data, not a code change.

The Planner may rewrite the workflow dynamically. `react()` returns `add_step` and the orchestrator splices it in. This is the mechanical basis for adaptive campaigns.

---

## 5. The five-layer architecture (what to build)

| Layer | Role | Invariant? |
|---|---|---|
| **1. Data / Provenance** | Append-only record store, SHA-256 per record, Merkle chain per campaign, environment snapshot per session, replay CLI. | **Yes — never change the guarantees.** |
| **2. Orchestration** | Async loop. Wraps every Operation call for provenance. Resource-aware scheduling. Failure containment. Event callbacks. | Rarely (framework updates). |
| **3. Operations** | Synthesis, characterisation, post-processing. Each defines `run` and `extract_features`. Real physics via MaMMoS components. | Frequently (new science, new instruments). |
| **4. Planners** | BO, heuristic, LLM, adaptive. `plan()` + `react()`. Provider-agnostic LLM policy with heuristic pre-filter. | Frequently (new algorithms, new models). |
| **5. Interface** | Campaign Console (web) + CLI. **Not a chat window.** Persistent, hashed, reproducible. Shows plan tree, run feed, live physics, intervention box, auto-report. | Rarely. |

The new hackathon addition on top of this (vs. the existing `matdiscovery`): **Claude Managed Agents** as the orchestration brain, **Claude Skills** as crystallised domain knowledge, and **one MCP gateway** exposing an in-repo capability-named tool registry — local adapters today, external MCP servers when a partner lab wants to plug in.

**Externally, present these five layers as the three in §2a** (Brain = layers 2+4 collapsed; Hands = layer 3 via the gateway; Ledger = layer 1). Layer 5 is the surface you watch all of it through.

---

## 5a. Capability-named tool registry (not a plugin system)

Tools are named by **what a scientist would call them**, not by the library that runs them. `micromagnetics_hysteresis`, not `ubermag_hysteresis`. `dft_intrinsics`, not `mammos_dft`. `device_response`, not `gmr_closed_form`. This is a one-way door — choose the scientific names at day 0, never rename.

**Shape of the registry.**
- One YAML declaration file per capability in `autolab/tools/`.
- Each declaration: `name`, `capability`, `inputs` (typed), `outputs` (typed), `resource`, `invoke` (adapter module path), `provenance_class`, `version`.
- SHA-256 of the declaration file is stamped into every record the tool produces. Updating the declaration is a provenance-visible event.
- One MCP gateway (`autolab/mcp/gateway.py`) reads the registry and exposes every declared capability over MCP.
- External tools (MaMMoS, ubermag, a real VSM) are wrapped by **autolab-owned adapters**, not registered by plugin entry points. Ownership of the adapter is how we guarantee the provenance contract.

**Why this is the right boundary.**
- Brain sees capabilities, not libraries. Replacing the backend for `micromagnetics_hysteresis` is a one-line YAML edit, not a prompt change.
- Hands are swappable per capability. A partner lab's real VSM replaces `hardware_stub` by implementing the same capability; the agent never notices.
- Ledger stays invariant. Declaration hash in every record gives us cross-lab comparability without trusting the other lab's implementation.

**What this is not.** Not a plugin system with external entry points. Not a per-library MCP server per backend. Not a generic tool router. One dev, one registry, one gateway. Anything more elaborate is v2.

---

## 6. Provenance — the non-negotiable layer

Every idea here is load-bearing. Do not skip any.

**Framework-enforced.** Modules do not write provenance. The orchestrator wraps every operation call. A module literally cannot skip provenance. Failures are records, not exceptions.

**Write-ahead records.** The record is created and persisted *before* the operation runs. Survives power failures, OOM kills, hard crashes. Orphaned "running" records are detectable on restart. You know something was attempted even if you never learn how it ended.

**Immutability + annotations.** Records are never modified or deleted. If a later analysis invalidates a result, it is *annotated* with a retraction/correction/note. The correction itself becomes provenance.

**Graph via `parent_ids`.** No graph database. SQLite with `parent_ids: list[str]` per record, indexed. `group_id` groups an experiment. `tags` give flexible cross-cutting labels. Linear, branching, reprocessing — all the same shape.

**Checksums + dual-write.** SHA-256 per record, verifiable on read. Every record dual-written to SQLite (WAL mode) and plain `.jsonl`. If SQLite corrupts, rebuild from the log.

**Data lineage.** Every input carries the `source_record_id` of the record it came from. You can trace any measurement back to the synthesis run, the BO suggestion, the Planner reasoning, the session it happened in.

**Reproducibility metadata.** Each session captures an `EnvironmentSnapshot` — Python version, package versions, git commit, random seeds, platform, hostname. Linked to records via `session_id`. Cheap to capture, invaluable to replay.

**Schema versioning + open metadata.** `schema_version` on every record. Core fields minimal (~15) and stable. Everything that might change goes in open `extra="allow"` metadata. Readers transform on read, never rewrite the past.

**Event sourcing.** All state (best result, convergence, calibration status, QC summary) is *derived* from the record log, never stored independently. The records are the only ground truth.

**Replay as a CLI verb.** `autolab replay <campaign-hash>` reproduces a campaign byte-for-byte against cached tool versions. This is what turns "we logged everything" into "we are reproducible."

**Merkle root is a trust primitive, not a gimmick.** The per-campaign Merkle root earns five things at once: (1) integrity of the record chain; (2) cheap proof-of-inclusion for any single record; (3) an immutable reference two labs can swap before they share data; (4) **mergeability across labs without either side having to trust the other** — both campaigns are verifiable against their own roots before being unioned; (5) a stable identifier for citing a dataset in a paper. The fifth item is how science papers eventually cite an autolab run.

**Dependency rule.** Models ← Store ← Orchestrator ← Dashboard. Operations and Planners depend only on models. An Operation never imports the Orchestrator. Clean layering is what keeps the platform material-agnostic.

---

## 7. The record schema (shape, not syntax)

Every operation execution produces one record with:
- **Identity** — `id`, `group_id`, `timestamp`, `record_status` (pending / running / completed).
- **What ran** — `operation` name, `module` version string.
- **Lineage** — `parent_ids` (predecessors), `inputs` (including `source_record_ids`).
- **Outcome** — `result` (status + outputs + error), `duration_ms`.
- **Why** — `decision` (reasoning, hypothesis, source — manual / BO / LLM / heuristic).
- **Quality** — `qc` verdicts, `system_state` (equipment snapshot).
- **Integrity** — `checksum`, `schema_version`, `session_id`.
- **Flex** — `tags`, `annotations` (append-only post-hoc additions).

Annotations capture retractions, corrections, and notes from the system, the user, or a re-QC pass. They never modify the record they reference — they extend it.

---

## 8. QC — the framework that makes the lab distrust itself

Four machine-readable layers, enforced after every operation:

1. **Instrument QC** — calibration status, drift detection, known-reference measurements.
2. **Process QC** — mass balance, thermal profile verification, atmosphere / environmental monitoring.
3. **Measurement QC** — curve sanity checks, repeat measurements, controlled replicates.
4. **Data QC** — schema validation, missingness, anomaly detection, failure-mode labelling.

Every QC verdict is structured: pass / fail / soft-fail, with reason, severity, and linked action rule. A `decision_grade` flag is computed from the verdict set. A record without QC is not decision-grade and the Planner must know.

**Diagnoses are claims, not facts.** When a Skill (e.g. `hysteresis-interpreter`) returns an interpretation — *"kink at 0.2 T suggests soft-phase contamination"* — that is logged as a claim with a confidence and a recommended validation step, never as a ground-truth field on the record. The validation run is logged separately, with `parent_ids` linking it back to the claim. Over time the ratio of validated claims to issued claims is itself a metric. This keeps the agent epistemically honest and prevents hallucinated physics from leaking into the dataset.

**Self-calibration emerges from this.** After a few hundred runs the system looks at `system_state` across records and detects patterns — furnace position X runs 7 °C hot, instrument Y drifts on Mondays, precursor lot Z has reduced yield. Nobody told it. It worked it out from its own data. Same mechanism works for simulated or physical equipment.

---

## 9. Resources are more than instruments

A **resource** is anything with finite capacity that an Operation needs: furnace, SQUID, XRD, SEM, robot, human time, *and* compute / GPU / solver licenses / external simulation queue slots. One abstraction, one scheduler.

Current minimal form: `Operation.resource = "furnace"` plus `ResourceManager` counting capacity. Near-term evolution: richer descriptors for kind, capabilities, queue state, turnaround. The hackathon demo only needs the minimal form — but the interface shape must not preclude the richer model.

The Planner suggests experiment **batches** sized to keep every resource busy. While sample A is in the furnace, sample B is in XRD, sample C is in SQUID. No idle equipment. The Planner thinks ahead while the lab works. For the demo this is a visible "plan tree" beat.

---

## 10. Multi-campaign as a first-class idea

A **campaign** is one goal-directed search: objective, planner, budget, state, provenance scope. The platform must eventually run multiple campaigns sharing resources. That is the product requirement.

For the hackathon, one campaign is enough — but the data model should carry `campaign_id` as a stable field so nothing has to be migrated later. Pause, resume, prioritise, budget, and report should eventually live at campaign scope, not lab scope.

---

## 11. ML data pipeline — flatten without losing

The contract: every Operation knows how to expose its outputs as a typed **FeatureView**, a small structured object with a fixed set of field kinds:

- `scalar` — numbers with units (`saturation_magnetisation: {value: 1.73, unit: "T"}`).
- `curve` — 1-D series (hysteresis, XRD pattern, MvT).
- `image` — 2-D array or rendered PNG pointer (domain image, loop render for vision).
- `spectrum` — labelled peaks or frequency-domain data.
- `pointer` — hash reference to a blob stored outside the record (large mesh, SEM stack).

Not `dict[str, float]`. A flat dict destroys everything the agent and the ML pipeline need to know about shape, unit, and provenance. The framework knows how to coerce a FeatureView into a flat row when a user asks for a DataFrame — flattening is a *derived view*, not the contract.

Consequences:
- One provenance store → many views (ML row, agent summary, UI panel, paper figure) all derived from the same FeatureView.
- Raw data always preserved. The row is a derived view, never the source of truth.
- Adding a new Operation automatically extends the feature space.
- Opus 4.7 vision reads the `image` kind directly without custom glue.

ML tasks supported from the same corpus: composition → property, processing → microstructure, structure → property, full-pipeline end-to-end. All derived views. `lab.to_dataset(features=[...], target=...)` returns a clean DataFrame.

---

## 12. The LLM planner idea (what carries forward)

The existing `LLMPolicyProvider` idea is exactly right and should survive:

- **Provider-agnostic** — the planner depends on a `llm_client: (prompt) -> str` callable, not on a specific SDK. Anthropic today, anything tomorrow.
- **Heuristic pre-filter** (subsumption layer 2) — if a cheap heuristic would escalate or stop anyway, skip the model call.
- **Structured JSON response** with a fixed schema: `type`, `reason`, `confidence`, plus action-specific fields.
- **Graceful fallback** to a heuristic if the model returns unparseable JSON or errors.
- **Reasoning logged to provenance** — the `decision` field on the record carries the LLM's prompt context hash and reason string.

Hackathon upgrade: replace the plain `llm_client` with a **Claude Managed Agent** so long-running campaigns survive restarts, subagent handoffs, and intermediate artefacts.

---

## 13. Human-in-the-loop as a provenance primitive

The scientist can always:
- Inject a manual result (`lab.record(...)`) through the same provenance pipeline. Manual and automated runs are indistinguishable at the data layer.
- Annotate an existing record (`lab.annotate(id, note)`) — never modify, only extend.
- Pause and resume the lab cleanly.
- Intervene in the Principal Agent's plan mid-campaign — and that intervention is itself a record, hashed, timestamped, reproducible.

No invisible human corrections. Every steering signal is in the log.

---

## 14. Observability — what the Console surfaces

`print(lab)` in the original design returns a live status string. In the hackathon version, the Campaign Console is that string rendered as a persistent web UI, plus:

- Campaign header (goal, constraints, session, git commit, schema version, Merkle root).
- **Plan tree** — Principal Agent's decomposition, Campaign subagents lighting up as they pick up branches.
- **Run feed** — every tool call, every Skill invocation, every agent message, append-only, hashed.
- **Live physics panel** — hysteresis loop / XRD / device response streaming as operations complete.
- **Intervention box** — free-text, recorded as a record.
- **Auto-generated report** at end of campaign: proposed material, recipe, predicted performance, uncertainty, hash-stamped link to full lineage.
- **Event callbacks** — the Console itself is just a subscriber to events. Anything else that wants to listen (Slack notifications, CI checks, external monitors) plugs in the same way.

**Not a chat window.** A scientist running a multi-hour campaign needs a persistent control surface, not an ephemeral conversation.

---

## 15. Simulated modules are permanent fixtures

Simulated Operations are not throwaway demo scaffolding. They serve four permanent roles:

1. **Demo** — end-to-end loop runs without hardware.
2. **Reference implementation** — "here is how to write an Operation."
3. **Integration tests** — deterministic, fast, always available.
4. **Surrogate screening** — cheap pre-filter before committing physical lab time.

This matters for the hackathon because MaMMoS runs are minutes, not milliseconds. A small surrogate fallback per Operation (closed-form, cached, or ML-fitted) keeps the demo responsive while full runs happen offline.

**Rule:** a surrogate is never silently substituted. If a surrogate answered, the record says so — `module: "MicromagneticsSurrogate v0.1"` — and downstream code can filter. Same mechanism, honest label.

---

## 16. The first vertical — rare-earth-free magnets / magnetic sensors

**Why magnets first.**
- Sam's PhD + postdoc + skyrmion work are all here.
- Massive unmet demand: EV motors, wind turbines, grid, MRI, defence, sensors.
- Strategic: ~60% of rare-earth processing is Chinese. UK / EU / US all funding sovereignty plays.
- Processing-dominated: MnAl, Fe-N, Sm-Fe-N, optimised ferrites, exchange-spring magnets — all fail or succeed on microstructure.
- Competitive moat: proprietary dataset linking composition × processing × microstructure × magnetic properties. Nobody has this.

**Hackathon demo goal.** *"Design the magnetic free layer of a GMR-based speed sensor for an EV motor — linear across ±50 mT, sensitivity > 5 %/mT, operating to 180 °C — and give me the recipe."* This is a MaMMoS sensor-optimisation workflow, made autonomous.

**Why the sensor framing beats the permanent-magnet framing for the hackathon.** Every judge has a sensor in their pocket and their car. The device-level target makes the multi-scale chain visible: device target → intrinsic magnetic parameters → temperature behaviour → hysteresis under geometry → sensor response. Five visible moves the LLM coordinates.

**Second vertical (12–18 months later).** HTS superconductors: REBCO / BSCCO wire and bulk, pinning-landscape-limited. Customers include CFS, Tokamak Energy, grid HTS developers, UKAEA-adjacent fusion supply chain. Same platform, different modules.

---

## 17. The hero beat — the physical debugging loop

Software engineers debug by running code, reading a stack trace, diagnosing the bug, and rewriting. Scientists debug by running a synthesis, reading a characterisation (a kinked hysteresis loop, a dual-phase XRD pattern), diagnosing the physics, and rewriting the recipe.

**autolab performs this loop automatically.**

1. Principal Agent proposes composition + processing + measurement plan.
2. MaMMoS MCP servers run the multiscale chain.
3. A hysteresis loop comes back kinked — soft-phase contamination at 0.2 T.
4. The `hysteresis-interpreter` Skill reads the **rendered PNG** of the loop (Opus 4.7 vision), returns a structured **claim with confidence** (*"soft-phase contamination, 70% confidence, recommended action: raise anneal temperature by 150 °C"*), logged as its own record — not written back as a ground-truth field on the measurement.
5. Principal updates the plan (workflow mutation via `add_step` or `replan`). A Campaign subagent reruns. The rerun record carries `parent_ids` back to the claim, so the claim is validated (or falsified) in the ledger.
6. New loop morphs clean. Target is hit. Report renders. Campaign hash finalises.

This is the one beat worth 25 % of the score on its own (Opus 4.7 Use) and is the visual payoff for Demo (25 %). It is architecturally natural: `react()` was built for exactly this.

---

## 18. What makes this world-leading (not a claim, a checklist)

Every item below is true of `autolab` as specified, and false of every autonomous-lab project in the public literature today. Tick them off during the build and in the README.

- [ ] Adaptive mid-experiment replanning via `react()` with a structured action vocabulary.
- [ ] Framework-enforced write-ahead provenance with SHA-256 per record and Merkle root per campaign.
- [ ] Byte-for-byte replay via a CLI verb.
- [ ] LLM planner with heuristic pre-filter, structured response, graceful fallback, and reasoning logged to provenance.
- [ ] Domain knowledge as versioned Skills (hysteresis reader, phase diagnoser, thermal-stability check, sensor-response evaluator, literature lookup).
- [ ] Opus 4.7 vision reading rendered scientific figures, not just arrays.
- [ ] Multiscale simulation chain (DFT → spin dynamics → micromagnetics → device) via MCP, so any lab instrument can replace any Operation with no agent changes.
- [ ] Two-tier Managed Agents (Principal PI + Campaign subagents) with checkpoint/resume.
- [ ] Material-agnostic platform; magnets chosen for the first vertical because they are processing-dominated.
- [ ] Campaign Console with plan tree, run feed, live physics, intervention box, auto-generated hash-stamped report.
- [ ] QC enforced in four layers; `decision_grade` computed per record.
- [ ] Failures first-class (`status: "failed"`, kept, labelled, used).
- [ ] Self-calibration from accumulated `system_state` across records.
- [ ] Event-sourced derived state (no stored "best so far" — always recomputed from records).
- [ ] Human interventions are provenance records, not invisible edits.
- [ ] Open-source, Apache-2.0, from first commit.

---

## 19. What the white paper says we must *not* do

Explicit negatives, lifted from `white-paper-2.md`:
- Do not treat processing as a nuisance variable. It is the dominant lever for the properties that matter.
- Do not trust simulated data as ground truth. ML trained on simulation inherits the simulation's approximations. Always show where the ground truth came from.
- Do not build yet-another-crystal-structure-prediction model. That problem is well-served. The gap is elsewhere.
- Do not ship a demo that hides the data layer. The dataset is the asset. Make provenance visible.
- Do not let "autonomous" mean "no human steering." Strategic direction stays human until the data justifies otherwise.

---

## 20. The pitch in one paragraph (for the README)

> autolab is the brain and the memory of an autonomous materials scientist. A Claude Opus 4.7 Principal Agent decomposes a device-level goal ("give me a GMR-sensor free layer that operates to 180 °C"), delegates hypotheses to Campaign subagents, and drives a real multiscale simulation stack (MaMMoS: DFT → spin dynamics → micromagnetics → device) through MCP. Domain expertise lives in Claude Skills — reading a hysteresis loop, diagnosing secondary phases, checking thermal stability. Every tool call is written through an append-only provenance store with SHA-256 per record and a Merkle root per campaign; `autolab replay` reproduces any campaign byte-for-byte. Failures are data, not exceptions. Human interventions are records, not edits. Today autolab's hands are MaMMoS. Tomorrow they are a real VSM, a real XRD, a real furnace — the agent never notices, because the tool interface does not change. The platform is the product. The models are replaceable. The dataset it generates is the moat.

---

## 21. Open design questions (to decide during the build)

These are unresolved and do not block day 0, but log your choice in the repo when you resolve them:

1. **`campaign_id` placement.** Field on `OperationRecord`, or inferred from `tags`? Prefer explicit field for hackathon — it is cheap and forward-compatible.
2. **Skill granularity.** One big `magnetism-expert` Skill or five narrow Skills? **Resolved: five narrow Skills, four interpretive + one procedural** (`anneal-recipe-writer`). The procedural one shows competence, not commentary.
3. **Subagent count in demo.** **Resolved: exactly one Campaign subagent**, visibly context-isolated from the Principal. More looks like theatre.
4. **Surrogate triggering.** Always use MaMMoS at full fidelity, or auto-switch to surrogates under a latency budget? For the hackathon demo: record the full run offline, cache it, replay it live. Record the surrogate mode in provenance.
5. **Report format.** Markdown + PDF, or HTML + PDF? Markdown is simpler, PDF via weasyprint is honest for a "paper." Stick with Markdown → PDF.
6. **Vision input format.** PNG of the loop, SVG, or raw numerical array? PNG lets Opus 4.7 read the shape like a scientist — that is the point. Send all three; let the Skill choose.
7. **Public identity.** Name `autolab` unless GitHub is taken. Backup `labloop`. Don't name it matdiscovery.
8. **License on ideas carried over.** Apache-2.0 is compatible with every dependency in the MaMMoS stack, ubermag, pymatgen, BoTorch, and Materials Project API client. Good.
9. **Tool naming.** **Resolved: capability-named, not library-named.** `micromagnetics_hysteresis`, not `ubermag_hysteresis`. One-way door, chosen at day 0.
10. **Plugin system.** **Resolved: none this week.** External tools are wrapped by autolab-owned adapters, declared in YAML, exposed through one MCP gateway. One dev cannot maintain a plugin contract. v2 at the earliest.
11. **LLM provider abstraction.** **Resolved: Claude-native this week** (Managed Agents, Skills, MCP). LiteLLM / provider-agnostic policy layer is v2. Prize rubric scores Opus 4.7 use at 25% + $5k — forfeiting that to abstract the model is the wrong trade.

---

## 21a. Anthropic defaults we explicitly disable

Three behaviours Anthropic's agent framework offers by default actively damage the provenance contract. We switch them off and say so in the README.

1. **Auto-compaction of conversation history.** Claude's default is to summarise long conversations to save context. For autolab, the record chain is the truth — summarised tool calls are not verifiable. Every tool call lands in the ledger in full, and the Principal pulls ledger slices into context explicitly.
2. **Agent-rewritable memory.** An agent editing its own notes is a provenance violation. autolab memory is append-only. Corrections are new records with `annotations` pointing at the thing they correct; the original is never changed.
3. **`bypassPermissions` / tool auto-approval.** Every tool invocation must go through the gateway, which logs before it calls. No code path that skips provenance.

These three are what separate a scientific record from a chat log with file system access.

---

## 21b. Hooks vocabulary (framework-enforced, non-skippable)

The orchestrator offers a small fixed set of hooks that run around every operation. **Hooks are not user-overridable bypasses** — they are where the framework enforces provenance guarantees, and user-supplied hooks run inside that guarantee, never around it.

- `pre_operation(ctx)` — fires after the write-ahead record is persisted, before the tool runs. Used for resource locking, dry-run checks, cost estimation.
- `post_operation(ctx, result)` — fires after the result is returned, before the record is finalised. Used for QC verdict assembly, feature extraction, surrogate invalidation. Errors here flip the record to `soft-fail`.
- `pre_campaign(ctx)` — fires once at campaign start. Used for environment snapshot, Merkle root init, seed logging.
- `post_campaign(ctx)` — fires once at campaign close. Finalises the Merkle root, generates the report, writes the campaign-level record.
- `on_intervention(ctx, intervention)` — fires whenever a human edits a plan or injects a record. Writes the intervention as its own hashed record with full context.

The orchestrator always logs the fact that a hook ran, and always logs the hook's own output as an annotation on the relevant record. Hook code cannot write records directly — it returns values the framework writes. This is how we get the "modules cannot skip provenance" guarantee with a user-extensible surface.

---

## 22. What this document is *for*

Every design decision during the 6-day build should be checked against this document. If the new `autolab` implementation violates any idea in §2 or §18, that is a bug, not a trade-off. If any idea in §6 (provenance) is skipped, the submission is not world-leading. If the demo in §17 is not the single clearest beat in the 3-minute video, the video is wrong.

When in doubt, re-read §2. The five moats are the product.
