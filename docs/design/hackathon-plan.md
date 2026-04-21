# autolab — Built with Opus 4.7 Hackathon Plan

**Event:** Built with Opus 4.7 (Cerebral Valley × Anthropic), virtual
**Dates:** Tue 21 Apr 2026 12:30 PM EST → Sun 26 Apr 2026 8:00 PM EST
**Team:** Sam Holt (solo — add a second builder only if a trusted person appears on Discord in the first 12 h)
**Submission:** GitHub repo (Apache-2.0, public from commit 1) + 3-min demo video + 100–200 word summary

> **Partially superseded — see CLAUDE.md.** Additionally, on 2026-04-22 the "Skill" abstraction was removed from the autolab model. Every reference below to `Skill`, `SKILL.md`, `hysteresis-interpreter` (as a Skill), or "five Skills" is superseded by **Interpretation Operations** — capabilities whose adapters call Claude and return Claim Records. See [2026-04-22-interpretations-and-metadata.md](2026-04-22-interpretations-and-metadata.md) §2. The framing "scientific record with an agent attached" is superseded by "autonomous lab with provenance as its foundation" (same doc §1).

---

## 1. The one-liner (lock this)

> **autolab is a scientific record with an agent attached — Claude runs experiments through a multiscale simulation, every step is hashed into an append-only ledger, and any lab can replay the campaign byte-for-byte.**

**Three layers the audience needs to hold in their head** (everything else is internal):

1. **Brain** — Claude Opus 4.7 + Skills. Decides and interprets.
2. **Hands** — Tools (simulation today, hardware tomorrow). Run the science.
3. **Ledger** — Hashed, replayable records. **The product.**

Every demo talking point points at one of these three. If a feature doesn't belong to one cleanly, it's cut.

**Demo frame:** *Design the magnetic free layer for a GMR-based speed sensor for an EV motor — linear across ±50 mT, sensitivity > 5 %/mT, operating to 180 °C — and give me the recipe.*

**Prizes targeted:** 1st/2nd/3rd main pool + **Best use of Claude Managed Agents ($5k)** + **Keep Thinking ($5k)**.

---

## 1b. Judging rubric → concrete moves

Stage 1 is asynchronous on 26–27 Apr. Judges see only: **3-min video, repo, 100–200 word summary.** Stage 2 (28 Apr 12:00 EST) replays the same video for the top 6. **Nothing new is built between submission and live judging** — the video is the submission, permanently.

| Criterion | Weight | How we score | Target |
|---|---|---|---|
| **Impact** | 30% | Named users (experimental labs, sensor OEMs), named market (EV / wind / fusion magnets), named adoption path ("one real VSM plugs in next quarter via MCP"). Explicit fit with "Build From What You Know." | 25–28 / 30 |
| **Demo** | 25% | Three visual beats: plan-tree blooming, hysteresis loop *morphing live*, split-screen vs BO, human intervention, auto-generated hash-stamped report. **Narration never stops.** Pre-cached run for the record. | 18–22 / 25 |
| **Opus 4.7 Use** | 25% | Managed Agents + Skills + MCP + **vision** (Opus reads the hysteresis PNG, not just the numbers) + Claude Code as dev tool. The vision moment is the "surprised even us" beat. | 20–23 / 25 |
| **Depth & Execution** | 20% | Real multiscale physics, Merkle-hashed provenance, `autolab replay` verb, clean MCP spec, tests. Most hackathon repos will be 500-line chat wrappers — this is not. | 17–19 / 20 |

**Projected total: 80–92 / 100.** Top-6 plausible; top-3 needs the vision beat + clean demo. **Nothing in Stage 2 can be improved after submission** — over-invest in the video.

**README must include a "Why this project" paragraph mapping explicitly to the four criteria.** Judges skim. Make it tickable.

---

## 2. Non-negotiable constraints

- **100 % new code.** Fresh repo, first commit after 12:30 PM EST 21 Apr. No copy-paste from `matdiscovery` or MaMMoS internals. MaMMoS, ubermag, pymatgen, Materials Project client used only as installed pip dependencies.
- **Apache-2.0, public, from commit 1.** Required by hackathon rules.
- **Every tool call goes through the provenance store.** No exceptions. If it isn't logged, it didn't happen.
- **Demo must run end-to-end on Sam's laptop, offline except for Claude API.** No "cloud magic" the judges can't verify.
- **3-minute demo video is the submission.** Everything else supports the demo.

---

## 3. Architecture — three layers externally, five internally

**What the audience sees (three layers):**

| Layer | What it does |
|---|---|
| **1. Brain** | Claude Opus 4.7 + Skills decide and interpret. |
| **2. Hands** | Tools (capability-named) run the science. |
| **3. Ledger** | Append-only hashed records. Replayable. Mergeable across labs. |

**What we actually build (five layers under the hood):**

| Layer | What it is | Tech |
|---|---|---|
| **1. Interface** | Persistent Campaign Console (web) + CLI | FastAPI + WebSockets + React/Vite (Tailwind); Typer CLI |
| **2. Orchestration** | Two-tier agents (Principal PI + Campaign subagents). Subagent file format follows Anthropic's `agents/*.md` spec. | Claude Managed Agents, Opus 4.7 |
| **3. Expertise** | Crystallised domain knowledge. SKILL.md format verbatim from Anthropic. Each skill is SHA-256 hashed and active-skill set enters every record. | Claude Skills |
| **4. Tools** | Capability-named (not library-named). One MCP gateway exposes an in-repo tool registry of YAML declaration files. Each file: `name`, `capability`, `inputs`, `outputs`, `resource`, `invoke`, `provenance_class`. Declaration-file SHA-256 goes into every record. | One MCP gateway + `autolab/tools/*.yaml` |
| **5. Provenance** | Append-only, hashed, reproducible record store. Framework-enforced writes on every operation. | SQLite + SHA-256 per record + campaign-level Merkle root; `autolab replay <hash>` |

**Do not explain layers 2–5 to judges.** They map onto Brain/Hands/Ledger. The elaborate design is what makes the three-layer story honest.

---

## 4. Repo layout (create in order Day 0)

```
autolab/
├── LICENSE                       # Apache-2.0
├── README.md                     # pitch + demo GIF + quickstart
├── pyproject.toml                # uv / hatch, Py 3.12
├── .github/workflows/ci.yml      # lint + tests + build console
├── autolab/
│   ├── __init__.py
│   ├── cli.py                    # `autolab run`, `autolab replay`, `autolab serve`
│   ├── console/                  # FastAPI app + WebSocket hub
│   │   ├── app.py
│   │   ├── ws.py
│   │   └── static/               # built React bundle
│   ├── agents/
│   │   ├── principal.py          # Managed Agent definition
│   │   ├── campaign.py           # subagent definition
│   │   └── prompts/
│   │   ├── hysteresis-interpreter/   # interpretive (vision)
│   │   ├── phase-diagnoser/          # interpretive
│   │   ├── thermal-stability-check/  # interpretive
│   │   ├── sensor-response-evaluator/ # interpretive
│   │   └── anneal-recipe-writer/     # procedural — competence, not commentary
│   ├── mcp/                      # ONE MCP gateway (not many servers)
│   │   └── gateway.py            # exposes the tool registry over MCP
│   ├── tools/                    # capability-named YAML declaration files + adapters
│   │   ├── micromagnetics_hysteresis.yaml   # backend: MaMMoS / ubermag
│   │   ├── dft_intrinsics.yaml              # backend: MaMMoS-DFT (cached)
│   │   ├── device_response.yaml             # backend: closed-form GMR model
│   │   ├── literature_lookup.yaml           # stub
│   │   ├── hardware_stub.yaml               # proves the interface shape
│   │   └── adapters/             # Python adapters called by the gateway
│   │       ├── mammos_backend.py
│   │       ├── device_model.py
│   │       └── hardware_stub.py
│   ├── skills/                   # Anthropic SKILL.md format, verbatim
│   ├── provenance/
│   │   ├── store.py              # SQLite append-only
│   │   ├── records.py            # pydantic schemas
│   │   ├── merkle.py
│   │   └── replay.py
│   ├── physics/                  # thin adapters over MaMMoS
│   │   ├── device_model.py       # closed-form sensor response
│   │   └── cache.py              # memoised expensive calls
│   └── baseline/
│       └── bo.py                 # BO using scikit-optimize (for split-screen)
├── frontend/                     # React/Vite source
├── examples/
│   └── gmr_sensor_demo.yaml      # the demo campaign
├── docs/
│   ├── architecture.md
│   ├── tool-interface.md         # the capability-named tool spec (adapters or MCP)
│   └── provenance.md
└── tests/
```

---

## 5. Six-day schedule

Hours are UK time (EST+5). Hacking opens 17:30 UK.

### Day 0 — Tue 21 Apr (kickoff → midnight UK, ~6 h)
**Goal: skeleton green + one real MaMMoS call working end-to-end.**
- [ ] 17:00–17:30 UK — watch virtual kickoff; join Discord; get role assigned.
- [ ] 17:30–18:00 — create `autolab` GitHub repo, Apache-2.0, first commit (empty README + LICENSE + pyproject).
- [ ] 18:00–19:30 — scaffold repo layout above (Claude Code drives this); CI green.
- [ ] 19:30–21:00 — `provenance/store.py` + `records.py` + unit tests (this is the product; build it first).
- [ ] 21:00–22:30 — stand up the MCP gateway (`autolab/mcp/gateway.py`) + one capability-named tool (`micromagnetics_hysteresis.yaml` + its adapter) that actually runs one cached micromagnetic hysteresis and returns it through the provenance store.
- [ ] 22:30–23:30 — minimal FastAPI `/ws` that streams a `RunRecord` to a static HTML page — console v0.
- **End-of-day gate:** one real hysteresis loop computed, logged with hash, visible in browser. Commit tagged `day-0`.

### Day 1 — Wed 22 Apr (~8 h)
**Goal: Principal + one Campaign subagent run a 3-step campaign end-to-end.**
- [ ] Morning: Principal Agent as a Managed Agent, minimal prompt, tool list = provenance + one MCP. Attend Thariq Shihipar AMA 17:00 UK for Claude Code best practices.
- [ ] Afternoon: Campaign subagent spawn/handoff pattern. Principal decomposes goal → delegates one hypothesis → subagent runs tools → reports back.
- [ ] Evening: wire the remaining capability-named tools behind the gateway: `dft_intrinsics` (cached), `device_response` (closed-form GMR model), `literature_lookup` (stub), `hardware_stub`. All five YAMLs SHA-256 hashed; hashes stamped into every record.
- [ ] 22:00–23:00 UK — Anthropic office hours (#office-hours) — ask about Managed Agents long-run semantics.
- **End-of-day gate:** type a goal in a YAML file, run `autolab run`, get a 3-step campaign with provenance and a final (possibly wrong) candidate. Commit tagged `day-1`.

### Day 2 — Thu 23 Apr (~8 h)
**Goal: Console v1 + Skills + the physical debugging loop.**
- [ ] Morning: attend Michael Cohen Managed Agents talk 16:00 UK — take notes, adjust Principal design if needed.
- [ ] 11:00 plan tree + run feed + live physics panel in React. WebSocket streams every record as it lands. Intervention box wired to provenance.
- [ ] Afternoon: write the five Skills (SKILL.md each + any helper scripts). Keep each under 500 words of instructions. The `hysteresis-interpreter` skill is the demo hero — it must reliably identify kinks, shoulders, and phase contamination **and it must accept the rendered loop as a PNG and reason over the image using Opus 4.7 vision**. This is the "surprised even us" beat.
- [ ] Evening: engineer the physical debugging loop — Principal receives a kinked loop, invokes `hysteresis-interpreter` Skill, diagnoses soft-phase contamination, raises anneal temperature, reruns, gets clean loop.
- **End-of-day gate:** console shows full campaign live with tree + loops morphing + Skill diagnoses in reasoning feed. Commit tagged `day-2`.

### Day 3 — Fri 24 Apr (~8 h)
**Goal: baseline, reproducibility, auto-report, hardening.**
- [ ] Morning: BO baseline (`baseline/bo.py`) on the same task. Split-screen view in console — Claude left, BO right, shared objective plot.
- [ ] Midday: `autolab replay <hash>` CLI verb — replays a campaign byte-for-byte against cached tool outputs. This is the demo's credibility anchor.
- [ ] Afternoon: auto-generated 1-page report. Jinja template → markdown → weasyprint PDF → embed in console. Includes Merkle root.
- [ ] Evening: attend Mike Brown (prior winner) 17:00 UK talk; harden one full end-to-end campaign run; fix any races in WS stream; write 15 unit tests minimum.
- **End-of-day gate:** end-to-end dry run records cleanly in ~6 min wall-clock. Commit tagged `day-3`.

### Day 4 — Sat 25 Apr (~10 h)
**Goal: demo polish + recording + documentation.**
- [ ] Morning: do 3 full dry runs back-to-back. Time each beat. Kill anything that takes >5 s without visible progress. Pre-warm caches for the recorded run.
- [ ] Midday: console visual polish — typography, colour, Tailwind fit-and-finish. Make the plan tree *beautiful*. Make loops morph smoothly.
- [ ] Afternoon: **record the 3-min video.** Script in §7. Use OBS, 1080p, clean terminal + console + one browser tab. Record narration separately, mix in post. Aim for 3–5 takes.
- [ ] Evening: `README.md` polish — hero GIF, one-liner, 3-line quickstart, architecture diagram (Brain/Hands/Ledger), demo video embed. `docs/tool-interface.md` — the capability-named tool spec (one YAML per capability) that local adapters **or** an external MCP server can implement. This is the moat in writing.
- **End-of-day gate:** video rendered, README shippable. Commit tagged `day-4`.

### Day 5 — Sun 26 Apr — submission day (hard stop 01:00 UK Mon 27 Apr = 20:00 EST Sun)
- [ ] Morning/midday: one pristine live dry-run to catch regressions from any late commits.
- [ ] 14:00 UK: attend Michal Nedoszytko (3rd place winner) 17:00 UK EST → Nothing wait, that's 18:00 UK. Cool listening while you lint.
- [ ] 16:00–22:00 UK: final polish. Commit tag `v1.0.0`. Push. Upload video to YouTube (unlisted, then public at 19:00 UK). Write the 100–200 word summary (§8). Submit via CV platform.
- [ ] **HARD STOP 20:00 EST = 01:00 UK Mon.** Do not touch the repo after submission.

---

## 6. Scope discipline — the "cut list"

In if it earns the demo:
- Two-tier Managed Agents, one Principal, **exactly one** Campaign subagent (visibly context-isolated)
- One MCP gateway exposing five capability-named tools: `micromagnetics_hysteresis`, `dft_intrinsics` (cached), `device_response`, `literature_lookup` (stub), `hardware_stub`
- Five Skills (four interpretive + one procedural). `hysteresis-interpreter` is the only one truly polished.
- Console with plan tree, run feed, live physics panel, intervention box, report view, **visible ledger panel showing record chain + Merkle root**
- Three record origins visible in the demo: one simulated, one hardware-stub, one mocked-imported-from-a-partner-lab — all Merkle-linked, same schema (≈40 lines of code, earns the modularity claim)
- BO baseline for split-screen
- Merkle-hashed provenance + `autolab replay`
- Auto-generated 1-page PDF report
- Diagnoses logged as **claims with confidence**, not facts (see §7, Beat 2)

**Explicitly cut:**
- SEM / XRD simulation (not in the demo path)
- Multi-user auth
- Any database other than SQLite
- Cloud deployment — runs on Sam's laptop
- Tests beyond the provenance layer + MCP server happy paths (aim 20–40 total, not 200)
- A pretty logo (README text is enough)
- The hardware-stub MCP does nothing — it is 40 lines that prove the interface shape. Spec only.
- Any optimiser other than BO for baseline
- Multiple material systems — GMR free layer only
- Real DFT runs at demo time — cache hits only
- "Autonomous" claims for the ~1 Campaign subagent — it's real, but don't oversell

If day-2 end-of-day gate is missed, cut: literature MCP, second Campaign subagent, BO split-screen, in that order.

---

## 7. The 3-minute demo script

Aim: **three beats**, each ~45 s, + 30 s intro + 15 s outro.

**0:00–0:15 — Hook (voiceover over console opening)**
> "This is a magnet. Your car has dozens of them. Designing one to spec takes a PhD student months of synthesis, measurement, guessing what went wrong, and trying again. I'm Sam Holt — I did that PhD. Tonight I'll show you autolab doing it in six minutes. Then I'll show you why the speed isn't the interesting part."

**0:15–0:30 — Setup (lock the three layers)**
- Screen: Campaign Console, empty. Goal field: *"Design a free layer for a GMR speed sensor — ±50 mT linear range, > 5 %/mT sensitivity, operates to 180 °C. Give me a recipe."*
- Voiceover: **"autolab is three things. A **brain** — Claude Opus 4.7 with a handful of Skills. **Hands** — a multiscale simulation stack today, real instruments tomorrow. And a **ledger** — every decision, every measurement, hashed into an append-only record. The ledger is the product."**

**0:30–1:15 — BEAT 1: plan blooms, ledger starts filling**
- Plan tree blooms on screen, three sibling hypotheses. Principal Agent spawns one Campaign subagent to pursue the strongest.
- Run feed streams tool calls in plain English: *"Checking intrinsic parameters for Fe₆₀Co₃₀Mn₁₀..." → "Running micromagnetic hysteresis..."*. Ledger panel shows records landing with hashes as they complete.
- First hysteresis loop appears — *kinked*.
- Voiceover: "The Campaign subagent runs in its own context window — the Principal never sees the 15 tool calls underneath, just the result. That's how this scales."

**1:15–2:00 — BEAT 2: the physical debugging loop + honesty beat**
- On-screen overlay: *"Opus 4.7 reads the loop image directly."* The rendered PNG is handed to the `hysteresis-interpreter` Skill. Claude returns a structured diagnosis: *soft-phase contamination, confidence 70%, recommended action: raise anneal temperature by 150 °C.*
- **Honesty beat (one line, 6 seconds):** *"That diagnosis is logged as a hypothesis with confidence — not as truth. The next run validates it. Both go into the ledger."*
- Second hysteresis loop morphs clean on screen. Ledger panel shows the validation record linked to the diagnosis record by parent_id.
- Split-screen briefly: left is Claude's campaign; right is a Bayesian-optimisation baseline on the same problem, still wandering.
- Wall-clock overlay: *"Equivalent bench time: 4 months. Real elapsed here: 47 seconds."*
- Voiceover: "Bayesian optimisation sees a number. Claude sees the loop — the actual image, the shape a scientist would read — proposes the physics, then checks itself. That's the difference."

**2:00–2:30 — BEAT 3: the ledger opens + human intervention + report**
- Sam types into the intervention box: *"Restrict to Co > 30 % — I want stronger anisotropy."* Plan tree reshuffles live; the intervention itself is recorded as a hashed entry in the ledger — not lost in a Slack message.
- One click opens the **ledger panel**: three record origins side by side — one simulated, one hardware-stub, one mocked-imported-from-a-partner-lab — **same schema, all Merkle-linked**. Sam runs `autolab replay <hash>` in the terminal. The campaign replays byte-for-byte.
- Target hit. Report PDF renders: composition, recipe, predicted performance, uncertainty, Merkle root.
- Voiceover: **"This is the first scientific record you can merge across labs without either side having to trust the other. That's the dataset nobody else has."**

**2:30–3:00 — Close (named adoption path for Impact score)**
- Screen: architecture diagram (Brain / Hands / Ledger) + one sentence overlay.
- Voiceover: "autolab is the brain. MaMMoS is one pair of hands. Next quarter a real VSM magnetometer at Max Planck plugs in — same tool spec, same ledger. Open source, Apache-2.0. Repo in the description. Thanks."

---

## 8. Written summary (≤200 words — submission draft)

```
autolab is a scientific record with an agent attached. A Principal Agent
— built on Claude Opus 4.7 Managed Agents — takes a device-level goal in
plain English ("design a free layer for a GMR speed sensor, linear across
±50 mT, operating to 180 °C"), decomposes it, and delegates to a Campaign
subagent that runs a real multiscale simulation stack (DFT → spin dynamics
→ micromagnetics → device model) through capability-named tools behind a
single MCP gateway.

Domain expertise lives in Claude Skills: reading a hysteresis loop, flagging
secondary phases, checking thermal stability, writing anneal recipes. When
a simulated measurement comes back wrong, Opus 4.7 reads the loop image
directly, logs a diagnosis as a claim with confidence, adapts the recipe,
and validates it on the next run — the physical debugging loop that no
static notebook workflow can do.

Every tool call, every skill invocation, every human intervention is written
to an append-only provenance store with SHA-256 per record and a Merkle root
per campaign. `autolab replay <hash>` reproduces a campaign byte-for-byte.
Two labs can merge campaigns without either having to trust the other.

Today autolab drives a simulated lab. Tomorrow a real VSM plugs into the
same tool spec. The ledger is the product.

Apache-2.0. github.com/samjrholt/autolab.
```

Word count ≈ 210 — trim a sentence if over limit.

---

## 9. Office-hours + live-session priority

Only attend the ones that move the build:
- **Wed 22 Apr 17:00 UK — Thariq Shihipar AMA on Claude Code.** Ask: pattern for Managed Agent that emits intermediate artefacts to a WebSocket.
- **Thu 23 Apr 16:00 UK — Michael Cohen, Managed Agents.** Ask: long-running task checkpoint/resume semantics; how to pass structured state between Principal and subagents.
- **Fri 24 Apr 17:00 UK — Mike Brown winner talk.** Listen for demo craft; don't talk.
- **Office hours (22:00–23:00 UK daily).** Only drop in if blocked.

Skip everything else.

---

## 10. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Managed Agents API surface shifts during hackathon | M | Pin versions at commit 1; isolate in `agents/` so swap cost is bounded |
| MaMMoS dependency install breaks on my machine | M | Pin versions; fall back to thin surrogate in `physics/` for any module that fails; *never* mock without logging it as surrogate in provenance |
| Demo takes >3 min to run at recording time | H | Pre-cache every MCP call in the recorded campaign; record a final clean run; keep narration on a separate audio track so length is controllable |
| Frontend polish eats time | H | Budget capped at 6 h total; ugly-but-clear beats beautiful-but-late; Tailwind + shadcn defaults |
| I get sick / lose a day | M | Day-4 is buffer; ship with day-3 state if forced |
| Solo builder burnout | H | Hard stop every day by 01:00 UK; no post-01:00 commits |
| Someone else ships "AI scientist" with better polish | M | Our moat is provenance + MaMMoS wiring + domain Skills — not achievable without magnetism background |
| Claude rate limits during demo recording | L | $500 credits is ample; schedule recording outside of US-peak hours |

---

## 11. Post-submission follow-through (week of 27 Apr)

- **Mon 27 Apr** — asynchronous judging day. Do not touch the repo. Nap. Draft a 2–3 sentence LinkedIn post + the demo video for immediate publish.
- **Tue 28 Apr 12:00 EST (17:00 UK)** — top-6 announcement in Discord #announcements. Be online. Closing ceremony 12:45 EST (17:45 UK). Whether or not you place: post the LinkedIn update + send the repo link to Michael Cohen / Thariq ("built on Managed Agents, thanks for the talk") within 2 hours.
- Update STEM Fellows application supplement with repo + video link if the form allows.
- Add `autolab` repo + demo video to CV, LinkedIn featured section, and profile README.
- Whatever the placement, the artefact is now permanent proof. That is the real prize.

---

## 12. One-line commit (read this tomorrow morning)

> **Ship a console — not a chat — that shows a real Managed Agent driving real multiscale magnetism simulations through MCP, with every decision hashed and replayable. GMR sensor demo, six minutes, one laptop, open-source, Apache-2.0.**

**Go.**
