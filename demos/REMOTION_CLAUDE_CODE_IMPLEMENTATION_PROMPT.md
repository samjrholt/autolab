# Autolab — The Autonomous Lab for the Next Materials Era
## Implementation Spec for Claude Code

---

## 0. Read this first

You are implementing a ~3:00 animated demo trailer video in **Remotion** (React-based video framework). The intended working project is `C:\Users\holtsamu\repos\autolab-video` on Windows, with TypeScript. If the project is not scaffolded yet, scaffold it as a Remotion TypeScript project first. If Remotion Studio is already running, it should live-reload as you save files.

**The quality bar is non-negotiable.** The brief from Sam is: *"I want people asking 'how did they do that — did they hire a pro graphics artist?'"* Fade-in text is not enough. Every scene must have genuine motion design craft — particle systems, SVG animation, kinetic typography, scene transitions, elegant UI zooms, dynamic callouts, and chart animation.

The aesthetic should preserve the reference trailer style: **warm + high-tech** — not cold sci-fi, not plain corporate, and not a dark terminal demo. Think: the hope and warmth of a Pixar opening combined with the precision of an Apple product launch, adapted for autonomous science. Keep the paper / ink / amber design language below unless Sam explicitly asks to change it.

There is an installed Remotion skill available from Claude Code. **Consult the Remotion skill before implementing.** Follow Remotion idioms: use `spring()`, `interpolate()`, `useCurrentFrame()`, `useVideoConfig()`, `<Series>`, `<Sequence>`, `<Audio>`, `<Img>`, and `<Video>`. Never use `setTimeout` or `setInterval`. All animation must be deterministic from frame number.

**Working approach:**
1. Read the existing `src/` directory to understand current state.
2. Restructure the project per the architecture in Section 5.
3. Build foundation components first (Section 6), then scenes in order (Section 7).
4. Use placeholders for screen recordings first; assets can be replaced later without changing scene code.
5. After each scene, pause and tell Sam to check the Studio preview at the relevant timestamp.
6. Keep Remotion Studio responsive. If a scene becomes too heavy, optimize before moving on.

**Important production constraint:** Sam may make one or two last-minute UI changes. Therefore, do not bake the UI into complex custom animations. Use Remotion for titles, motion design, callouts, zooms, captions, charts, transitions, and polish. Use replaceable screen-recording assets for the actual autolab Console moments.

---

## 1. Context

**Who:** This trailer is for a hackathon submission and a wider audience of non-technical judges, scientists, investors, and future users.

**What:** autolab is an autonomous lab with provenance as its foundation. It helps scientists design and run campaigns, coordinate work across resources, interpret results, adapt mid-campaign, and preserve the full record of what happened.

**Primary message:**

> The next materials era is not blocked by imagination. It is blocked by trustworthy lab data. autolab is the autonomous lab that generates it.

**Demo example:** magnetic sensor-shape optimisation. autolab is general, but this video uses sensor-shape optimisation as the concrete proof.

**Tone:** Inspiring, clear, intelligent, grounded. The video must be understandable to a non-technical viewer but still credible to a scientist. Avoid jargon in narration. It is fine if the UI visually shows technical terms, hashes, records, and charts.

**Product framing:**

- **Brain** — decides what to try next.
- **Hands** — run simulations, instruments, tools, or remote resources.
- **Ledger** — keeps a trustworthy receipt of everything that happened.

**What not to do:**

- Do not make this feel like a generic AI agent demo.
- Do not over-index on terminal commands.
- Do not end on `autolab replay`.
- Do not explain implementation internals verbally.
- Do not imply physical instruments are running live in the hackathon demo; the demo path is computational, while the product shape supports experimental and computational science.

---

## 2. Final script — source of truth for voiceover and on-screen text

The video is 3 minutes, structured as 9 pods of ~20 seconds.

Use Sam's own recorded voiceover if present at `public/audio/voiceover.wav`. If the audio file is not present yet, implement timing with captions and placeholder audio support. The edit must allow the audio file to be added later without restructuring.

```
ACT 1 — THE NEXT MATERIALS ERA NEEDS A NEW KIND OF LAB

Scene 1 (0:00 – 0:20) — Hook: materials eras
"Every era is defined by its materials. Bronze. Iron. Steel. Silicon."
"Today, AI can imagine millions of new materials and designs."
"But imagination is not the bottleneck anymore."
"The bottleneck is trustworthy data from the lab."

On-screen caption:
"The bottleneck is trustworthy lab data."

Scene 2 (0:20 – 0:40) — What autolab is
"autolab is a new kind of lab assistant."
"It has a Brain to decide what to try next."
"Hands to run simulations, instruments, or tools."
"And a Ledger that keeps a receipt for everything that happened."

On-screen caption:
"Brain. Hands. Ledger."

Scene 3 (0:40 – 1:00) — The lab wakes up
"When I start a campaign, autolab does not just run a checklist."
"It breaks the goal into work, assigns that work to the available machines, and records each step as it happens."

On-screen caption:
"Not a checklist. A lab coordinating work."

ACT 2 — THE SCIENTIST LOOP

Scene 4 (1:00 – 1:20) — A result appears
"Let's say we're designing a new magnetic sensor."
"A standard AI just chases a high score, completely blind."
"But a scientist looks at the shape of the result and asks: what does this mean?"

On-screen caption:
"A score is not the whole experiment."

Scene 5 (1:20 – 1:40) — Claude reads the evidence
"autolab gives Claude the actual figure, not just the number."
"Claude writes down a hypothesis, how confident it is, and what experiment would check it."

On-screen caption:
"Hypothesis + confidence + next test"

Scene 6 (1:40 – 2:00) — The plan changes
"Then the lab changes course."
"It adds the next test, reshuffles the plan, and keeps the original reasoning."
"The hypothesis is not treated as truth. It is tested."

On-screen caption:
"The lab adapts mid-campaign."

ACT 3 — THE DATA MOAT COMPOUNDS

Scene 7 (2:00 – 2:20) — Claude versus a standard optimiser
"Here is the same problem with a standard optimiser."
"It sees only a number, so it wanders."
"Claude sees the evidence, reasons from the pattern, and gets to a better design faster."

On-screen caption:
"Seeing the evidence changes the search."

Scene 8 (2:20 – 2:40) — Scientists stay in the driver's seat
"But scientists are still in the driver's seat."
"If I step in and change the constraints, the lab adapts instantly — and permanently logs my decision."
"At the end, it produces the design, the recipe, and the record of how it got there."

On-screen caption:
"Human judgment becomes part of the record."

Scene 9 (2:40 – 3:00) — The real prize
"This is the real prize: not one lucky result, but a growing record of what worked, what failed, and why."
"Every campaign makes the next one smarter."
"autolab is the autonomous lab for the next materials era."

On-screen caption:
"Every campaign makes the next one smarter."

Final title:
autolab
The autonomous lab for the next materials era.
```

**Text rules:**

- Preserve the script wording unless Sam explicitly asks for edits.
- Keep on-screen captions short.
- Use technical words visually, not verbally.
- `autolab` is lowercase.
- Use British spelling where relevant: optimiser, optimisation.
- The em dash in “instantly — and permanently” is intentional.

---

## 3. Design language

### 3.1 Color palette

Create `src/theme.ts`:

```typescript
export const COLORS = {
  // Paper tones — the canvas
  paper: '#FAF8F4',        // base background
  paperWarm: '#F5EFE4',    // warmer sections
  paperDeep: '#EADFC8',    // deepest warm tone (rare accent)

  // Ink — text
  ink: '#1A1814',          // primary text
  ink2: '#4A4740',         // secondary text
  ink3: '#8A877F',         // tertiary / captions

  // Amber — warmth, possibility, the "glow"
  amber: '#B8894D',        // accent text, primary glow
  amberLight: '#D4A76A',   // highlights
  amberDeep: '#8B6535',    // shadows on amber elements
  amberGlow: 'rgba(184, 137, 77, 0.35)',

  // Terracotta — autolab / Anthropic-style accent, reveal moments only
  terracotta: '#C96342',
  terracottaLight: '#D77B5E',
  terracottaGlow: 'rgba(201, 99, 66, 0.3)',

  // Supporting scientific signal colors — use sparingly
  cyan: '#3B8EA5',
  green: '#4F9D69',
  red: '#B85C5C',

  border: '#DDD9D0',
};

export const FONTS = {
  serif: "'Lora', Georgia, serif",       // for main text (inspiring, human)
  sans: "'DM Sans', -apple-system, sans-serif",  // for labels, dates, meta
  mono: "'JetBrains Mono', monospace",   // for coded / tech moments
};
```

Install/load fonts via `@remotion/google-fonts`:

```typescript
import { loadFont as loadLora } from '@remotion/google-fonts/Lora';
import { loadFont as loadDMSans } from '@remotion/google-fonts/DMSans';
import { loadFont as loadJetBrainsMono } from '@remotion/google-fonts/JetBrainsMono';
```

### 3.2 Typography

Use the same feel as the reference trailer:

- `Lora` for big human/inspiring text.
- `DM Sans` for labels, captions, dates, and UI-adjacent text.
- `JetBrains Mono` only for small technical details, record hashes, or code-like labels.

### 3.3 Motion principles

**Rule 1 — Everything breathes.** No linear interpolations for anything visible. Use `spring()` for entry/exit with damping 18–22. Use easing curves for timed transitions. Never hard cut between opacities — always minimum 10-frame fades.

**Rule 2 — Stagger.** When multiple elements appear, stagger their entries by 3–6 frames each. Creates a sense of sequence and craft.

**Rule 3 — Micro-motion.** Static elements are the enemy. Even held elements should have a subtle continuous animation — a gentle scale breathing (±0.5%), a very slow drift, or a pulse. Use `Math.sin(frame / N) * amplitude`.

**Rule 4 — Depth via parallax.** Backgrounds move slower than midground which moves slower than foreground. Even a subtle 2–4px drift at different rates reads as depth.

**Rule 5 — Light has direction.** Glows, shadows, and light sweeps always imply a consistent light source (slightly upper-right). Don't have glow on all sides equally — fake directional lighting.

### 3.4 The neural network background (persistent)

**This is the visual signature of the entire video.** A subtle, living graph of nodes and connections runs behind every scene. It is the AI / lab-record motif that unifies the trailer without being literal.

Specifications:

- **40–55 nodes** positioned semi-randomly but hand-tuned to feel composed (not uniform grid, not chaotic)
- Node size: 3–6px, varies per node
- Node color: `COLORS.amber` at base 0.25 opacity, varies
- **Connections**: draw lines between nodes within a threshold distance (~280px). ~80–120 connections total
- Connection stroke: 1px, `COLORS.amber` at 0.08–0.15 opacity
- **Animation**:
  - Nodes pulse (scale 1.0 → 1.4 → 1.0) on independent cycles, each node has a random phase offset, period 2–5 seconds
  - Connections "fire" — occasionally (every 40–80 frames) a random connection gets a brightness pulse (opacity 0.1 → 0.4 → 0.1 over ~30 frames)
  - The whole layer has a very subtle horizontal drift (±8px over 10 seconds) for depth
- **Density control**: expose a `density` and `brightness` prop that scenes can increase during emotional peaks. Default brightness 1.0; Scene 5 goes to 1.4; Scene 7 goes to 2.0; Scene 9 goes to 1.7 at the final title reveal.

Implementation: One SVG layer, generated once (seeded random so it's stable across re-renders), positions memoized. All animation is frame-driven.

**IMPORTANT:** The network must not compete with text or screen recordings. Test that text remains crisply readable. If in doubt, dial down opacity.

---

## 4. Runtime and framerate

- **Total duration:** 5,400 frames = 3:00 at 30fps
- **Resolution:** 1920×1080
- **FPS:** 30

Scene durations:

| Scene | Start | End | Seconds | Frames |
|-------|-------|-----|---------|--------|
| 1 | 0:00 | 0:20 | 20 | 600 |
| 2 | 0:20 | 0:40 | 20 | 600 |
| 3 | 0:40 | 1:00 | 20 | 600 |
| 4 | 1:00 | 1:20 | 20 | 600 |
| 5 | 1:20 | 1:40 | 20 | 600 |
| 6 | 1:40 | 2:00 | 20 | 600 |
| 7 | 2:00 | 2:20 | 20 | 600 |
| 8 | 2:20 | 2:40 | 20 | 600 |
| 9 | 2:40 | 3:00 | 20 | 600 |

---

## 5. File architecture

Restructure or create `src/` as follows:

```text
src/
├── index.ts
├── index.css
├── Root.tsx
├── AutolabTrailer.tsx
├── theme.ts
├── components/
│   ├── NeuralNetwork.tsx
│   ├── ParticleField.tsx
│   ├── KineticText.tsx
│   ├── LightSweep.tsx
│   ├── BreathingContainer.tsx
│   ├── GlassFrame.tsx
│   ├── Caption.tsx
│   ├── Callout.tsx
│   ├── SceneShell.tsx
│   ├── VideoAsset.tsx
│   └── ConvergenceChart.tsx
├── scenes/
│   ├── Scene01_MaterialsEras.tsx
│   ├── Scene02_BrainHandsLedger.tsx
│   ├── Scene03_LabWakesUp.tsx
│   ├── Scene04_ResultAppears.tsx
│   ├── Scene05_ClaudeReadsEvidence.tsx
│   ├── Scene06_PlanChanges.tsx
│   ├── Scene07_ClaudeVsOptimiser.tsx
│   ├── Scene08_HumanInLoop.tsx
│   └── Scene09_DataMoatClose.tsx
├── icons/
│   ├── BrainIcon.tsx
│   ├── HandsIcon.tsx
│   ├── LedgerIcon.tsx
│   ├── SensorIcon.tsx
│   ├── LabMachineIcon.tsx
│   └── RecordHashIcon.tsx
└── utils/
    ├── random.ts
    └── easing.ts
```

Use this `AutolabTrailer.tsx` structure:

```tsx
import { AbsoluteFill, Audio, Series, staticFile } from 'remotion';
import { COLORS } from './theme';
import { NeuralNetwork } from './components/NeuralNetwork';
import { Scene01_MaterialsEras } from './scenes/Scene01_MaterialsEras';
import { Scene02_BrainHandsLedger } from './scenes/Scene02_BrainHandsLedger';
import { Scene03_LabWakesUp } from './scenes/Scene03_LabWakesUp';
import { Scene04_ResultAppears } from './scenes/Scene04_ResultAppears';
import { Scene05_ClaudeReadsEvidence } from './scenes/Scene05_ClaudeReadsEvidence';
import { Scene06_PlanChanges } from './scenes/Scene06_PlanChanges';
import { Scene07_ClaudeVsOptimiser } from './scenes/Scene07_ClaudeVsOptimiser';
import { Scene08_HumanInLoop } from './scenes/Scene08_HumanInLoop';
import { Scene09_DataMoatClose } from './scenes/Scene09_DataMoatClose';

export const AutolabTrailer = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.paper }}>
      <NeuralNetwork />
      <Audio src={staticFile('audio/voiceover.wav')} />
      <Series>
        <Series.Sequence durationInFrames={600}><Scene01_MaterialsEras /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene02_BrainHandsLedger /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene03_LabWakesUp /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene04_ResultAppears /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene05_ClaudeReadsEvidence /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene06_PlanChanges /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene07_ClaudeVsOptimiser /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene08_HumanInLoop /></Series.Sequence>
        <Series.Sequence durationInFrames={600}><Scene09_DataMoatClose /></Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
```

If `voiceover.wav` is not present yet, do not crash the whole render. Either comment `<Audio>` temporarily or implement a safe optional audio component.

---

## 6. Foundation components — build first

### 6.1 `NeuralNetwork.tsx`

Use the persistent neural-network background from Section 3.4. It is the visual signature of the video and should stay close to the reference prompt's implementation style.

For autolab, the meaning is slightly different: the network represents AI reasoning, lab records, evidence, and provenance links. But visually it should still feel like a subtle warm amber neural graph on paper — not a cold cyberpunk grid.

Generate nodes once using seeded random. Draw as SVG. Animate via frame-derived values.

### 6.2 `ParticleField.tsx`

Reusable particle system. Props:

- `count: number`
- `mode: 'drift' | 'converge' | 'explode' | 'orbit' | 'line'`
- `originFrame: number`
- `duration: number`
- `target?: { x: number; y: number }`
- `color?: string`
- `size?: { min: number; max: number }`
- `seed?: number`

Use deterministic start/end positions from seeded random. Animate with transforms only. Use particles for materials dust, data points, title reveals, and final data moat accumulation.

### 6.3 `KineticText.tsx`

Text animation component. Props:

- `text: string`
- `mode: 'type' | 'assemble' | 'fade' | 'wordCascade'`
- `inAt: number`
- `outAt?: number`
- `highlight?: string[]`
- `style?: CSSProperties`

Modes:

- **type:** characters appear one by one, with a small glow at the cursor.
- **assemble:** letters start scattered and spring into place.
- **wordCascade:** words enter one at a time with slight vertical lift and blur resolving to sharp text.
- **fade:** simple fallback.

### 6.4 `GlassFrame.tsx`

Wrap screen recordings or screenshots in a polished glass UI frame.

Features:

- rounded corners
- subtle border
- inner shadow
- top-left window dots
- optional label
- optional slow camera drift
- optional zoom target
- optional scanline / reflection gradient

This is how all autolab Console clips should appear.

### 6.5 `LightSweep.tsx`

A diagonal gradient sweep used for reveal moments and chart highlights.

Props:

- `inAt`
- `duration`
- `color`
- `angle`
- `width`

### 6.6 `Caption.tsx`

Bottom caption component with short on-screen text. It should be elegant, readable, and not subtitle-like unless needed.

Style:

- 34–44px, DM Sans
- text color `COLORS.ink`
- highlighted keywords in amber/cyan
- subtle paper-warm backing or translucent pill only when over UI

### 6.7 `ConvergenceChart.tsx`

Animated chart for Scene 7.

Requirements:

- Two labelled lines:
  - Claude-guided campaign
  - Standard optimiser
- Claude line should visibly improve faster.
- Standard optimiser should wander.
- Animate points appearing sequentially.
- Add glow trail to Claude line.
- Add target band or target line if useful.
- Avoid tiny axis labels; non-technical viewers need the gist.

Can use SVG directly rather than a charting library for full control.

### 6.8 `utils/random.ts`

Implement seeded random helpers:

```typescript
export const createRNG = (seed: number) => () => number;
export const seededRange = (rng: () => number, min: number, max: number) => number;
```

Use Mulberry32 or similar.

### 6.9 `utils/easing.ts`

Export:

- `easeOutExpo`
- `easeInOutCubic`
- `easeOutBack`
- `easeOutQuart`

Use with `interpolate()`.

---

## 7. Scene-by-scene specs

For each scene: the text is the source of truth. Visual details are recipes. Feel free to strengthen them, but do not weaken the craft.

---

### SCENE 1 — Materials eras (0:00–0:20, 600 frames)

**Text:**

- Bronze
- Iron
- Steel
- Silicon
- What comes next?
- The bottleneck is trustworthy lab data.

**Visual arc:**

Frames 0–80:
- Start on the warm paper canvas, very quiet and nearly empty.
- A single warm particle appears center screen like a spark.
- The particle splits into a small cloud of material dust.
- The neural network background is barely visible.

Frames 80–300:
- The words `Bronze`, `Iron`, `Steel`, `Silicon` appear one at a time.
- Each word has a distinct material treatment:
  - Bronze: warm metallic amber.
  - Iron: darker graphite/steel texture.
  - Steel: cool brushed highlight.
  - Silicon: faint cyan wafer-grid glint.
- Each word forms from particles, holds briefly, then slides/dissolves into the next.

Frames 300–430:
- `What comes next?` assembles from scattered letters.
- Background network brightens slightly.

Frames 430–600:
- The line `The bottleneck is trustworthy lab data.` appears with a strong but elegant reveal.
- `trustworthy lab data` glows amber.
- End with a subtle camera push forward into the UI world.

**Quality bar:** This opening must feel cinematic. No plain title card.

---

### SCENE 2 — Brain, Hands, Ledger (0:20–0:40, 600 frames)

**Text/caption:**

- Brain.
- Hands.
- Ledger.

**Visual arc:**

This scene explains autolab in the simplest possible language.

Frames 0–120:
- A glass-framed autolab Console appears, either as a placeholder screenshot or `public/assets/console_overview.png`.
- If the asset is missing, use a beautiful mock UI placeholder that clearly has a goal bar, resource lanes, and ledger panel.

Frames 120–420:
- Three callout cards enter in sequence:
  1. Brain — icon: neural/decision node. Callout points to planning/goal area.
  2. Hands — icon: robotic hand/resource lanes. Callout points to running work/resources.
  3. Ledger — icon: record chain/hash. Callout points to ledger/records panel.
- Each callout has a tiny animated SVG icon, not a static emoji.
- Each callout should feel like an Apple keynote annotation.

Frames 420–600:
- The three words align into a simple triad: `Brain  →  Hands  →  Ledger`.
- A warm light sweep passes through them.
- The Console remains visible behind.

**Do not:** Use dense architecture diagrams. This is for non-technical viewers.

---

### SCENE 3 — The lab wakes up (0:40–1:00, 600 frames)

**Asset:** `public/assets/beat1_lab_wakes_up.mp4`

**Fallback if asset missing:** use placeholder UI animation with resource lanes filling and ledger rows appearing.

**Visual arc:**

Frames 0–80:
- GlassFrame enters from slight perspective angle.
- Caption: `Not a checklist. A lab coordinating work.`

Frames 80–440:
- Play screen recording of campaign start.
- Add three polished callouts:
  - `Goal becomes work`
  - `Resources fill automatically`
  - `Records land as it runs`
- Use small animated arrows and pulses, not giant blocks.

Frames 440–600:
- Zoom into ledger rows landing and then back out to show full Gantt/plan context.
- A few tiny hash particles fly from completed work pills into the Ledger panel.

**Quality bar:** The viewer must understand that the system is actively coordinating work, not replaying a static dashboard.

---

### SCENE 4 — A result appears (1:00–1:20, 600 frames)

**Asset:** `public/assets/beat2_result_appears.mp4` or `public/assets/sensor_result.png`

**Visual arc:**

Frames 0–120:
- Transition from UI lanes into the sensor result.
- Show score/objective number large for a moment.
- The score appears attractive but incomplete.

Frames 120–360:
- The figure/shape/curve appears beside the score.
- The score becomes one small part of a richer evidence card.
- Caption: `A score is not the whole experiment.`

Frames 360–600:
- The chart/shape gets a subtle scan or magnifying lens pass.
- The word `blind` from the voiceover is visualized: a standard optimiser line/agent sees only the score, while the figure is greyed out to it.

**Design idea:** split the screen for a few seconds:

Left: `Standard optimiser` sees only `Score: 0.71`.
Right: `Scientist` sees score + shape + curve + context.

---

### SCENE 5 — Claude reads the evidence (1:20–1:40, 600 frames) ⭐ SHOWPIECE

**Asset:** `public/assets/beat2_claude_reads_evidence.mp4` or figure screenshot plus generated claim card.

**Visual arc:**

This is the first magic moment. Make it feel like the system is actually looking at scientific evidence.

Frames 0–120:
- Zoom into the result figure.
- A thin amber scanning line passes across the image.
- Tiny data particles lift off the figure.

Frames 120–300:
- Data particles travel from the figure into a Claude/evidence card.
- Do not show a giant Claude logo. Use subtle text: `Claude reads the figure`.
- The provenance constellation brightens and forms a link between figure and claim.

Frames 300–520:
- A Claim card assembles:
  - `Hypothesis`
  - `Confidence`
  - `Next test`
- Use placeholder content if the real UI asset is not ready:
  - Hypothesis: `Shape pattern suggests a better candidate region`
  - Confidence: `72%`
  - Next test: `Validate nearby design`
- Make clear this is a hypothesis, not truth.

Frames 520–600:
- The Claim card stamps into the Ledger with a satisfying but restrained motion.
- Caption: `Hypothesis + confidence + next test`

**Quality bar:** This scene must be one of the two most polished moments in the video.

---

### SCENE 6 — The plan changes (1:40–2:00, 600 frames)

**Asset:** `public/assets/beat2_plan_changes.mp4`

**Fallback:** generated plan tree animation.

**Visual arc:**

Frames 0–120:
- Start with previous plan tree.
- Highlight the claim/evidence node.

Frames 120–360:
- A new step branches into the plan.
- Existing steps slide and reshuffle smoothly.
- Resource lanes adapt.
- Show cause-and-effect: figure → hypothesis → new test.

Frames 360–520:
- The new test becomes active.
- A small label appears: `Test the hypothesis`.
- Avoid saying `react()` verbally, but if the UI has `react()` visible, subtly highlight it.

Frames 520–600:
- Ledger/evidence link forms between original result, hypothesis, and validation step.
- Caption: `The lab adapts mid-campaign.`

**Do not:** make this look like a random UI update. The viewer must see why the plan changed.

---

### SCENE 7 — Claude vs standard optimiser (2:00–2:20, 600 frames) ⭐ SHOWPIECE

**Visual arc:**

This is the proof scene. It should feel crisp, legible, and satisfying.

Use `ConvergenceChart.tsx` unless there is an excellent captured UI chart. A generated chart is safer and more controllable.

Frames 0–80:
- Warm paper/glass chart panel enters.
- Title: `Same problem. Two ways to search.`

Frames 80–360:
- Standard optimiser line appears first: orange/grey, wandering.
- Claude-guided line appears second: cyan/amber glow, improves faster.
- Animate points trial by trial.
- Add small labels that follow the line ends.

Frames 360–480:
- Claude line crosses target or reaches best region.
- Target band glows green.
- Small badge: `Better design faster`.

Frames 480–600:
- Split the chart visually into the idea:
  - Standard optimiser: `sees a number`
  - Claude-guided: `sees evidence`
- Caption: `Seeing the evidence changes the search.`

**Suggested placeholder values:**

```typescript
const standard = [0.12, 0.15, 0.13, 0.19, 0.18, 0.22, 0.21, 0.24, 0.23, 0.28, 0.31, 0.30, 0.34, 0.33, 0.36];
const claude = [0.14, 0.21, 0.27, 0.34, 0.39, 0.45, 0.51, 0.57, 0.60, 0.64, 0.68, 0.72, 0.75, 0.78, 0.80];
```

Tune values to real data later if available.

**Quality bar:** This should be instantly understandable without knowing what Bayesian optimisation is.

---

### SCENE 8 — Scientists stay in the driver's seat (2:20–2:40, 600 frames)

**Asset:** `public/assets/beat3_human_intervention.mp4`

**Fallback:** generated intervention box + plan update animation.

**Visual arc:**

Frames 0–150:
- Show human intervention input.
- A typed constraint appears, for example:
  - `Prefer simpler geometry`
  - `Restrict candidate region`
  - `Prioritise manufacturable designs`
- Keep text generic if the final demo wording changes.

Frames 150–330:
- The plan adapts instantly.
- New constraint appears as a permanent record in the Ledger.
- Use a tasteful stamp/chain-link motion, not a legal-document cliché.

Frames 330–520:
- Report/design begins to render.
- Show final design card with recipe/evidence summary.

Frames 520–600:
- Caption: `Human judgment becomes part of the record.`
- The Console fades into an evidence montage.

**Tone:** Reassuring. The message is: scientists are amplified, not replaced.

---

### SCENE 9 — The data moat compounds (2:40–3:00, 600 frames)

**Visual arc:**

This is the emotional close. Do not end on terminal replay.

Frames 0–120:
- Final report/design card appears center.
- Around it, records from the campaign begin to orbit or stack.

Frames 120–300:
- Records multiply into a provenance constellation.
- Each record is represented as a small card/dot:
  - result
  - hypothesis
  - validation
  - intervention
  - final design
  - failed attempt
- Include failures as useful data.

Frames 300–450:
- The constellation expands outward, implying future campaigns are building on this one.
- Caption: `Every campaign makes the next one smarter.`

Frames 450–600:
- Clean final title reveal:

```
autolab
The autonomous lab for the next materials era.
```

- Title forms from the same record particles.
- Add optional small footer:
  - `Apache-2.0 · github.com/samjrholt/autolab`
- End with quiet confidence, not a loud logo slam.

**Quality bar:** The final 20 seconds must feel like the value of the company/product, not just the end of the demo.

---

## 8. Replaceable asset plan

Create this folder structure:

```text
public/
  assets/
    console_overview.png
    beat1_lab_wakes_up.mp4
    beat2_result_appears.mp4
    beat2_claude_reads_evidence.mp4
    beat2_plan_changes.mp4
    beat3_human_intervention.mp4
    final_report_or_ledger.mp4
  audio/
    voiceover.wav
```

If an asset is missing, scenes must still render using placeholders. Do not block development waiting for final UI captures.

When Sam makes final UI changes, he should only need to replace files in `public/assets/` using the same filenames.

---

## 9. Quality checklist — before declaring done

Before saying the build is complete, verify:

- [ ] Total duration is exactly 5,400 frames at 30fps.
- [ ] Every scene has motion beyond fade-in.
- [ ] Text is readable at 100% zoom.
- [ ] The opening feels cinematic, not like a slide deck.
- [ ] Brain / Hands / Ledger is understandable in under 20 seconds.
- [ ] Screen-recorded UI is visible and not over-covered by effects.
- [ ] Scene 5 feels like Claude is reading scientific evidence.
- [ ] Scene 6 clearly shows cause and effect: result → hypothesis → changed plan.
- [ ] Scene 7 chart is legible to a non-technical viewer.
- [ ] Scene 8 makes human control feel reassuring.
- [ ] Scene 9 closes on the compounding data moat, not a terminal command.
- [ ] If `voiceover.wav` exists, it is synced and not drowned by any music/sound effects.
- [ ] Remotion Studio preview plays end-to-end without errors.

---

## 10. Known risks / things to watch

1. **Performance:** Particle systems and SVG constellations can slow preview. Generate positions once, use seeded random, and animate with transforms.
2. **Asset absence:** Final UI recordings may not exist yet. Build placeholders that look good but are easy to replace.
3. **Voiceover timing:** Sam's recorded voice may not match exact 20-second pods. Make scenes slightly flexible with local timing constants.
4. **Too much text:** The voiceover already carries the story. On-screen captions should be short.
5. **Over-jargon:** If a caption contains implementation language, replace it with plain English.
6. **Replay temptation:** Do not end with `autolab replay`. The close is the compounding trustworthy dataset.

---

## 11. Build order

1. Read existing Remotion project files.
2. Update or create `theme.ts`.
3. Create `utils/random.ts` and `utils/easing.ts`.
4. Create foundation components:
  - `NeuralNetwork`
   - `ParticleField`
   - `KineticText`
   - `GlassFrame`
   - `Caption`
   - `Callout`
   - `ConvergenceChart`
5. Register the `AutolabTrailer` composition in `Root.tsx`.
6. Build Scene 1 and pause for review.
7. Build Scene 2 and pause for review.
8. Build Scene 3 and pause for review.
9. Build Scene 4 and pause for review.
10. Build Scene 5 and pause for review. This is a showpiece.
11. Build Scene 6 and pause for review.
12. Build Scene 7 and pause for review. This is a showpiece.
13. Build Scene 8 and pause for review.
14. Build Scene 9 and pause for review.
15. Full preview pass and timing polish.
16. Render only after Sam approves the preview.

After building each scene, pause and tell Sam:

> Scene N is ready. Please scrub to timestamp X in Remotion Studio and check. I'll wait for feedback before proceeding.

---

## 12. Rendering to MP4

Final render:

```powershell
npx remotion render AutolabTrailer out/autolab-trailer.mp4
```

High-quality render:

```powershell
npx remotion render AutolabTrailer out/autolab-trailer-hq.mp4 --crf=18 --codec=h264
```

If the composition ID differs, inspect `Root.tsx` and use the registered composition ID.

---

## Summary of expectations

If this spec is executed faithfully, Sam should watch the preview and feel:

1. The opening is inspiring.
2. The product is understandable.
3. The demo feels real.
4. The chart proves the point.
5. The close feels bigger than a feature list.

The brief is:

> Make people feel that autolab is not another AI wrapper. It is the autonomous lab for the next materials era.
>
> I want people asking 'how did they do that — did they hire a pro graphics artist?'

Make that brief true.
