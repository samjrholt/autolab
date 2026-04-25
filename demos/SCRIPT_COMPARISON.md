# Autolab Demo Video: Script Comparison

This document compares the original draft script from the hackathon plan against the new, polished script optimized for a mixed audience (non-technical, judges, and investors).

---

## 1. Original Draft Script (from `demos/PLAN.md`)

**Hook (0:00–0:20):** "Science is bottlenecked not by prediction models — but by decision-grade data. autolab is an autonomous lab that generates it."

**Beat 1 — Scheduler / Provenance (0:20–1:00):** Lab boots. A campaign goal is typed in plain English. The Principal Agent decomposes it into a plan tree; the resource Gantt fills with interleaved Operations. Every record hashed, every tool call logged. The ledger panel shows SHA-256 hashes landing in real time. 
*Voiceover:* "Every action, every failure, every reasoning step — immutable, hashed, replayable."

**Beat 2 — react() with vision (1:00–1:50):** A hysteresis loop completes — it's kinked. The PNG goes to `hysteresis_interpret`. Claude returns: "Soft-phase contamination, confidence 72%. Recommended: raise anneal temperature 150 °C." The plan tree reshuffles live. 
*Voiceover:* "Claude sees the loop — not just the number — and proposes the physics. Then checks itself."

**Beat 3 — Claude beats BO (1:50–2:40):** Split screen. Claude campaign converges in ~15 trials. Optuna/BO wanders. 
*Voiceover:* "Bayesian optimisation sees a scalar. Claude sees the image, infers the physics, adapts the recipe. This is what it means for an agent to be an experimentalist." Target hit.

**Close (2:40–3:00):** Replay command. One hash. Full audit trail.
*Voiceover:* "autolab. The autonomous lab with provenance as its foundation."

---

## 2. Final Polished Script (The "Next Materials Era" Approach)

Designed in three acts, tuned for non-technical comprehension, and paced in 20-second pods.

### Act 1 — The next materials era needs a new kind of lab
* **0:00–0:20 (Hook):** "Every era is defined by its materials. Bronze. Iron. Steel. Silicon. Today, AI can imagine millions of new materials and designs. But imagination is not the bottleneck anymore. The bottleneck is trustworthy data from the lab."
* **0:20–0:40 (Brain, Hands, Ledger):** "autolab is a new kind of lab assistant. It has a Brain to decide what to try next. Hands to run simulations, instruments, or tools. And a Ledger that keeps a receipt for everything that happened."
* **0:40–1:00 (The lab wakes up):** "When I start a campaign, autolab does not just run a checklist. It breaks the goal into work, assigns that work to the available machines, and records each step as it happens."

### Act 2 — The scientist loop
* **1:00–1:20 (A result appears):** "Let's say we're designing a new magnetic sensor. A standard AI just chases a high score, completely blind. But a scientist looks at the shape of the result and asks: what does this mean?"
* **1:20–1:40 (Claude reads the evidence):** "autolab gives Claude the actual figure, not just the number. Claude writes down a hypothesis, how confident it is, and what experiment would check it."
* **1:40–2:00 (The plan changes):** "Then the lab changes course. It adds the next test, reshuffles the plan, and keeps the original reasoning. The hypothesis is not treated as truth. It is tested."

### Act 3 — The data moat compounds
* **2:00–2:20 (Claude vs BO):** "Here is the same problem with a standard optimiser. It sees only a number, so it wanders. Claude sees the evidence, reasons from the pattern, and gets to a better design faster."
* **2:20–2:40 (Human-in-the-loop):** "But scientists are still in the driver's seat. If I step in and change the constraints, the lab adapts instantly—and permanently logs my decision. At the end, it produces the design, the recipe, and the record of how it got there."
* **2:40–3:00 (The true moat):** "This is the real prize: not one lucky result, but a growing record of what worked, what failed, and why. Every campaign makes the next one smarter."
* **Close:** "autolab: the autonomous lab for the next materials era."

---

## 3. The Comparison Analysis

1. **Accessibility & Tone:** 
   - *Original:* Heavy on technical jargon (`react()`, `SHA-256`, `Bayesian optimisation`). 
   - *Polished:* Uses powerful analogies ("Brain, Hands, Ledger", "completely blind", "driver's seat") that investors and non-technical judges instantly grasp.
2. **Emotional Arc:**
   - *Original:* A bit dry. Focuses purely on features (Planner, Provenance, Replay).
   - *Polished:* Starts with a grand societal hook ("Eras are defined by materials"). It makes the software feel like the missing piece of human progress.
3. **The Climax/Close:**
   - *Original:* Ended with `autolab replay` in a terminal. Very engineering-focused, but lacks an emotional punch.
   - *Polished:* Ends with the "Dataset Moat" concept ("Every campaign makes the next one smarter"). It pitches the *value* of the product, not just a CLI command.
