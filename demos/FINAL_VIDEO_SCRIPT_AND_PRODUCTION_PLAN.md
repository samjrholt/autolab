# autolab trailer — submission cut

3:00 target · autolab visible by 0:35 · one search problem · one adaptation · one scheduler proof · one ledger proof · one clean payoff

This cut combines the cinematic thesis with the working-MVP proof. The viewer should leave with one sentence:

> autolab is an autonomous lab where Claude plans, tools run, resources are scheduled, and every decision becomes replayable scientific evidence.

Submission-day rule: **do not add new product features for the video.** Tighten the story, record deterministic demo assets, and ship a clean framework repo with the sensor demo as an example pack.

---

## ACT 1 — THE PROBLEM

### Pod 1 (0:00 – 0:16) — The Imagination Gap

**Visual:** Warm paper. Lora serif words fade in one at a time: *Bronze. Iron. Steel. Silicon.* Question mark. No UI yet.

**Voiceover:**
Every era is defined by its materials.
Bronze. Iron. Steel. Silicon.

AI can now imagine millions of candidates.

But imagination is not the bottleneck anymore.
Proof is.

**On-screen caption:** "Imagination is not the bottleneck."

---

### Pod 2 (0:16 – 0:35) — Proof Needs Provenance

**Visual:** Fast hand-drawn sequence: scattered CSVs, a notebook, a failed run, then a single value card — "coercivity = 2T" — surrounded by missing context: geometry, sweep rate, material, instrument state.

**Voiceover:**
Real science is messy.

Data is scattered.
Failures are rarely published.
Context lives in notebooks, folders, and memory.

A measurement without its history is just a number.

Property without provenance is noise.

**On-screen caption:** "Property without provenance is noise."

---

## ACT 2 — THE IMPLEMENTATION

### Pod 3 (0:35 – 0:55) — Meet autolab

**Visual:** Clean transition into the autolab Console. Three regions highlight in sequence with amber callouts: planning / evidence rail (Brain), resource-lane Gantt (Hands), scrolling record list (Ledger).

**Voiceover:**
So I built autolab.

An autonomous lab with three simple parts.

Brain: Claude reads the lab record, chooses from the available tools, designs experiments, and reacts as evidence comes in.
Hands: autolab routes each step to the right tool and resource, so the work actually runs.
Ledger: every action, result, claim, and failure becomes a record.

The record is the foundation.

**On-screen caption:** "Brain. Hands. Ledger."

---

### Pod 4 (0:55 – 1:25) — One Search Problem Inside The Lab

**Visual:** Screen recording. Two prepared runs — Optuna and Claude — start on the same search space. Resource lanes fill in parallel; plan cards move from queued to running to complete; ledger rows tick in. Keep the Console visible, not just the comparison chart.

**Voiceover:**
Here is one materials-design problem inside autolab, run two ways.

Both runs have the same goal: design a better magnetic sensor.
Both get the same budget: twelve real physics simulations.

One uses standard Bayesian optimisation.
The other is planned by Claude.

autolab schedules the work across the VM resource, updates the plan, and records every action as it happens.

**On-screen caption:** "One goal in. A whole lab moving."

---

### Pod 5 (1:25 – 2:10) — From Baseline To Reaction

**Visual:** Zoom into the Console reasoning rail and plan tree.
- Optuna baseline: scattered candidates, objective improves slowly, plan cards complete without physics rationale.
- Trial 1: Fe16N2 · sx=60 nm · sy=10 nm → 400 mT. Highlight: "highest-Ms material", "strong aspect ratio", "shape anisotropy".
- Ledger row / claim appears with Claude rationale.
- Planner reacts: Trial 2 is added/refined.
- Trial 2: Fe16N2 · sx=68 nm · sy=6 nm → 500 mT. Highlight: "exploit", "extreme elongation", "push Hmax higher".

**Voiceover:**
Bayesian optimisation sees a number.
It samples, updates, and slowly improves.

Then Claude gets the same lab, the same budget, and the same tool catalogue.

This is where autolab becomes different.

Claude starts from physics: it intuits the highest-magnetisation material, stretched into a high-aspect-ratio shape.

Trial one reaches 400 millitesla.

That result is written to the ledger.
Then the planner reacts to the record.

Claude pushes the same idea further: thinner, longer, more shape anisotropy.

Trial two hits 500.

The important part is not that Claude made a suggestion.
It is that every result becomes a record, and the plan changes because of that record.

**On-screen caption:** "Evidence in. Plan updated."

---

## ACT 3 — THE CONSEQUENCES

### Pod 6 (2:10 – 2:35) — Claude Beats Blind Optimisation

**Visual:** Full-screen chart (`var/demo_lab/_compare_optuna_vs_claude.png`). Reveal Optuna first: best-so-far climbs until trial 12; scattered circles across the search space. Then reveal Claude: flat at 500 mT from trial 2; red Fe16N2 squares clustered around the physics-informed region.

**Voiceover:**
This is the result.

Standard Bayesian optimisation found it on trial twelve.

Claude found it on trial two.

Six times faster.

Not because it got lucky.
Because it could reason with the physics and refine with new evidence.

**On-screen caption:** "Claude found it 6× faster."

---

### Pod 7 (2:35 – 2:50) — Every Step is Evidence

**Visual:** Camera glides into the ledger. 49 records. SHA-256 checksums. Claim records. Prompt hash / response text snippets. Parent-child links. Feels like receipts, not decoration.

**Voiceover:**
And this is why the result is trustworthy.

Every step leaves a receipt.

The simulation.
The Claude claim.
The planner decision that followed.

Each one is hashed.
Each one is append-only.
And each one points back to the evidence it used.

**On-screen caption:** "The record is the foundation."

---

### Pod 8 (2:50 – 3:00) — The Dataset Is the Moat

**Visual:** Pull back from one run to many. Successful trials, failed trials, Claude claims, Optuna trials, ledger records become a growing map. Then return to warm paper: *Bronze. Iron. Steel. Silicon.* A new word fades in: *autolab.*

**Voiceover:**
This is the real prize.

A growing memory of what worked, what failed, and why.

Every campaign adds evidence.
Every record makes the next decision smarter.

autolab is the autonomous lab for the next materials era.

**On-screen caption:** "Every campaign makes the next one smarter."

---

## Final title card

```
autolab
The autonomous lab for the next materials era.
Apache-2.0 · github.com/samjrholt/autolab
```

---

## Notes

- `autolab` is always lowercase
- British spelling: optimiser, optimisation
- On-screen captions are short; voiceover carries the full story
- Technical terms (hashes, trial numbers, field values) appear in the UI visually, not spoken aloud
- Do not end on replay — close on the compounding dataset
- Speak slowly. Let silence do some of the work.
- Product should appear by 0:35. Do not spend a full minute on the problem before showing the thing that was built.
- The race is one search problem inside autolab, not the whole product. Keep the larger claim: closed-loop autonomous science with provenance as the foundation.
- Make `react()` explicit in plain English: result written to ledger -> planner reacts -> plan changes.
- If live Claude latency is risky, record from a seeded/prior ledger. Deterministic capture is acceptable because replayable evidence is part of the product story.

---

## Product Readiness For This Story

Ship the repo as a **clean alpha framework** with the sensor workflow as a registered demo pack, not as a demo-only app.

Must be true before recording/submission:

- `pixi run clean && pixi run serve-prod` boots an empty/default Lab without demo clutter.
- `pixi run sensor-demo` registers the VM resource, sensor capabilities, workflow, and queued Claude/Optuna campaigns.
- The Console can show: resource lane activity, plan status, Claude reasoning/claims, result spotlight/chart, and ledger records.
- The ledger contains real claim annotations with `prompt_sha256`, `response_text`, `model`, `offline`, record checksums, and parent/target links.
- `pixi run autolab verify --root var/demo_lab` or the equivalent `/verify` endpoint passes for the demo ledger used in recording.
- `pixi run test`, scoped `pixi run lint`, and `pixi run frontend-build` are green after final source changes.

Do not build for the video today:

- New navigation or IA.
- New provenance side panels.
- A preflight UI.
- More example workflows.
- Physical-lab claims not shown by the demo.

Commit policy:

- Commit source, docs, tests, demo registration scripts, and built frontend assets if the server depends on them.
- Do not commit local ledgers, runtime logs, `.autolab-work`, generated temp outputs, or personal machine paths.
- If keeping a demo evidence asset in the repo, put it under a deliberate documented fixture path, not under `var/` runtime state.

---

## Previous Recorded Transcripts

> Generated by `transcribe.mjs` from the recorded M4A files. These are reference transcripts from the previous cut; use the timed script above for the submission retake/edit.

### Pod 1 — The Imagination Gap

Every era is defined by its materials. Advanced materials are the foundations of everything we build, use and rely on, from energy to medicine, from transportation to computation. But materials discovery is slow. Decades of trial and error. The biggest breakthroughs are often accidents. AI is starting to change that. Researchers already use it to imagine millions of new materials, but imagination is not the bottleneck anymore. Proof is, we need to ground prediction and reality, and the lab is the bottleneck.
### Pod 2 — How Science Actually Runs

I work as a material scientist, as a physicist, and real science is messy. Data are scattered, failures are never published. Machine learning, people say, garbage in, garbage out. In AI for science, at the moment, it's nothing in, nothing out.
### Pod 3 — Property Without Provenance

I see this in my day-to-day, that the deeper problem is provenance. The same composition of a material, different processing, and we get completely different results. Without this additional context, even good data is just noise.
### Pod 4 — Meet autolab

For this hackathon, I've built Autolab, an autonomous lab built around three main ideas to try and speed up this material's discovery and scientific progress. One is a brain, so clawed, to try and decide what we should try next, where we should investigate. Two is hands to actually run the tools that we have in our lab, and three is a ledger that remembers everything that we do.
### Pod 5 — The Race Starts

Let's take an example of trying to design a better magnetic sensor. So we have the same problem, and let's do it in two different ways. One driven by Claude, and the other driven by standard Bayesian optimisation. Autolab runs them both, and we give them both the same budget of 12 different real physics simulations that it can do.
### Pod 6 — Claude Reasons Like a Scientist

Bayesian optimisation just tries to optimise this numerical value. And we can see that as it does trials, as it calls some real physics simulations, it does get better over time, but slowly.
### Pod 7 — Claude Beats Blind Optimisation

Claude, on the other hand, starts with reasoning, starts with physics, and given its target says we want the highest magnetization material, and we know we want a long thin shape. So in one trial, it gets 40 mSv, Tesla. The second trial, we can look at its reasoning, and it pushes the same idea even further, refining it.
### Pod 8 — Every Step is Evidence

The results really speak for themselves. Claude reaches the optimum at the second trial. Bayesian optimisation reaches it at trial 12. It's six times faster to use Claude as our reasoner and physics than Bayesian optimisation in this example.
### Pod 9 — The Dataset Is the Moat

Every step of this race is recorded. All of the records, all hashed, all appending the ledger. And the real prize in this is not one lucky result, it's a data set that works. What failed and why? Every campaign making the next one smarter, recording everything. Autolab, this is the autonomous lab for the next generation of science.
