# autolab trailer — submission cut

3:00 target · product visible by 0:35 · one campaign · one adaptation · one ledger proof

This cut combines the cinematic thesis with the working-MVP proof. The viewer should leave with one sentence:

> autolab is an autonomous lab where Claude plans, tools run, resources are scheduled, and every decision becomes replayable scientific evidence.

Submission-day rule: **do not add new product features for the video.** Tighten the story, record deterministic demo assets, and ship a clean framework repo with the sensor demo as an example pack.

---

## ACT 1 — THE PROBLEM

### Pod 1 (0:00 – 0:18) — The Imagination Gap

**Visual:** Warm paper. Lora serif words fade in one at a time: *Bronze. Iron. Steel. Silicon.* Question mark. No UI yet.

**Voiceover:**
Every era is defined by its materials.
Bronze. Iron. Steel. Silicon.

AI can now imagine millions of candidates.

But imagination is not the bottleneck anymore.
Proof is.

The bottleneck is the lab.

**On-screen caption:** "The bottleneck is the lab."

---

### Pod 2 (0:18 – 0:32) — How Science Actually Runs

**Visual:** Hand-drawn ink sketches in amber: scientist moving a USB stick between machines, stack of paper notebooks, scattered CSV icons, a fixed-arrow flowchart. Slightly chaotic, slightly absurd.

**Voiceover:**
Real science is messy.

Data is scattered.
Failures disappear.
Context lives in notebooks, folders, and memory.

In AI for science, the problem is often not garbage in, garbage out.
It is nothing in, nothing out.

**On-screen caption:** "Nothing in. Nothing out."

---

### Pod 3 (0:32 – 0:45) — Property Without Provenance

**Visual:** Two side-by-side panels. Left: a database card with one lonely value — "coercivity = 2T". Right: missing context fans out in ink annotations — annealing temperature, cooling rate, grain size, sweep rate, sample geometry, instrument state.

**Voiceover:**
The deeper problem is provenance.

The same composition can give completely different results depending on processing, geometry, and instrument state.

Without that context, even good data is noise.

**On-screen caption:** "Property without provenance is noise."

---

## ACT 2 — THE IMPLEMENTATION

### Pod 4 (0:45 – 1:05) — Meet autolab

**Visual:** Clean transition into the autolab Console. Three regions highlight in sequence with amber callouts: planning panel (Brain), resource-lane Gantt (Hands), scrolling record list (Ledger).

**Voiceover:**
So I built autolab.

An autonomous lab with three simple parts.

A Brain: Claude decides what to try next.
Hands: registered tools run simulations and experiments.
A Ledger: every action, claim, result, and failure is written down.

The record is the foundation.

**On-screen caption:** "Brain. Hands. Ledger."

---

### Pod 5 (1:05 – 1:30) — The Race Starts

**Visual:** Screen recording. Two prepared campaigns — Claude and Optuna — start on the same search space. Resource lanes fill in parallel; plan cards move from queued to running to complete; ledger rows tick in.

**Voiceover:**
Here is one campaign running inside the lab.

Same goal: design a better magnetic sensor.
Same budget: twelve real physics simulations each.

One planner is Claude.
One is standard Bayesian optimisation.

autolab schedules the work across the VM resource and records every action as it happens.

**On-screen caption:** "One goal in. A whole lab moving."

---

### Pod 6 (1:30 – 2:05) — Claude Reacts Like a Scientist

**Visual:** Zoom into the Console reasoning rail and plan tree.
- Trial 1: Fe16N2 · sx=60 nm · sy=10 nm → 400 mT. Highlight: "highest-Ms material", "strong aspect ratio", "shape anisotropy".
- Ledger row / claim appears with Claude rationale.
- Planner reacts: Trial 2 is added/refined.
- Trial 2: Fe16N2 · sx=68 nm · sy=6 nm → 500 mT. Highlight: "exploit", "extreme elongation", "push Hmax higher".

**Voiceover:**
This is where autolab is different.

Claude starts from physics: the highest-magnetisation material, stretched into a high-aspect-ratio shape.

Trial one reaches 400 millitesla.

That result is written to the ledger.
Then the planner reacts to the record.

Claude pushes the same idea further: thinner, longer, more shape anisotropy.

Trial two hits 500.

**On-screen caption:** "Evidence in. Plan updated."

---

## ACT 3 — THE CONSEQUENCES

### Pod 7 (2:05 – 2:28) — Claude Beats Blind Optimisation

**Visual:** Full-screen chart (`var/demo_lab/_compare_optuna_vs_claude.png`). Best-so-far panel. Claude flat at 500 mT from trial 2; Optuna reaches 500 mT only at trial 12. Scatter panel: Claude squares all red Fe16N2; Optuna circles scattered.

**Voiceover:**
This is the result.

Claude found the optimum in two trials.

Optuna — a standard Bayesian optimisation method — found it on trial twelve.

Six times faster.

Not because it got lucky.
Because it had words for the physics:
magnetisation, switching field, shape anisotropy.

**On-screen caption:** "Claude found it 6× faster."

---

### Pod 8 (2:28 – 2:45) — Every Step is Evidence

**Visual:** Camera glides into the ledger. 49 records. SHA-256 checksums. Claim records. Prompt hash / response text snippets. Parent-child links. Feels like receipts, not decoration.

**Voiceover:**
Every part of that race is recorded.

Forty-nine records.
Each hashed.
Each append-only.

The Claude claim is a record.
The simulation result is a record.
The next decision links back to both.

**On-screen caption:** "The record is the foundation."

---

### Pod 9 (2:45 – 3:00) — The Dataset Is the Moat

**Visual:** Pull back from one run to many. Successful trials, failed trials, Claude claims, Optuna trials, ledger records become a growing map. Then return to warm paper: *Bronze. Iron. Steel. Silicon.* A new word fades in: *autolab.*

**Voiceover:**
This is the real prize.

Not one lucky result.
A dataset of what worked, what failed, and why.

Every campaign makes the next one smarter.

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
- Product should appear by 0:35-0:45. Do not spend a full minute on the problem before showing the thing that was built.
- The race is one campaign inside autolab, not the whole product. Keep the larger claim: closed-loop autonomous science with provenance as the foundation.
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

## Actual recorded transcripts

> Generated by `transcribe.mjs` from the recorded M4A files.

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
