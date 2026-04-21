# autolab

**An autonomous lab with provenance as its foundation.**

autolab is a closed-loop, resource-aware framework for autonomous science. A long-running Lab service orchestrates experimental or computational workflows: an agent (Claude Opus 4.7) proposes and reacts, a typed pool of Resources executes, and every step — including the agent's reasoning and every failed or off-target attempt — lands as an append-only hashed Record. Adaptive mid-experiment replanning, live scheduler visualisation, real multiscale physics, and first-class capture of scientific intuition are core.

> **Status — pre-build.** The framework is being scaffolded. The design contract lives in [docs/design/](docs/design/); implementation begins April 2026.

## What it is

Three layers to anyone outside the project:

1. **Brain** — Claude Opus 4.7 as Planner and PolicyProvider, reading records and rendered figures and deciding what to do next.
2. **Hands** — Capability-named tools behind one MCP gateway, including *Interpretation Operations* that call Claude to read a figure and return a structured Claim. Simulation today, real instruments tomorrow.
3. **Ledger** — An append-only, hashed, replayable scientific record with tags and free-text annotations on every entry. The substrate that makes the autonomy trustworthy and the evidence compound across campaigns.

Five layers under the hood: Interface, Orchestration, Expertise, Tools (MCP gateway + capability-named registry, Interpretation Operations included), Provenance.

## Quickstart (planned)

```bash
# Install the environment via pixi.
pixi install

# Boot the Lab — FastAPI + WebSocket on :8000.
pixi run serve

# Register resources / tools / workflows against the running Lab.
pixi run autolab register resource examples/resources/example-furnace.yaml

# Start a campaign.
pixi run autolab campaign start examples/campaigns/example-campaign.yaml

# Reproduce a past campaign byte-for-byte.
pixi run autolab replay <campaign-id>
```

(Commands above are the planned CLI surface; several are not yet implemented.)

## Repo layout

| Path | What it is |
|---|---|
| [`src/autolab/`](src/autolab/) | The Python package. |
| [`tests/`](tests/) | pytest unit + integration. |
| [`docs/design/`](docs/design/) | Design synthesis, glossary, scenarios, thesis. |
| [`docs/architecture/`](docs/architecture/) | Concrete architecture docs (as written). |
| [`docs/examples/`](docs/examples/) | Documented example workflows. |
| [`frontend/`](frontend/) | React + Vite + Tailwind Campaign Console (to be scaffolded). |
| [`CLAUDE.md`](CLAUDE.md) | Guidance for Claude Code working in this repo. |
| [`pyproject.toml`](pyproject.toml) | Python package metadata + lint / type / test config. |
| [`pixi.toml`](pixi.toml) | Environment + task manifest. |

## Design contract

Before changing framework code, read (in this order):

1. [docs/design/autolab-ideas-foundation.md](docs/design/autolab-ideas-foundation.md) — the load-bearing design synthesis.
2. [docs/design/GLOSSARY.md](docs/design/GLOSSARY.md) — canonical terms.
3. [docs/design/scenarios.md](docs/design/scenarios.md) — real scientist-workflow pressure tests.
4. [CLAUDE.md](CLAUDE.md) — current-state design contract, invariants, locked decisions.

## Licence

Apache-2.0 — see [LICENSE](LICENSE).
