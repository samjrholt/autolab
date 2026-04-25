# Final 3-Minute Autolab Video Script + Production Plan

Audience: non-technical judges, scientists, investors, and future users.

Goal: make autolab feel obvious, inspiring, and real. The viewer should leave with one sentence in their head:

> autolab is the autonomous lab for the next materials era.

This video should not feel like a software walkthrough. It should feel like a story about why science needs a new kind of lab, with the UI proving that the story is real.

---

## Final Structure

- **Total length:** 3 minutes
- **Format:** 9 pods of ~20 seconds
- **Narration:** Sam's own voice
- **Build method:** Remotion edit with replaceable screen-recording assets
- **Visual style:** warm, paper/ink/amber highlights, minimal captions, one clear visual idea per pod
- **Primary demo example:** magnetic sensor-shape optimisation
- **Narrative Arc:** Act 1 (The Problem) → Act 2 (The Implementation) → Act 3 (The Consequences)

For the Claude Code build prompt, use [REMOTION_CLAUDE_CODE_IMPLEMENTATION_PROMPT.md](REMOTION_CLAUDE_CODE_IMPLEMENTATION_PROMPT.md).

---


# Voiceover Script + Shot List

> Word-count target: Pod 1 is the long opener (~50s). Pods 2 and 3 are tight (~10s each). Pods 4-9 sit around 30-38 words at Sam's measured ~130 wpm. Cut words rather than speed up. Pauses are part of the budget.

---

## Act 1 — The Problem

### Pod 1 — The Imagination Gap

**Visual**
Warm paper background. Lora serif words fade in one at a time, paced to the voiceover: *Bronze. Iron. Steel. Silicon.* Then a question mark fades in. Subtle paper-grain texture; no UI yet.

**Voiceover** *(calm, spacious — ~105 words, ~50s with pauses)*

> Every era is defined by its materials.
> Bronze. Iron. Steel. Silicon.
>
> Advanced materials are the foundation of everything we build, use, and rely on.
> From energy to medicine. From transport to computation.
>
> But material discovery is slow.
> Decades of trial and error.
> The biggest breakthroughs are often accidents.
>
> AI is starting to change that.
> Researchers are already using it to imagine millions of new materials.
>
> But imagination is not the bottleneck anymore.
> Proof is.
> We need to ground prediction in reality.
>
> The bottleneck is the lab.

**On-screen caption (final beat)**

> The bottleneck is the lab.

---

### Pod 2 — How Science Actually Runs

**Visual**
Hand-drawn ink sketches in amber: a scientist moving a USB stick between machines, a stack of paper notebooks, scattered CSV icons, a fixed-arrow flowchart. Slightly chaotic, slightly absurd. Layered with subtle pencil-sketch lines that animate in.

**Voiceover** *(grounded, human — ~22 words, ~10s)*

> Real science is messy.
>
> Data is scattered. Failures are never published.
>
> In machine learning: garbage in, garbage out.
> In AI-4-science: nothing in, nothing out.

**On-screen caption**

> Manual. Brittle. Forgotten.

---

### Pod 3 — Property Without Provenance

**Visual**
Two side-by-side panels. Left: a database card showing one lonely property value: "coercivity = 2T". Right: the missing context fans out in ink annotations: annealing temperature, cooling rate, grain size, sweep rate, sample geometry, instrument state.

**Voiceover** *(the core diagnosis — ~22 words, ~10s)*

> The deeper problem is provenance.
>
> Same composition. Different processing. Completely different material.
>
> Without context, even good data is noise.

**On-screen caption**

> Property without provenance is noise.

---

## Act 2 — The Implementation

### Pod 4 — Meet Autolab

**Visual**
Clean transition into the Autolab Console. Three regions softly highlight in sequence with amber callouts: a planning panel (Brain), a resource-lane Gantt (Hands), a scrolling record list (Ledger).

**Voiceover** *(clear, introductory — ~32 words)*

> This is autolab.
>
> An autonomous lab built around three ideas.
>
> A Brain — Claude — to decide what to try next.
> Hands, to run the tools.
> And a Ledger, that remembers everything.

**On-screen caption**

> Brain. Hands. Ledger.

---

### Pod 5 — The Race Starts

**Visual**
Screen recording, sped up subtly. Register the sensor demo from the Console. Two campaigns start on the same search space: Claude and Optuna. Resource lanes fill in parallel; ledger rows tick in.

**Voiceover** *(quiet wonder — ~30 words)*

> Two campaigns. Same problem. Same budget.
>
> Design a better magnetic sensor.
>
> One driven by Claude.
> One by standard Bayesian optimisation.
>
> Autolab runs them both.

**On-screen caption**

> One goal in. A whole lab moving.

---

### Pod 6 — Claude Reasons Like a Scientist

**Visual**
Zoom into the Console reasoning rail. First show trial 1 as a cold start: Fe16N2, sx=60 nm, sy=10 nm, 400 mT. Highlight: "highest-Ms material", "strong aspect ratio", "shape anisotropy". Then cut to trial 2: Fe16N2, sx=68 nm, sy=6 nm, 500 mT. Highlight: "exploit", "extreme elongation", "push Hmax higher".

**Voiceover** *(this is the reveal — ~36 words)*

> Claude starts from physics.
>
> Highest-magnetisation material. Long, thin shape. Strong shape anisotropy.
>
> Trial one: 400 millitesla.
>
> It pushes the same idea further.
>
> Trial two: 500.

**On-screen caption**

> Physics first. Then evidence.

---

## Act 3 — The Consequences

### Pod 7 — Claude Beats Blind Optimisation

**Visual**
Full-screen chart: `var/demo_lab/_compare_optuna_vs_claude.png`. Start on the best-so-far panel. Highlight Claude flat at 500 mT from trial 2, then Optuna reaching 500 mT only at trial 12. Then briefly show the scatter panel: Claude squares all red Fe16N2; Optuna circles scattered across materials. Overlay a small contrast: "Claude: Ms, shape anisotropy, switching field" vs "Optuna: sample, update, sample".

**Voiceover** *(the punchline — ~32 words)*

> This is the result.
>
> Claude reaches the optimum at trial two.
>
> Bayesian optimisation reaches it at trial twelve.
>
> Six times faster — because Claude has the words for the physics.

**On-screen caption**

> Claude found it 6x faster.

---

### Pod 8 — Every Step is Evidence

**Visual**
Camera glides into the ledger. Show `var/demo_lab/ledger/ledger.jsonl` or the Console ledger panel. Highlight 49 records, SHA-256 checksums, claim records, and parent-child links. The style should feel like receipts, not decoration.

**Voiceover** *(proof-oriented, slower — ~32 words)*

> And every step of that race is recorded.
>
> Forty-nine records. Each hashed. Each append-only.
>
> Claude tells us what it thinks happened.
> The ledger shows what actually did.

**On-screen caption**

> The record is the foundation.

---

### Pod 9 — The Dataset Is the Moat

**Visual**
Pull back from one run to many. Successful trials, failed trials, Claude claims, Optuna trials, and ledger records become a growing map. Then return to the warm paper background: *Bronze. Iron. Steel. Silicon.* A new word fades in: *Autolab.*

**Voiceover** *(slow, quiet, certain — ~32 words)*

> This is the real prize.
>
> Not one lucky result. A dataset of what worked, what failed, and why.
>
> Every campaign makes the next one smarter.
>
> Autolab. The autonomous lab for the next materials era.

**Final title card**

> autolab
> The autonomous lab for the next materials era.
> *Apache-2.0 · github.com/samjrholt/autolab*

---

# Recording Notes for Sam's Voice

## How to record the voiceover

Record the voiceover first, before final screen captures. It will make the video much easier to edit.

Recommended setup:

1. Use your best available microphone.
2. Record in a quiet room with soft furnishings.
3. Record at least three full takes.
4. Smile slightly while speaking; it changes the tone.
5. Leave a one-second pause between pods so cuts are easy.
6. Do not try to sound like a presenter. Sound like a scientist explaining something important to an intelligent friend.

Target pace:

- Around 105-120 words per minute.
- The script is intentionally sparse enough that you can pause between ideas.
- If a pod runs long, cut words rather than speeding up.

TED-style delivery rule:

- Say one thought.
- Pause.
- Let the visual answer it.
- Then move on.

Delivery direction:

- Act 1: calm, serious, almost philosophical.
- Act 2: quiet wonder; show the system coming alive without sounding salesy.
- Act 3: confident, proof-oriented, slightly more energetic.
- Final line: slow down.

---

# How to Make the Video in Remotion

## Why Remotion is a good choice here

Remotion is good for this project because the video has:

- timed text
- screen recordings
- animated callouts
- charts
- replaceable assets
- a fixed 3-minute structure

Most importantly, Remotion lets you keep the video editable until the last moment. If the UI changes later, you only replace one screen recording file. You do not rebuild the whole video.

---

## Recommended production workflow

### Phase 1 — Build the video with placeholders

Create the Remotion project and build the 9 scenes using placeholder assets:

- placeholder Console screenshot
- placeholder resource-lane video
- placeholder result figure
- placeholder convergence chart
- placeholder report screenshot

This lets the timing, captions, and story lock before the UI is final.

### Phase 2 — Record Sam's voice

Record the full voiceover as one audio file.

Recommended file:

- `voiceover.wav`

Put it in:

- `demos/video/public/audio/voiceover.wav`

Then align each scene to the audio.

### Phase 3 — Capture the final UI late

After the last UI changes are done, record only the screen assets that need replacing.

Recommended assets:

- `pod4_autolab_console.mp4`
- `pod5_race_start.mp4`
- `pod6_claude_reasoning.mp4`
- `pod7_optuna_vs_claude_chart.png`
- `pod8_ledger_hash_chain.mp4`
- `pod9_final_report_or_wordmark.mp4`

Put them in:

- `demos/video/public/assets/`

If the file names stay the same, Remotion will automatically use the updated clips.

### Phase 4 — Render and review

Render the full video. Watch it all the way through. Then check:

- Can a non-technical viewer explain what autolab does?
- Does a scientist believe the loop?
- Does a judge see the working demo?
- Does the final line feel bigger than a feature list?
- Are there any words on screen that compete with your voice?

---

# Practical Remotion Setup

## Suggested folder structure

Use this structure inside the repository or in a sibling `autolab-video` folder:

```text
demos/video/
  package.json
  remotion.config.ts
  src/
    Root.tsx
    scenes/
      Pod1ImaginationGap.tsx
      Pod2MessyScience.tsx
      Pod3ProvenanceProblem.tsx
      Pod4MeetAutolab.tsx
      Pod5RaceStarts.tsx
      Pod6ClaudeReasoning.tsx
      Pod7OptunaVsClaude.tsx
      Pod8LedgerEvidence.tsx
      Pod9DatasetMoat.tsx
    components/
      Caption.tsx
      Callout.tsx
      SceneShell.tsx
      VideoFrame.tsx
  public/
    assets/
    audio/
```

If you are using a separate `autolab-video` repo, keep the same internal structure there.

---

## Basic Remotion concept

Remotion is just React for video.

Instead of pages, you make scenes.
Instead of CSS animations in a browser, you animate by frame number.
Instead of exporting a website, you render an MP4.

The useful mental model:

> One scene = one spoken idea.

At 30 frames per second:

- 20 seconds = 600 frames
- 30 seconds = 900 frames
- 3 minutes = 5,400 frames

So the whole video can still be a sequence of 9 scenes, but the exact scene lengths should follow the recorded voiceover rather than a fixed grid.

---

# How to handle last-minute UI changes

This is important: do not bake the UI into custom animations too early.

Use Remotion for:

- intro title cards
- captions
- arrows
- zooms
- callouts
- chart overlays
- final title

Use screen recordings for:

- the actual Console
- the Gantt/resource lanes
- the race start
- the reasoning rail
- the ledger panel

Use the generated chart for:

- `var/demo_lab/_compare_optuna_vs_claude.png`

That means late UI changes only require replacing the screen recordings.

The safest rule:

> If it might change tomorrow, make it a replaceable video asset.

---

# Asset Capture Checklist

Capture these after the UI is final enough:

## Clip 1 — Autolab Console

Length: 10-15 seconds

Must show:

- the Console
- Brain / Hands / Ledger regions
- simple amber callouts

Use in:

- 1:00-1:20

## Clip 2 — Race start

Length: 15-20 seconds

Must show:

- Claude and Optuna campaigns start
- resources fill
- plan tree grows
- ledger records appear

Use in:

- 1:20-1:40

## Clip 3 — Claude reasoning

Length: 15-20 seconds

Must show:

- trial 1: Fe16N2, sx=60 nm, sy=10 nm, 400 mT
- trial 2: Fe16N2, sx=68 nm, sy=6 nm, 500 mT
- trial 1 reasoning: "highest-Ms material", "strong aspect ratio", "shape anisotropy"
- trial 2 reasoning: "exploit Fe16N2", "extreme elongation", "push Hmax higher"
- optional backup inserts from later trials: "local optimum near boundary", "probe Hmax landscape"

Use in:

- 1:40-2:00

## Clip 4 — Optuna vs Claude chart

Length: still image or generated Remotion chart

Must show:

- `var/demo_lab/_compare_optuna_vs_claude.png`
- Claude reaches 500 mT at trial 2
- Optuna reaches 500 mT at trial 12
- material scatter panel if legible
- contrast label: Claude reasons from physics; Optuna samples statistics

Use in:

- 2:00-2:20

## Clip 5 — Ledger hash chain

Length: 15-20 seconds

Must show:

- 49 records
- visible SHA-256 checksums
- append-only ledger rows
- claim records / reasoning records

Use in:

- 2:20-2:40

## Clip 6 — Final report / wordmark

Length: 10-15 seconds

Must show:

- successful and failed trials becoming a dataset
- evidence chain
- final autolab wordmark

Use in:

- 2:40-3:00

---

# Editing Rules

## Keep captions short

Good:

> Brain. Hands. Ledger.

Bad:

> A Claude PolicyProvider delegates to a Campaign Planner and persists SHA-256 records.

## Use technical terms visually, not verbally

It is fine if the UI shows terms like `react()` or hash values. But the voiceover should translate them.

Say:

> The lab changes course.

Do not say:

> The Planner's `react()` method emits an `add_step` Action.

## Do not end on replay

Replay is a valuable engineering feature, but not the emotional close for this audience.

If needed, show it as a small credibility caption earlier:

> Replayable from the record.

But close on:

> Every campaign makes the next one smarter.

## One idea per pod

Each 20-second pod should have exactly one main idea:

1. Imagination is no longer the bottleneck.
2. Science is still messy and lossy.
3. Measurements need provenance.
4. Autolab = Brain, Hands, Ledger.
5. The real race starts.
6. Claude reasons from physics.
7. Claude finds the optimum 6x faster.
8. Every step becomes evidence.
9. The dataset compounds.

---

# If Time Is Short

If there is not enough time to build the full Remotion version, make the simplest version:

1. Record Sam's voiceover.
2. Capture 5–7 clean screen clips.
3. Use Remotion only to place clips, captions, and title cards.
4. Do not over-animate.
5. Spend remaining time making the first 20 seconds and final 20 seconds feel polished.

Priority order:

1. clear story
2. clean audio
3. visible working demo
4. simple captions
5. animations

Bad audio will hurt more than simple visuals.

---

# Final Checklist Before Submission

- [ ] Voiceover sounds calm and confident.
- [ ] First 10 seconds clearly state why this matters.
- [ ] The viewer understands Brain / Hands / Ledger.
- [ ] The UI appears by 1:10.
- [ ] The lab visibly coordinates work.
- [ ] The Claude trial-1 to trial-2 reasoning is understandable.
- [ ] The Optuna vs Claude chart is legible.
- [ ] The 6x speedup lands clearly.
- [ ] The ledger is visibly append-only and hashed.
- [ ] The dataset/moat idea is clear.
- [ ] Final result/report is visible.
- [ ] Closing line is not technical.
- [ ] Final frame includes project name and repo.

---

# Final Line

> autolab is the autonomous lab for the next materials era.
