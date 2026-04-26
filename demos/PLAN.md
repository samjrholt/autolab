# Hackathon Submission: Demo Video & Story Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Current final script:** use `demos/FINAL_VIDEO_SCRIPT_AND_PRODUCTION_PLAN.md` as the recording script and production workflow. It supersedes the older replay-led close below for the final narrated video: the video should close on the compounding trustworthy-data moat, not on `autolab replay`.

**Goal:** Produce a compelling 3-minute Remotion video for the autolab hackathon submission that tells the story of an autonomous lab — Claude beats BO, react() mid-experiment adaptation, and full provenance — with a reproducible demo path backed by clean seed scripts.

**Architecture:** Three parallel workstreams — (1) `demos/` folder with seed scripts that always reproduce the demo state, (2) frontend polish on the 3 key UI moments that will be screen-captured, (3) Remotion video project that combines screen captures + animated overlays into the final submission video.

**Tech Stack:** Python (seed scripts), FastAPI/WebSocket (live Lab), React/Vite/Tailwind (UI), Remotion (`@remotion/cli`, React), existing autolab codebase.

**Deadline:** 2026-04-26 20:00 EST

---

## The Story (read before coding anything)

Use `demos/FINAL_VIDEO_SCRIPT_AND_PRODUCTION_PLAN.md` as the source of truth. The final submission video is a tight proof of the working MVP, not a broad manifesto.

**Hook (0:00–0:35):** AI can imagine millions of materials, but proof is still slow, scattered, and poorly recorded. End the hook on the thesis: *property without provenance is noise.*

**Beat 1 — Meet autolab + scheduler proof (0:35–1:25):** Show the actual Console. Brain, Hands, Ledger. Start the sensor optimisation comparison and keep the resource lanes, plan tree, and ledger rows visible while the lab schedules work across the VM resource.

**Beat 2 — `react()` from evidence (1:25–2:10):** Claude makes a physics-grounded first trial, the result is written to the ledger, and the planner reacts to that record by refining the next trial. The core line is: every result becomes a record, and the plan changes because of that record.

**Beat 3 — payoff + ledger proof (2:10–3:00):** Show the simple scoreboard: Claude reaches the optimum in two trials; Optuna reaches it at trial twelve. Then prove this was not a loose benchmark by zooming into the ledger: hashed records, claim records, prompt/response metadata, and parent-child links. Close on the compounding dataset, not on a replay command.

---

## Critical Files

| File | Role |
|------|------|
| `demos/` | New folder — all demo seed scripts live here |
| `demos/seed_demo.py` | Seeds Lab with 2 campaigns (Claude + BO) in terminal state |
| `demos/run_demo.py` | Runs the live 3-beat demo path step by step |
| `demos/video/` | Remotion project |
| `demos/video/src/Root.tsx` | Remotion composition root |
| `demos/video/src/scenes/` | One file per beat + hook/close |
| `frontend/src/` | Existing React UI — polish 3 moments |
| `frontend/src/shell/AppShell.jsx` | Already modified (git status) |
| `frontend/src/shell/Sidebar.jsx` | Already modified |
| `frontend/src/App.jsx` | Already modified |
| `frontend/src/styles.css` | Already modified |
| `examples/mammos_sensor/` | Primary demo workflow |
| `examples/sensor_shape_opt/` | Source of the Claude vs BO runs |

---

## Task 1: Demo Seed Scripts

Create reproducible scripts that always put the Lab in the exact state needed for each video beat.

**Files:**
- Create: `demos/__init__.py`
- Create: `demos/seed_demo.py`
- Create: `demos/README.md`

- [ ] **Step 1: Create the demos folder and seed script**

```python
# demos/seed_demo.py
"""
Populate the running Lab with two completed campaigns:
  - 'sensor-shape-opt (claude)' — converged in 15 trials, hit target
  - 'sensor-shape-opt (optuna)' — ran 15 trials, did not hit target

Run against a live Lab: python demos/seed_demo.py --lab-url http://localhost:8000
"""
import argparse, asyncio, json, httpx

CLAUDE_CAMPAIGN = {
    "id": "demo-claude-001",
    "name": "sensor-shape-opt (claude)",
    "goal": "Maximise GMR sensor FOM Hmax_A_per_m. Free-layer shape: superellipse n, Lx, Ly.",
    "planner": "claude",
    "status": "completed",
}

OPTUNA_CAMPAIGN = {
    "id": "demo-optuna-001",
    "name": "sensor-shape-opt (optuna)",
    "goal": "Maximise GMR sensor FOM Hmax_A_per_m. Free-layer shape: superellipse n, Lx, Ly.",
    "planner": "optuna",
    "status": "completed",
}

async def seed(lab_url: str):
    async with httpx.AsyncClient(base_url=lab_url, timeout=30) as client:
        for campaign in [CLAUDE_CAMPAIGN, OPTUNA_CAMPAIGN]:
            r = await client.post("/campaigns/seed", json=campaign)
            r.raise_for_status()
            print(f"Seeded campaign: {campaign['name']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(seed(args.lab_url))
```

- [ ] **Step 2: Create `demos/README.md`**

Content: step-by-step instructions for reproducing the demo. Sections: Prerequisites, Start Lab, Seed data, Screen capture moments (Beat 1, 2, 3), Run Remotion render.

- [ ] **Step 3: Add `/campaigns/seed` endpoint to `src/autolab/server/app.py`**

This endpoint accepts a campaign dict with pre-baked `status` and inserts it into the ledger without running it — for demo seeding only. Mark it with a `# DEMO ONLY` comment and guard with `if settings.demo_mode`.

- [ ] **Step 4: Commit**

```bash
git add demos/ src/autolab/server/app.py
git commit -m "feat: add demo seed scripts and /campaigns/seed endpoint"
```

---

## Task 2: Frontend Polish — Three Key Moments

The three moments that must look great on camera. No new features — sharpen what's there.

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/shell/AppShell.jsx`
- Modify: `frontend/src/shell/Sidebar.jsx`
- Modify: `frontend/src/styles.css`
- Modify: relevant page components under `frontend/src/`

### Moment A: Resource Gantt + Plan Tree (Beat 1)

- [ ] **Step 1: Verify the CampaignDetailPage Gantt renders correctly**

Run `npm run dev` in `frontend/`, navigate to a seeded campaign, and confirm:
- Resource lanes are visible with pill-shaped operation blocks
- Colours distinguish different experiments
- Real-time updates arrive via WebSocket

- [ ] **Step 2: Add a "Ledger" sidebar panel to CampaignDetailPage**

Small right-side panel (200px wide) showing the last 8 records as: `[hash[:8]] capability_name status`. New records animate in from the top (CSS slide-in). This makes provenance visually present during Beat 1.

- [ ] **Step 3: Simplify the sidebar navigation**

The sidebar should show exactly 4 items for the demo: **Campaigns**, **Ledger**, **Resources**, **Analysis**. Hide anything else behind a collapsed "More" section. Clear labels, no jargon.

### Moment B: react() Loop (Beat 2)

- [ ] **Step 4: Build a `ClaimCard` component**

```tsx
// frontend/src/components/ClaimCard.tsx
interface ClaimCardProps {
  capability: string;       // "hysteresis_interpret"
  diagnosis: string;        // "Soft-phase contamination"
  confidence: number;       // 0–1
  recommendedAction: string; // "Raise anneal temperature 150 °C"
  status: "claim" | "validated" | "refuted";
}
```

Renders as a card with a yellow "CLAIM" badge (or green VALIDATED / red REFUTED). Shows in the plan tree when an Interpretation Operation record arrives. This makes Beat 2 legible at a glance.

- [ ] **Step 5: Wire ClaimCard to the WebSocket event stream**

When a record with `record_type === "claim"` arrives on the WS stream, insert a ClaimCard into the plan tree below its parent operation.

### Moment C: Claude vs BO Convergence Chart (Beat 3)

- [ ] **Step 6: Add an Analysis tab to CampaignDetailPage (or AnalysisPage)**

Side-by-side line chart: X = trial number, Y = objective value. Two series: Claude campaign (blue), BO campaign (orange) — matching the screenshot colours. Use recharts (already in React stack or add it). Pull data from `GET /ledger?campaign=demo-claude-001` and `GET /ledger?campaign=demo-optuna-001`.

- [ ] **Step 7: Add "Best so far" and "Objective by trial" toggle** matching the screenshot tabs exactly (Objective / Best so far / Shape map / Runtime). This is already partially there — make it pixel-perfect.

- [ ] **Step 8: Commit frontend changes**

```bash
git add frontend/src/
git commit -m "feat: polish demo UI — ledger panel, ClaimCard, convergence chart"
```

---

## Task 3: Remotion Video Project

Set up a Remotion project under `demos/video/` that produces the final 3-minute submission video.

**Files:**
- Create: `demos/video/package.json`
- Create: `demos/video/remotion.config.ts`
- Create: `demos/video/src/Root.tsx`
- Create: `demos/video/src/scenes/Hook.tsx`
- Create: `demos/video/src/scenes/Beat1_Scheduler.tsx`
- Create: `demos/video/src/scenes/Beat2_React.tsx`
- Create: `demos/video/src/scenes/Beat3_BOvsClaude.tsx`
- Create: `demos/video/src/scenes/Close.tsx`
- Create: `demos/video/src/components/TitleCard.tsx`
- Create: `demos/video/src/components/Annotation.tsx`

- [ ] **Step 1: Bootstrap the Remotion project**

```bash
cd demos/video
npm init remotion@latest .
# Choose: blank template, TypeScript
```

- [ ] **Step 2: Set video spec in `remotion.config.ts`**

```ts
import { Config } from "@remotion/cli/config";
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
```

Root composition: `fps=30`, `durationInFrames=5400` (3 min × 60 sec × 30 fps), `width=1920`, `height=1080`.

- [ ] **Step 3: Create `Root.tsx` with scene sequencing**

```tsx
// demos/video/src/Root.tsx
import { Composition, Series } from "remotion";
import { Hook } from "./scenes/Hook";
import { Beat1Scheduler } from "./scenes/Beat1_Scheduler";
import { Beat2React } from "./scenes/Beat2_React";
import { Beat3BOvsClaude } from "./scenes/Beat3_BOvsClaude";
import { Close } from "./scenes/Close";

export const RemotionRoot = () => (
  <Composition
    id="AutolabDemo"
    component={() => (
      <Series>
        <Series.Sequence durationInFrames={600}>  {/* 0:00–0:20 */}
          <Hook />
        </Series.Sequence>
        <Series.Sequence durationInFrames={1200}> {/* 0:20–1:00 */}
          <Beat1Scheduler />
        </Series.Sequence>
        <Series.Sequence durationInFrames={1500}> {/* 1:00–1:50 */}
          <Beat2React />
        </Series.Sequence>
        <Series.Sequence durationInFrames={1500}> {/* 1:50–2:40 */}
          <Beat3BOvsClaude />
        </Series.Sequence>
        <Series.Sequence durationInFrames={600}>  {/* 2:40–3:00 */}
          <Close />
        </Series.Sequence>
      </Series>
    )}
    fps={30}
    durationInFrames={5400}
    width={1920}
    height={1080}
    defaultProps={{}}
  />
);
```

- [ ] **Step 4: Create `TitleCard` and `Annotation` shared components**

```tsx
// demos/video/src/components/TitleCard.tsx
import { useCurrentFrame, spring, useVideoConfig, AbsoluteFill } from "remotion";

export const TitleCard = ({ title, subtitle }: { title: string; subtitle?: string }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = spring({ frame, fps, from: 0, to: 1, durationInFrames: 20 });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", background: "#0a0a0a" }}>
      <div style={{ opacity, textAlign: "center", color: "white", fontFamily: "Inter, sans-serif" }}>
        <h1 style={{ fontSize: 72, fontWeight: 700, margin: 0 }}>{title}</h1>
        {subtitle && <p style={{ fontSize: 32, opacity: 0.6, marginTop: 16 }}>{subtitle}</p>}
      </div>
    </AbsoluteFill>
  );
};
```

```tsx
// demos/video/src/components/Annotation.tsx
// Animated callout box that appears over screen captures
export const Annotation = ({
  text, x, y, frame: showAt,
}: { text: string; x: number; y: number; frame: number }) => {
  const frame = useCurrentFrame();
  const opacity = frame >= showAt ? Math.min(1, (frame - showAt) / 10) : 0;
  return (
    <div style={{
      position: "absolute", left: x, top: y, opacity,
      background: "rgba(99,102,241,0.9)", color: "white",
      padding: "8px 16px", borderRadius: 8, fontSize: 24,
      fontFamily: "Inter, sans-serif", fontWeight: 600,
      boxShadow: "0 4px 24px rgba(0,0,0,0.4)"
    }}>
      {text}
    </div>
  );
};
```

- [ ] **Step 5: Create `Hook.tsx` scene**

Text-only scene on dark background. Fade in three lines with staggered spring animations:
1. "Science is bottlenecked not by AI prediction models..."
2. "...but by decision-grade experimental data."
3. "autolab is the autonomous lab that generates it."

Final 2 seconds: autolab logo / wordmark.

- [ ] **Step 6: Create `Beat1_Scheduler.tsx`**

Structure: 
- 0–2s: Title card "Beat 1: The Scheduler"
- 2–20s: Embed screen capture video asset `assets/beat1_scheduler.mp4` (recorded from live UI) using `<Video>` component
- Overlay `Annotation` components that highlight: the resource Gantt filling, a hash landing in the ledger sidebar, cross-experiment interleaving
- Voiceover text appears as subtitles at bottom

Include placeholder for `assets/beat1_scheduler.mp4` — this file gets added after screen capture.

- [ ] **Step 7: Create `Beat2_React.tsx`**

Structure:
- 0–2s: Title card "Beat 2: The react() Loop"
- 2–5s: Show the kinked hysteresis PNG (`assets/kinked_loop.png`) with annotation "Kinked — soft-phase contamination?"
- 5–15s: Show Claude's Claim response as animated text appearing character by character (or line by line)
- 15–30s: Screen capture of plan tree reshuffling (`assets/beat2_replan.mp4`)
- 30–50s: Second run completes — clean loop appears — Claim validated

- [ ] **Step 8: Create `Beat3_BOvsClaude.tsx`**

The hero scene. Uses animated recharts-style line chart rendered entirely in Remotion (no screen capture needed — pure SVG animation):

```tsx
// Animate trial-by-trial, adding one data point every 8 frames
// Claude series: values from actual run data
const CLAUDE_VALUES = [195000, 220000, 270000, 290000, 340000, 338000, 310000, 265000, 270000, 265000, 300000, 295000, 345000, 260000]; // from screenshot
const OPTUNA_VALUES = [-15000, -15000, -15000, -15000, -15000, -15000, 70000, -20000, -15000, 30000, 265000, 260000]; // from screenshot
```

Each new point springs in. Voiceover text: "Bayesian optimisation sees a number. Claude sees the loop — proposes the physics — then checks itself."

Final frames: green "TARGET HIT" badge appears. Transition to report PDF rendering.

- [ ] **Step 9: Create `Close.tsx`**

Dark background. Animated terminal text:
```
$ autolab replay demo-claude-001
✓ 47 records verified
✓ SHA-256 chain intact
✓ Reproduction complete
```

Then fade to: "autolab" wordmark + "Apache 2.0" + GitHub URL.

- [ ] **Step 10: Commit Remotion project**

```bash
git add demos/video/
git commit -m "feat: add Remotion video project for hackathon submission"
```

---

## Task 4: Demo Run Script (Reproducible Live Path)

For judges who want to run it themselves and for the screen capture sessions.

**Files:**
- Create: `demos/run_demo.py`
- Create: `demos/demo_config.yaml`

- [ ] **Step 1: Create `demos/demo_config.yaml`**

```yaml
lab_url: http://localhost:8000
campaigns:
  claude:
    name: "sensor-shape-opt (claude)"
    planner: claude
    goal: "Maximise GMR sensor FOM Hmax_A_per_m"
    workflow: sensor_shape_opt
    max_trials: 15
  optuna:
    name: "sensor-shape-opt (optuna)"
    planner: optuna
    goal: "Maximise GMR sensor FOM Hmax_A_per_m"
    workflow: sensor_shape_opt
    max_trials: 15
screen_capture_pauses:
  - "after_campaign_start"      # Beat 1: Gantt filling
  - "after_first_kinked_result" # Beat 2: react() fires
  - "after_claude_convergence"  # Beat 3: chart appears
```

- [ ] **Step 2: Create `demos/run_demo.py`**

Script that:
1. Starts both campaigns simultaneously
2. Pauses and prints "CAPTURE MOMENT: Beat 1 — Gantt filling" at the right moment
3. Injects a pre-baked kinked hysteresis result to trigger the react() loop (so Beat 2 always fires)
4. Waits for the chart to show convergence
5. Prints instructions for each capture

- [ ] **Step 3: Commit**

```bash
git add demos/run_demo.py demos/demo_config.yaml
git commit -m "feat: add reproducible demo run script with capture pause points"
```

---

## Task 5: Screen Capture Sessions

After frontend polish is done and demo scripts work — record the 3 beat assets.

- [ ] **Step 1: Capture `assets/beat1_scheduler.mp4`**
  - Boot Lab, run `demos/run_demo.py`
  - Record from campaign start until Gantt has 3+ filled lanes and 8+ ledger hashes visible
  - Target: 18 seconds of recording

- [ ] **Step 2: Capture `assets/kinked_loop.png`**
  - Screenshot of the kinked hysteresis chart from the UI (or generate synthetically)

- [ ] **Step 3: Capture `assets/beat2_replan.mp4`**
  - Record plan tree reshuffling after react() fires
  - Target: 15 seconds

- [ ] **Step 4: Add assets to Remotion project**
  - Copy to `demos/video/public/assets/`
  - Update `Beat1_Scheduler.tsx` and `Beat2_React.tsx` with actual file paths

---

## Task 6: Final Render & Submission Prep

- [ ] **Step 1: Render the video**

```bash
cd demos/video
npx remotion render AutolabDemo out/autolab-demo.mp4 --codec=h264
```

Expected output: `out/autolab-demo.mp4`, ~180MB, 3 minutes.

- [ ] **Step 2: Review the render**

Watch the full video. Check: transitions are smooth, annotation timing is correct, voiceover text matches visual beats, convergence chart animation is compelling.

- [ ] **Step 3: Update README.md with submission content**

Add to project README:
- 1-paragraph abstract matching the white-paper framing
- The convergence chart image embedded inline
- `autolab serve` + `autolab campaign start demos/demo_config.yaml` quick start
- Link to submission video

- [ ] **Step 4: Tag and push**

```bash
git tag v1.0.0
git push origin master --tags
```

---

## Verification

| Test | Command | Expected |
|------|---------|----------|
| Demo seeds correctly | `python demos/seed_demo.py` | Two campaigns in Lab, no errors |
| Live demo runs | `python demos/run_demo.py` | 3 pause points printed, react() fires |
| Frontend builds | `cd frontend && npm run build` | No errors, static files in `server/static/` |
| Remotion renders | `cd demos/video && npx remotion render` | `out/autolab-demo.mp4` produced |
| Convergence chart | Open Analysis page with seeded data | Two series visible, Claude above BO |

---

## Day-by-Day Schedule

**Day 3 (today, Apr 23):** Task 1 (seed scripts) + Task 2 (frontend polish)
**Day 4 (Apr 24):** Task 3 (Remotion project skeleton) + Task 4 (demo run script)
**Day 5 (Apr 25):** Task 5 (screen capture sessions) + wire assets into Remotion
**Day 6 (Apr 26, deadline 20:00 EST):** Task 6 (render + README + tag)
