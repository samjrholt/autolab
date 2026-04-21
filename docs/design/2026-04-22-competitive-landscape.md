# 2026-04-22 — Competitive landscape and positioning

Synthesised from a 2026-04-22 survey of four system classes: Electronic Lab Notebooks, provenance standards, ML experiment trackers, and published autonomous-lab frameworks. Companion to [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md) — that doc handles the framing/abstractions consequences; this doc handles the positioning consequences.

Purpose: keep a durable record of **what to steal from existing systems** and **where autolab deliberately moves beyond state of the art**, so these judgements do not have to be re-derived in later design conversations.

---

## 1. Summary of the field

The survey found near-universal convergence on five patterns for balancing structured and unstructured metadata (cited individually below). Autonomous labs currently under-serve free-text human context; ELNs over-serve it and under-serve execution; ML trackers nail the tag/notes shape but know nothing about lab Resources; provenance standards describe work post-hoc but cannot execute.

**No surveyed system combines all three of:** framework-enforced hashed provenance, adaptive mid-experiment replanning driven by an agent reading rendered figures, and first-class queryable capture of human narrative evidence. That is autolab's opening.

---

## 2. Electronic Lab Notebooks

### Systems surveyed
Benchling, eLabFTW (incl. 4.0+ metadata and extra_fields), Chemotion with the **LabIMotion** extension, RSpace, LabArchives, plus the ELN Consortium `.eln` / RO-Crate interchange format.

### What they are
Human-operated digital notebooks with typed metadata bolted on. LabIMotion is the sharpest example of the structured/unstructured bridge: **Elements → Segments → Datasets**, where Segments are reusable typed metadata blocks attached to any Element, and **Text Templates** are reusable prose chunks a technician can insert and fill in.

### What to leverage (concrete imports)

1. **Segments as reusable typed metadata blocks** (LabIMotion pattern). Don't enforce one global schema across capabilities — let Lab operators define named typed blocks (e.g. a "Sintering Conditions" Segment with temperature, atmosphere, hold time) and attach them to any Record beyond its capability-declared outputs. The per-capability `tool.yaml` describes the Operation contract; Segments describe the experimental context. Different axis, both needed. ([Chemotion LabIMotion docs](https://chemotion.net/docs/eln/admin/text_template))
2. **Text Templates for intuition capture.** Pre-written prose stubs ("**Today's furnace condition:** \_\_\_\_\_\_") that a technician inserts into an annotation and fills in. Cheap to ship, surprisingly effective at extracting structured-enough notes from non-code humans.
3. **eLabFTW 4.0+ extra_fields builder.** A per-Lab, admin-editable JSON schema for per-Record extra metadata, with typed fields and validators. The pattern: do not hardcode a schema — let the Lab operator define it and version it in the ledger. ([eLabFTW metadata docs](https://doc.elabftw.net/metadata.html))
4. **`.eln` RO-Crate export format** (ELN Consortium). Chemotion, eLabFTW, RSpace, Kadi4Mat all support it. Writing an exporter for autolab is ~1 day of work and buys instant interoperability with the ELN ecosystem. ([ELN Consortium](https://github.com/theelnconsortium))
5. **Tags as folksonomy** (eLabFTW, Benchling). autolab already has `tags: list[str]` on every Record — keep it. Add Console autocomplete against recently-used tags to prevent synonym drift.
6. **Template-per-experiment-kind** (Benchling notebook templates, Chemotion templates). The ELN-wide pattern: a template defines required structured tables + free-text scaffolding for each experiment kind. Maps onto autolab's `tool.yaml` per capability.

### What autolab does much better

- **The ledger is the primary actor, not the scientist.** ELNs assume a human clicking "save." autolab produces Records by running experiments autonomously and attaches human free text as a first-class annotation *on top*. Benchling cannot produce a Record without a human gesture; autolab does nothing else.
- **Record integrity is load-bearing.** SHA-256 per entry, append-only, write-ahead. Benchling has audit logs but no cryptographic integrity. eLabFTW added RFC 3161 timestamping as a bolt-on. autolab treats it as non-negotiable from commit 1.
- **Replayability.** `autolab replay <campaign-hash>` reproduces a campaign byte-for-byte from cached tool outputs. No ELN has an equivalent — RO-Crate is *declarative* but not executable. autolab makes replay executable.
- **One surface from plan to record.** In Benchling the notebook is downstream of the work; in autolab the Lab *is* the work. One system plans, runs, and records.

---

## 3. Provenance standards

### Systems surveyed
W3C PROV (PROV-O), RO-Crate 1.1, Common Workflow Language (CWL).

### What they are
Declarative graph standards for "what happened" in scientific computation. Not executable; not agent-aware.

### What to leverage

1. **The `Entity / Activity / Agent` mental model.** PROV is a well-thought-out minimal graph. autolab's Record already has `parent_ids` and lineage; exposing a PROV-shaped view over the ledger (`GET /ledger/prov?campaign=…`) is ~100 lines and lets autolab plug into any PROV-aware downstream tool. ([PROV-O](https://www.w3.org/TR/prov-o/))
2. **RO-Crate as export format.** JSON-LD + attached files, metadata on every entity. Matches autolab's dual SQLite + JSONL + blob-store structure almost directly. `autolab export <campaign-id> --format ro-crate` buys ELN Consortium interop at zero extra schema cost. ([RO-Crate 1.1 spec](https://www.researchobject.org/ro-crate/specification/1.1/metadata.html))
3. **`description` / `comment` / `doc` on every typed node.** Universal pattern across PROV, RO-Crate, CWL. autolab's annotation model already follows this shape — keep it disciplined.

### What autolab does much better

- PROV and RO-Crate **describe** work after the fact. autolab **emits** PROV-shaped Records *write-ahead*, as the work runs. That isn't a new standard, it's the standards actually enforced in-loop.
- **Agent decisions are first-class graph nodes.** PROV has `Agent` but treats it nominally. autolab's ledger records not just that an Agent acted, but *what it decided, why, and what evidence it read*. The `decision` field on a Record and the `Claim` Record type have no direct PROV analogue — they are a richer agent-provenance layer. No standard body exists for "agent reasoning provenance"; autolab is early enough to set an informal one.

---

## 4. ML experiment trackers

### Systems surveyed
MLflow, Weights & Biases.

### What they are
Servers that log params, metrics, artifacts, and tags per training run; dominant in ML engineering.

### What to leverage

1. **Four-tier record shape: typed config + typed metrics + tags + markdown notes.** MLflow and W&B converged on this independently; it's the right shape. autolab already has `inputs` (config), `outputs` (metrics), `tags`, and Annotation for notes. What's missing is the *UI convention* that these are the four columns of a runs-table, searchable left-to-right. Copy the W&B runs-table UX directly. ([MLflow tracking](https://mlflow.org/docs/latest/tracking/), [W&B Run API](https://docs.wandb.ai/models/ref/python/experiments/run))
2. **Search DSL.** MLflow's `tags.owner = 'sam' and metrics.rmse < 0.1` syntax is excellent — users learn it fast, it composes well. Adopt the same grammar for `GET /ledger?filter=…` instead of inventing a custom query language.
3. **Reserved tag namespace.** MLflow reserves `mlflow.*` for system tags (`mlflow.source.git.commit`, `mlflow.user`, `mlflow.note.content`). autolab should reserve `autolab.*` similarly — `autolab.session_id`, `autolab.resource`, `autolab.branch_id` — so system-emitted tags never collide with user tags.
4. **Notes as a reserved tag (`mlflow.note.content`).** Elegant — the notes blob is just a well-known tag, not a separate table. Reduces schema surface by one field. Worth considering whether to make autolab annotations a tag convention instead of a separate model; tentative answer: no, because annotations need their own hashed Record identity for append-only integrity. But the lesson — don't over-proliferate fields when a tag convention suffices — stands.

### What autolab does much better

- **The orchestrator is first-class.** MLflow and W&B are passive — your code calls `log_metric`. autolab's scheduler actively runs Operations and the Record is emitted by the orchestrator, not by user code. Provenance is framework-enforced, not user-discipline-enforced.
- **Resource-aware scheduling.** Neither tracker knows what a Resource is. autolab's scheduler arbitrates real or computational Resources across experiments and campaigns, visibly.
- **`react()` / adaptive replanning.** No tracker has the concept of "the system changed its plan based on this result." That is the #1 autolab axis; MLflow/W&B offer no surface for it.

---

## 5. Autonomous labs (the actual competitors)

### Systems surveyed
AlabOS / A-Lab (LBNL), ChemOS 2.0, Coscientist (Boiko et al.), BayBE (Merck), Emerald Cloud Lab (Symbolic Lab Language).

### System-by-system

| System | What it is | What to leverage | Where autolab beats it |
|---|---|---|---|
| **AlabOS / A-Lab (LBNL)** | Robotic materials-discovery lab with a task-graph executor and MongoDB store ([Nature 2023](https://www.nature.com/articles/s41586-023-06734-w), [arXiv 2405.13930](https://arxiv.org/html/2405.13930v1)) | Generic `logger` object that attaches arbitrary JSON to any entity; sample-position tracking; replication-to-cloud pattern | Rigidly DAG-executed — no `react()`; no vision; no human-narrative capture; single-campaign focused; no cross-experiment interleaving |
| **ChemOS 2.0** | Distributed self-driving lab for chemistry, fog-node architecture ([Matter 2024](https://www.sciencedirect.com/science/article/pii/S2590238524001954)) | Two-database split (experiments vs simulations); fog-node pattern for edge equipment | Schema-first with no free-text slot; no LLM-as-scientist; closed-source |
| **Coscientist (Boiko et al.)** | LLM-driven chemistry agent (GPT-4) ([Nature 2023](https://www.nature.com/articles/s41586-023-06792-0)) | The idea that *the LLM trajectory is itself the record* — adopt: log every `react()` prompt and response as a Record | Narrative-only, no typed provenance layer; not a framework, not reusable; single-agent, not multi-campaign |
| **BayBE (Merck)** | Bayesian DOE campaign engine ([Digital Discovery 2025](https://pubs.rsc.org/en/content/articlelanding/2025/dd/d5dd00050e)) | Clean `Campaign` object with typed parameter/target schema; well-thought-out parameter-space definitions | DOE engine, not a lab — no execution, no provenance, no free text, no vision |
| **Emerald Cloud Lab** | Commercial remote-lab with Symbolic Lab Language ([ECL docs](https://www.emeraldcloudlab.com/documentation/functions/), [Wikipedia](https://en.wikipedia.org/wiki/Emerald_Cloud_Lab)) | Protocol-as-typed-code; ALCOA+ compliant metadata auto-annotation; hashed integrity | Proprietary; Wolfram-Language-only; no free-text narrative slot; cloud-only |

### Cross-system pattern

None treat narrative, intuition, or off-target findings as first-class evidence. AlabOS and ChemOS have nowhere for "don't run left electrode hot today." BayBE has no surface for it. ECL's SLL is the protocol, not the context. Coscientist captures narrative but loses typed structure because its trajectory *is* the record.

### What autolab does much better than all of them

1. **`react()` with vision.** None has it cleanly. AlabOS runs fixed DAGs; ChemOS too. Coscientist has LLM reactivity but no typed plan tree to mutate. This remains autolab's #1 world-leading axis.
2. **Cross-experiment interleaving within a campaign.** AlabOS does multi-campaign; nobody in the survey does cross-experiment interleaving on shared Resources within a campaign. Confirmed by the ai-lab-software comparison and the autonomous-lab literature.
3. **Narrative evidence as first-class, queryable, hashed.** A technician's "left electrode hot today" is an Annotation Record on `arc-furnace-1` — hashed, append-only, join-queryable against every future measurement on that Resource.
4. **Interpretation Operations as the ledger-native way to use LLMs.** Every Claude call is a Record with a Claim output, a hashed prompt and model ID, replayable from cache. Neither Coscientist nor any other surveyed lab records LLM calls this way. This is what makes the agent *replaceable*.
5. **Unified computational + physical.** AlabOS is robotic; ChemOS is distributed instruments; BayBE is pure DOE; none unify an in-process ubermag simulation and an arc-furnace run under one ledger. autolab does.

---

## 6. Post-hoc LLM structuring (adjacent research)

### Systems surveyed
**LISTER** — semi-automatic metadata extraction from annotated eLabFTW text ([paper](https://www.researchgate.net/publication/374322736_LISTER_Semiautomatic_Metadata_Extraction_from_Annotated_Experiment_Documentation_in_eLabFTW)). **Dagdelen et al. 2024** — fine-tuned LLMs extracting structured materials-science records from paper paragraphs ([Nat Commun](https://www.nature.com/articles/s41467-024-45563-x)). **Clinical imaging** — several GPT-4 radiology-report structurers in the 2025 literature.

### What to leverage
Both projects validate one autolab move: **capture free prose unchanged at run-time, project into typed fields lazily with an LLM for querying.** autolab's equivalent is `annotation_extract` — an Interpretation Operation that reads an Annotation's body and writes a structured Claim Record with extracted tagged facts. Original prose stays immutable in the ledger; structure is recovered on demand.

### What autolab does much better
Both LISTER and Dagdelen et al. are post-hoc research pipelines, not in-loop features. autolab ships it as a first-class Operation running while the Campaign runs, with extracted structure becoming part of the same queryable ledger. **No surveyed autonomous-lab framework does this in-loop.**

---

## 7. Four differentiators (the positioning one-liners)

These are defensible from the survey and shippable inside the 6-day budget because the primitives (Operation, Record, Annotation, `react()`) are already in the design.

1. **The only autonomous-lab framework with framework-enforced, write-ahead, hashed provenance** — where "framework-enforced" means an Operation *cannot* skip it. Every other surveyed system relies on user discipline (MLflow, W&B), post-hoc export (AlabOS), or proprietary bolt-on (eLabFTW timestamping).
2. **The only autonomous-lab framework where the agent reads rendered figures and revises the plan mid-experiment** — vision + `react()` + a mutable plan tree. Everyone else runs fixed DAGs.
3. **The only autonomous-lab framework where scientific intuition — narrative notes, failed attempts, off-target samples — is first-class queryable evidence, not ELN-exiled prose.** Autonomous labs skew rigid; ELNs skew unstructured; autolab does both.
4. **The only autonomous-lab framework where every LLM call is itself a Record** — replayable from cache, with hashed prompt and model ID, so the agent is provably replaceable without breaking the science.

---

## 8. Action items

These fall out of this landscape analysis and should go on the build backlog:

- **[Leverage]** Reserve the `autolab.*` tag namespace for system-emitted tags.
- **[Leverage]** Ledger query DSL modelled on MLflow's (`tags.foo = 'x' and outputs.Hc_kA_per_m >= 800`).
- **[Leverage]** RO-Crate exporter — `autolab export <campaign-id> --format ro-crate`.
- **[Leverage]** PROV-shaped ledger view — `GET /ledger/prov?campaign=…`.
- **[Leverage]** LabIMotion-style Segments — per-Lab typed metadata blocks attachable to any Record. Likely v1.1 if time forces a cut; at minimum reserve the design slot.
- **[Leverage]** Text Template pattern for Console annotation entry — prewritten prose stubs with blanks.
- **[Differentiator]** Ship `POST /records/{id}/annotations` on day 1. Annotation is a Record. Hashed, append-only, authored.
- **[Differentiator]** Ship `annotation_extract` as a v1.1 Interpretation Operation. Demo-eligible if time allows.
- **[Differentiator]** Every Claude call (whether Planner `react()` or an Interpretation Operation) writes a Record with hashed prompt + model ID. No exceptions.
- **[Differentiator]** `autolab replay <campaign-hash>` is demo-critical — it is the credibility anchor that distinguishes autolab from every ELN, every tracker, and every other autonomous lab.

## 9. Where this doc sits

- Companion to [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md). That doc records the *internal* decisions (no Skill, metadata shape); this doc records the *external* positioning (vs. other systems).
- Should be re-checked before writing any marketing prose, the README opening paragraph, the demo video voiceover, or the submission summary. Do not re-derive the landscape — use this.
- Update in-place if a new system class appears worth benchmarking against (e.g. protein-design autonomous labs, catalysis self-driving labs) or if an existing system ships a major feature that changes the comparison.
