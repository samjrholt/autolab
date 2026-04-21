# Scenarios

**Pressure tests on the framework, not a contract on any vertical.**

Each scenario below is a real scientist workflow the abstractions in [GLOSSARY.md](GLOSSARY.md) must express without awkwardness. If an architectural choice makes any scenario harder to live than it already is, the choice is wrong. The **specific materials and numbers** in any scenario (Fe-Co-Mn, L1₀, 1200 °C, GMR sensors, DFT on 100 compositions, MaMMoS chain, …) are chosen for concreteness and may change — the framework must not. We may swap the demo vertical entirely; the framework must not follow.

When you find yourself uncertain about a Record field, a Planner signature, a Resource property, or a `react()` action, walk the scenarios and check that each remains expressible.

This is a living document. Add new scenarios when you encounter cases the framework handles awkwardly.

**Terminology note.** Read [GLOSSARY.md](GLOSSARY.md) first. "Operation," "Sample," "Record," "Resource," and the `react()` Action vocabulary are load-bearing terms used below without further explanation.

---

## Scenario 1 — Iterative synthesis refinement (branch on partial success)

**Narrative.** Scientist picks Fe₅₅Co₂₅Mn₂₀. Weigh → mill → sinter (60 °C/h ramp, 1200 °C × 48 h, 60 °C/h cool). PXRD shows 60 % L1₀ phase. Not good enough, but not useless. Decision: re-sinter a fresh pellet from the same milled powder with quench cooling. **Also** measure the current 60 % sample — it is still data. Two magnetometry measurements follow from one milled powder jar.

**Framework demand.**
- The milled powder is a **Sample** — a first-class, identified thing the `mill` Operation produces (`produces_sample: true`) that can be consumed by two downstream Operations.
- Workflows must branch on a Sample, not just on success / fail. Two Experiments may share a common parent Record via `parent_sample_ids`.
- Both measurement paths produce usable dataset rows. Neither is "the answer," but both correlate phase purity with coercivity.

**`react()` mapping.** `branch` from the mill Record — pursue slow-cool and quench paths in parallel. Both arms proceed through PXRD and magnetometry.

**Implementation note.** The mill Record's `sample_id` is the stable identifier. Both downstream sinter Operations' `inputs.source_record_ids` point to the mill, and their own Records inherit the mill's `sample_id` via `parent_sample_ids` until a Sample-producing sinter mints a new one. Policy decision: **branch creates two Experiments sharing a parent Record**, not one Experiment with two tails. Rationale: one Experiment = one DAG = one dataset row. This keeps the `group_id` semantics clean.

---

## Scenario 2 — Total synthesis failure, retry reusing upstream

**Narrative.** Pick a high-Mn composition. Weigh → mill → sinter at 1200 °C × 48 h. Open furnace — sample is a puddle. Eutectic melting. No sample exists: cannot PXRD, cannot magnetometry. Decision: log the failure, retry sintering at 1000 °C using the **same milled powder** still in the jar.

**Framework demand.**
- When an Operation fails, the downstream Operations in that Experiment cascade-skip (correct behaviour for the first attempt).
- A retry must specify a **new upstream Sample** — starting from the mill, not from the failed sinter.
- The "reuse upstream" decision is explicit in the Record's lineage, not implicit.

**`react()` mapping.** `retry_step` with modified params (`temperature: 1000`) **and** `source_record_ids` pointing to the mill Record, not the failed sinter.

**Implementation note.** The `retry_step` action must accept both `params` and `source_record_ids`. A naive "retry from scratch" would rerun the mill — wasteful and provenance-lossy. The resulting lineage:
```
mill ─┬─ sinter₁ (failed)
      └─ sinter₂ (success) → pxrd → magnetometry
```
Both sinter Operations share mill as parent. The failed branch stays in the ledger as a Record with `status: failed` and a reason — failures are data, not exceptions.

---

## Scenario 3 — Unexpected phase, pivot to different characterisation

**Narrative.** Pick Fe₇₀Co₃₀ expecting a bcc soft magnet. PXRD returns L1₀ ordering — a hard magnet. More interesting than planned. Scientist adds steps not in the original workflow: hysteresis loop + high-temperature VSM to find the Curie point.

**Framework demand.**
- The Workflow is not fixed at campaign start. `react()` can introduce Operations that weren't in the initial DAG.
- New Operations must already exist as registered capabilities in the Lab's Tool registry — the Planner cannot invent tools.
- Adding a characterisation step mid-flight is a first-class action, not a workaround.

**`react()` mapping.** `add_step` — splice `hysteresis_loop` and `vsm_curie_temperature` into the workflow after PXRD.

**Implementation note.** This pressures the Tool registry to be **broad from day 0** — `pxrd_measure`, `hysteresis_loop`, `vsm_curie_temperature`, `sem_image`, `dsc`, etc., even if several are thin surrogates or stubs for the hackathon. If the Planner wants a capability the Lab doesn't have, the correct escape hatch is `ask_human` → register a new capability (which is itself a hashed Record: a "registration intervention"). Tools cannot be invented by the agent.

---

## Scenario 4 — Resource orchestration at Campaign scale (**the demo's #1 beat**)

**Narrative.** The Lab has been booted with a realistic set of Resource instances — for example 2 × arc furnace, 1 × tube furnace, 1 × SLURM partition, 1 × SQUID, 1 × PXRD. The scientist submits a Campaign with a goal and a budget. The Principal Agent decomposes it, spawns a Campaign subagent, and the Planner's first `plan()` returns a **batch of Operations spanning several Experiments** — five candidate compositions, each with its own Workflow.

Immediately, things start in parallel: arc-furnace-1 takes composition A's melt; arc-furnace-2 takes composition B's melt; the SLURM partition begins composition C's MLIP relax; the tube furnace is idle waiting for a sintering step. When A's melt completes, A moves to PXRD while the arc furnace accepts composition D. When A's PXRD comes back, A moves to SQUID while the tube furnace picks up A's next heat-treatment step — and meanwhile C's DFT is still running on SLURM. No Resource is idle while work is ready. Experiments A–E are all alive at once, threaded through the shared pool.

The Console shows this: each Resource instance is a lane on the screen; Operations are pills that fill their lanes while running; the plan tree above shows five Experiments growing in parallel; records land in the ledger panel as they complete. The scheduler is doing clever work and a scientist in the audience can see it — that is the beat.

**Framework demand.**
- Resources are **named instances**, not counted pools. `arc-furnace-1` and `arc-furnace-2` are distinct; an Operation requesting `kind: arc_furnace` acquires any free compatible instance.
- The scheduler interleaves Operations **across Experiments within the same Campaign** on shared Resources. Per-Experiment execution must not be strictly linear.
- `Planner.plan(history, resources) → list[ProposedOperation]` may return Operations belonging to different Experiments. The orchestrator dispatches greedily against free compatible Resources.
- Resource acquisition is atomic (one `asyncio.Lock` per ResourceManager acquire) — no double-booking.
- Capability matching: an Operation may declare capability requirements (e.g. `kind: arc_furnace, requires: {max_temp_gt: 1400}`); the scheduler filters Resource instances before acquiring.
- The Console renders Resource-lane activity in real time over WebSocket (one event per acquire / release / start / complete).

**`react()` mapping.** Not a `react()` scenario — this is `plan()` + the scheduler. But it is the beat the scheduler is *for*, and `react()` decisions in subsequent scenarios will happen *inside* this live plan tree, which is what makes their visual impact land.

**Implementation note.** This is the place where autolab genuinely goes past the prior art. Comparable autonomous-lab frameworks do multi-campaign scheduling (one Orchestrator per Campaign, shared ResourceManager), but their per-Experiment execution is sequential — Experiment A completes fully before Experiment B starts inside the same Campaign. The demo's #1 beat is cross-experiment interleaving inside a single Campaign on typed, instanced Resources with live visualisation. Everything else in the build ties back to making this beat possible.

---

## Scenario 5 — Quality gate with human override

**Narrative.** Sinter → PXRD reports 45 % target phase. Automatic threshold is 50 %, so the Planner's default is re-sinter. Scientist looks at the pattern: "the secondary phase is interesting — measure it anyway." Human overrides the auto re-sinter decision.

**Framework demand.**
- QC layers flag sub-threshold results and recommend an action.
- `react()` has an action that pauses the Experiment and waits for human input — the Lab does not block globally, but the Experiment does.
- The human's response is a hashed Intervention Record linked to the pause Record, so the override is auditable.

**`react()` mapping.** `ask_human` — write an "awaiting human decision" Record listing the proposed actions; park the Experiment; resume on Intervention.

**Implementation note.** This is the load-bearing argument for the Lab being a persistent service. An `ask_human` in a one-shot CLI invocation is useless. In a running Lab, the Experiment enters a `paused` state, the Console displays the ask, the scientist responds through the intervention endpoint, and a resume Record unblocks the Experiment. Timeout policy: **wait indefinitely**, surface the wait prominently in the Console. Never auto-continue a pause.

---

## Scenario 6 — Consumable precursor runs out mid-campaign *(added 2026-04-21)*

**Narrative.** Campaign targets Sm-Co-Fe alloys. Halfway through, the Sm powder jar is empty. Options: (a) pause until resupply arrives, (b) substitute a different precursor lot (different provenance!), (c) reprioritise the remaining queue to compositions that don't need Sm.

**Framework demand.**
- A Resource is not just a capacity count — it also has **consumable inventory**. An Operation's run decrements the consumable.
- A Resource reaching its threshold fires a hook that triggers `react()`.
- A precursor substitution is itself a decision in the Record, visible in the dataset (the substituted lot may behave differently).

**`react()` mapping.** `ask_human` (which path to take?) or `replan` (drop Sm-bearing compositions from the remaining queue).

**Implementation note.** Extends the Resource shape from `{name, kind, capacity}` to `{name, kind, capacity, consumables: {...}}`. Each Operation declaration names the consumables it draws from. For the hackathon, two simulated consumables are enough to earn the architectural claim. The alternative — omitting consumables for v1 — means Scenario 6 lives only in the docs, which is acceptable but weaker.

---

## Scenario 7 — Instrument drift caught by cross-record QC *(added 2026-04-21)*

**Narrative.** The SQUID magnetometer has been reading ~5 % low for the last week against the Pd reference standard. Multiple recent magnetometry Records are affected. QC at layer 1 (instrument calibration) flags the trend. Lab needs to: (a) pause further magnetometry, (b) annotate affected Records with a provisional correction, (c) schedule a calibration run, (d) optionally re-measure high-value samples.

**Framework demand.**
- QC runs can inspect **across Records**, not just within one — it's a Hook that sees the ledger slice.
- Records can be retroactively **annotated with a provisional correction** without mutation. The Annotation itself is a Record.
- The Planner can compose a response spanning multiple affected Experiments.

**`react()` mapping.** `add_step` (calibration run) + Annotations on affected Records + optional `retry_step` on high-value magnetometry runs.

**Implementation note.** This scenario is the "self-calibration" story from ideas-foundation §8 made concrete. For the hackathon we do not build a real drift detector; we build the *machinery* — cross-record QC Hook, Annotation-on-existing-Record, provisional-correction field in the Record schema — and demonstrate it firing on a scripted drift event. The machinery earns the architectural claim; the detector is a v1 concern.

---

## Scenario 8 — Multiscale computational chain (structure → Hc) *(added 2026-04-21)*

**Narrative.** A Campaign wants an estimate of coercivity Hc for a family of candidate hard-magnet compositions. For each candidate the Planner proposes one Experiment with a four-step computational Workflow:

1. **Structure relaxation.** An MLIP (MACE, CHGNet, or MatterSim) relaxes the candidate crystal structure — minutes, not hours. Output: relaxed geometry Sample.
2. **Intrinsic parameters at 0 K.** The relaxed structure feeds a `mammos-dft` Operation (or a `mammos-ai` surrogate if the latency budget is tight) returning Ms, K1, A_ex as scalars with units.
3. **Temperature-dependent intrinsics.** The 0 K intrinsics feed a `mammos-spindynamics` Kuzmin-fit Operation returning Ms(T), K1(T), and Tc up to the target operating temperature.
4. **Hysteresis and coercivity.** The finite-T intrinsics feed a `mammos-mumag` finite-element micromagnetic Operation on a realistic grain geometry, returning a hysteresis loop and Hc.

If Hc meets the Campaign's `AcceptanceCriteria`, the Planner's `react()` returns `accept`. If a step fails (DFT doesn't converge, micromagnetics instability), `react()` returns `retry_step` with adjusted params. If `mammos-ai` returned a surrogate value and Hc is borderline, `react()` returns `add_step` scheduling a full `mammos-dft` confirmation run.

**Framework demand.**
- The same Operation / Resource / Record / `react()` abstractions hold when every step is computational. No "physical lab" special case in the framework.
- Resources here are `slurm-partition-gpu`, `dft-licence-pool`, `cpu-worker`. Typed instances with capability dicts (`{gpu_count, mem_gb, eligible_codes: ["vasp", "quantum-espresso"]}`).
- Samples are digital but still first-class (the relaxed structure, the parameter set, the hysteresis curve). `produces_sample: true` on the relax Operation; downstream Operations carry `parent_sample_ids`.
- Every step knows how to declare a surrogate via `mammos-ai`. Per the "surrogates are never silently substituted" invariant, the Record's `module` field is `mammos-ai.v0.3` vs. `mammos-dft.v1.2` — the Planner can filter on it.

**`react()` mapping.** `accept` on passing Hc; `retry_step` on convergence failure (new initial spin config or tighter SCF); `add_step` to promote a surrogate result to a full DFT confirmation; `ask_human` if the relaxed structure falls outside expected space-group set (possible phase transition).

**Implementation note.** This is the leading candidate for **the cool example workflow** the hackathon demo runs. Everything in it is real physics, every step has a MaMMoS subpackage, surrogates keep the demo responsive, and the chain is visibly multiscale (Å to µm to macroscopic Hc). The framework itself must stay ignorant that this example exists — it is declared as YAML Tool declarations and Python adapters in the tool registry, nothing more. If we replace this example with catalysis or protein design next month, none of the framework code should need to change.

---

## Scenario 9 — Planner proposes; human chooses differently *(added 2026-04-21)*

**Narrative.** Planner's batch proposes the next five compositions, with Co₆₀Fe₄₀ at the top. Scientist: "I've seen this system — Co₅₅Fe₄₅ first, the single-phase window is narrow." The scientist's choice runs. The Planner's proposal was not wrong, just overridden.

**Framework demand.**
- Proposed Operations are **first-class Records** with `record_status: proposed` *before* they run.
- Human overrides pick from the proposed set (or inject a new one) without deleting the unchosen proposals.
- The ledger retains a lossless account of **what the agent considered**, not only what it did.

**`react()` mapping.** Not a `react()` scenario — the action is a human Intervention that chooses among proposals. The Planner's next `plan()` call sees both the proposal history and the actual execution history.

**Implementation note.** This costs almost nothing and buys a lot: when the Planner suggests N next steps, all N land as `proposed` Records immediately; the one that runs transitions to `running → completed`; the unchosen ones remain as `proposed` forever. This turns the ledger into a record of *reasoning*, not just *action*. It is also how the demo's plan-tree panel stays honest — the blooming tree is literal ledger state, not theatre.

---

## Principles we derive from this set

Patterns that recur across the nine scenarios — any of these becoming awkward to express is a signal the design is drifting.

1. **Samples are first-class.** The thing an Operation transforms has a `sample_id`, optionally `parent_sample_ids`, an `is_destructive` flag, and is minted only when `produces_sample: true`. A later Operation consuming an earlier one's output references it via `source_record_id`. Scenarios 1, 2, 4, 8 all hinge on this.
2. **Resources are named instances with typed capabilities.** Not counted pools. User-facing input may be "2 × arc furnace," but the scheduler sees `arc-furnace-1` and `arc-furnace-2`, each with a capabilities dict. Capability matching happens before acquisition. (Scenarios 4, 6, 8.)
3. **Failures are Records; retries share upstream.** A failed Operation lives in the ledger with `status: failed` and a reason. A retry is a new Operation with an explicit `source_record_ids` pointing to the earlier still-valid step, not a mutation of the failed one. (Scenarios 2, 7.)
4. **`react()` Action vocabulary is closed.** `continue`, `accept`, `stop`, `add_step`, `retry_step`, `replan`, `escalate`, `branch`, `ask_human`. No ad-hoc new Actions; if a scenario needs one, extend [GLOSSARY.md](GLOSSARY.md) first. (Scenarios 1–8.)
5. **The Lab is always on.** `ask_human`, cross-record QC, resource exhaustion handling, proposed-Record bookkeeping, cross-Experiment scheduling — all require a long-lived service. Ship the FastAPI server from day 0.
6. **Proposals are Records.** The ledger is not a log of what happened; it is a record of what was considered and what was chosen. Unchosen proposals stay in the ledger as breadcrumbs. (Scenarios 5, 9.)
7. **Annotations extend; they do not replace.** Corrections, retractions, drift flags, human notes — all land as new Records linked to the originals. The original is never touched. (Scenarios 2, 5, 7, 9.)
8. **The Tool registry is static per Lab boot.** The Planner cannot invent Tools; it can only propose `ask_human` when a needed capability is missing. Registering a new Tool is a hashed intervention, not an agent action. (Scenario 3.)
9. **Surrogates are labelled, never substituted silently.** If a `mammos-ai` surrogate answered, the Record's `module` field says so. The Planner may choose to promote a surrogate result to a full run via `add_step`. (Scenario 8.)
10. **A Campaign's goal is immutable.** A scientist who changes what they're optimising for stops the current Campaign and starts a new one. No auto-fork, no mutate-and-annotate. (Derived cross-cutting; no dedicated scenario.)

If any of these principles becomes awkward to honour in code, stop and re-read [GLOSSARY.md](GLOSSARY.md) before patching around it.
