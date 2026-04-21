# 2026-04-22 — Interpretations, metadata capture, and the "Skill" decision

This doc consolidates design decisions reached on 2026-04-22 that affect two things: (a) how interpretive reasoning is modelled in autolab, and (b) how metadata — structured and free-text — is captured on Records. Written in the same commit that removes `Skill` from `GLOSSARY.md`.

Supersedes Skill-related language in [autolab-ideas-foundation.md](autolab-ideas-foundation.md), [hackathon-plan.md](hackathon-plan.md), and the Brain-layer descriptions in CLAUDE.md and README.md.

## 1. Framing correction

autolab is **primarily an autonomous lab**. Claude orchestrates experiments and thinks like a scientist; the ledger is how that autonomy stays honest and how evidence compounds across campaigns. The ledger is not the product — the deliverable is goal-shaped (a material, a trend, a Pareto frontier, a sensor design) and the ledger is the substrate that makes it trustworthy and reusable.

Prior framing — "a scientific record with an agent attached" — was overcorrection. Replace with: **an autonomous lab with provenance as its foundation**.

## 2. "Skill" is removed as an autolab abstraction

`Skill` was borrowed from Anthropic's `SKILL.md` construct and conflated two things: (a) Claude-side reasoning patterns (which are a harness concern, not an autolab concern), and (b) the scientific act of *interpreting* a measurement.

**Decision: interpretations are Operations.** A `pxrd_interpret` capability takes a record-ID pointing at an XRD record, its adapter calls Claude with the rendered PNG, and it writes a Claim-shaped Record. Same as any other Operation. No new abstraction, no Skill concept.

Consequences:

- The `Claim` glossary entry is retained but re-sourced: "returned by an interpretation Operation (typically an LLM-backed adapter that reads a record or figure)." Confidence is still mandatory. Validation runs still link via `parent_ids`.
- The `resource` for an interpretation Operation is `claude-opus` (or similar), capacity = concurrent calls allowed. This makes LLM usage visible to the scheduler and replayable from cache.
- The ai-lab-software prior art never had a Skill abstraction either — the orchestrator/planner loop was enough. Confirmed in [C:\Users\holtsamu\repos\ai-lab-software/matdiscovery/orchestrator.py:233–290](file:///C:/Users/holtsamu/repos/ai-lab-software/matdiscovery/orchestrator.py#L233-L290).

What replaces the "five Skills" plan from hackathon-plan.md §5 day-2: a handful of interpretation Operations (`pxrd_interpret`, `hysteresis_interpret`, `phase_purity_estimate`, etc.) registered the same way any other capability is. Each gets a `tool.yaml`, an adapter, and lands in the ledger next to `arc_melt` and `xrd_measure`.

## 3. Metadata capture — the converged pattern

A 2026-04-22 survey of the field (ELNs, LIMS, provenance standards, ML experiment trackers, autonomous-lab frameworks) found near-universal convergence on five patterns. autolab adopts all five.

1. **Template-per-experiment-kind, no global schema.** Each capability's `tool.yaml` declares typed inputs and outputs. There is no attempt at a universal schema across capabilities. Matches Benchling's entry-schema + structured-tables pattern and Chemotion's Segments model.
2. **Four-tier record shape: typed metrics + typed config + controlled-vocabulary tags + one markdown notes blob per record.** MLflow and Weights & Biases converged on this independently. autolab's `Record` already carries typed `outputs`, `inputs`, `tags: list[str]`, and per-Record `annotations: list[Annotation]`.
3. **Free text rides on the thing it describes, not in a separate notes table.** PROV, RO-Crate, CWL, MLflow, W&B all put `description`/`comment`/`doc`/`note` as a field on every typed node. autolab puts it on the Record.
4. **Tags are the universal escape valve** between rigid schema and free prose. Cheap to write, cheap to search, degrade gracefully into a folksonomy. Enforce nothing at framework level; let Campaigns define controlled vocabularies if they want.
5. **Full-text search is table-stakes; semantic search is bonus.** Index annotation bodies for substring match at minimum. Embedding search is v1.1.

## 4. The opening — narrative evidence as first-class

The survey's most useful finding: **autonomous labs currently under-serve free-text human context.** AlabOS, ChemOS, BayBE, Emerald Cloud Lab all skew rigidly typed; the technician's intuition ("don't run left electrode hot today," "batch smelled weird today," "I think this phase is more useful than we realised") has no native home. The only exception is Coscientist, where the LLM trajectory *is* the record by accident — narrative-first because the agent's reasoning is the artefact.

autolab's opening: **treat narrative evidence as first-class, append-only, queryable.** Concretely:

- `POST /records/{id}/annotations` on any Record at any time. A technician's note about `arc-furnace-1` becomes an Annotation on that Resource's most recent maintenance Record, or a free-standing Annotation on the Resource entity itself.
- Every Annotation is a Record in its own right: hashed, append-only, immutable, timestamped, authored.
- Annotations carry `tags` and a free `content` field. That is it.
- An optional interpretation Operation — `annotation_extract` — can be run later to project annotation prose into typed fields for querying. The original prose stays untouched. This is the in-loop version of what [LISTER](https://www.researchgate.net/publication/374322736_LISTER_Semiautomatic_Metadata_Extraction_from_Annotated_Experiment_Documentation_in_eLabFTW) and [Dagdelen et al. 2024](https://www.nature.com/articles/s41467-024-45563-x) do post-hoc for ELN text and scientific papers.

No autonomous-lab framework surveyed does this in-loop. It is a real opening.

## 5. Sharpened positioning

autolab is **the autonomous lab that treats scientific intuition — human narrative, failed attempts, off-target samples, fleeting technician context — as first-class, append-only, queryable evidence**, driven by an agent that thinks like a scientist because it's reading the same record a scientist would. Every other autonomous lab either types everything rigidly and loses the prose, or logs the prose and never recovers structure. autolab does both.

## 6. Concrete follow-ups for the build

- Remove `Skill` as a term from `GLOSSARY.md`; add a deprecated note. ✅ in this commit.
- Update `CLAUDE.md` framing paragraph and remove the "Skill count is not locked" bullet. ✅ in this commit.
- Update `README.md` three-layer description so "Brain" is Claude-as-Planner/PolicyProvider, not Claude-plus-Skills. ✅ in this commit.
- Leave `autolab-ideas-foundation.md` and `hackathon-plan.md` marked as partially superseded; add explicit pointer to this doc.
- Ensure the Record dataclass ships with `tags: list[str]` and `annotations: list[Annotation]` from day 0 (ai-lab-software's [models.py:162–208](file:///C:/Users/holtsamu/repos/ai-lab-software/matdiscovery/models.py#L162-L208) is the template to copy).
- Add `POST /records/{id}/annotations` to the Lab HTTP surface and an Annotation entry form to the Console.
- `annotation_extract` is v1.1 unless the demo narrative needs it.
