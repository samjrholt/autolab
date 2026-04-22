# autolab

**An autonomous lab with provenance as its foundation.**

autolab is a closed-loop, resource-aware framework for autonomous science. A long-running Lab service orchestrates experimental and computational workflows: an agent (Claude Opus 4.7) proposes and reacts, a typed pool of Resources executes, and every step — including the agent's reasoning and every failed or off-target attempt — lands as an append-only hashed Record. Adaptive mid-workflow replanning, live scheduler visualisation, and first-class provenance are core.

> **Status — alpha.** Core framework, FastAPI + WebSocket service, live Campaign Console, Claude Opus 4.7 Planner / PolicyProvider / free-text Campaign Designer, per-operation duration learning, and the Ledger-native MLflow-style query DSL are all in place. 119 tests pass. The framework scope is experimental + computational science; the current hackathon demo path is computational-only. Design contract lives in [docs/design/](docs/design/); task-shaped how-tos in [docs/guides/](docs/guides/).

## What it is

Three layers to anyone outside the project:

1. **Brain** — Claude Opus 4.7 as Planner and PolicyProvider, reading records and rendered figures and deciding what to do next.
2. **Hands** — Capability-named tools and operations that execute scientific work on typed resources. Simulation and computation are the current demo path; the same interfaces are intended to support instrument-backed operations too.
3. **Ledger** — An append-only, hashed, replayable scientific record with tags and free-text annotations on every entry. The substrate that makes the autonomy trustworthy and the evidence compound across campaigns.

Five layers under the hood: Interface, Orchestration, Expertise, Tools (MCP gateway + capability-named registry, Interpretation Operations included), Provenance.

## Quickstart

```bash
pixi install           # set up the Python 3.12 environment
pixi run frontend-build # build the Console bundle into src/autolab/server/static/
pixi run serve         # boot uvicorn on :8000 — FastAPI + WebSocket + Console
```

Open `http://localhost:8000/` for the live Campaign Console — resource-lane
orchestration, adaptive plan view, live result spotlight, Claude-driven
free-text Campaign Designer, intervention flow, and provenance drawer. See
[docs/guides/00-quickstart.md](docs/guides/00-quickstart.md) for the five-minute
tour.

For frontend work, pixi also manages the Node toolchain:

```bash
pixi run frontend-install  # install npm dependencies in frontend/
pixi run frontend-dev      # run the Vite dev server on :5173
pixi run frontend-build    # emit the production bundle for FastAPI
```

### HTTP surface (partial)

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/status` | Lab overview: resources, tools, campaigns, record counts, ETAs. |
| `POST` | `/resources` | Register a Resource (body = JSON). |
| `POST` | `/tools/register-yaml` | Register a capability from a JSON/YAML declaration. |
| `POST` | `/workflows` | Register a reusable `WorkflowTemplate`. |
| `POST` | `/campaigns` | Submit a Campaign (planner picked by name). |
| `POST` | `/campaigns/design` | Claude turns free text into a draft Campaign + workflow. |
| `GET`  | `/ledger?filter=…` | Query the Ledger with an MLflow-style DSL. |
| `GET`  | `/estimate/eta?campaign_id=…` | Projected finish time from the duration model. |
| `POST` | `/records/{id}/annotate` | Append a hashed note to any Record. |
| `GET`  | `/verify` | Recompute every Record's SHA-256 and flag mismatches. |
| `WS`   | `/events` | Live event stream — records, campaigns, resources, escalations. |
| `POST` | `/workflows/{name}/run` | Execute a registered WorkflowTemplate directly. |
| `POST` | `/records/{id}/extract` | Run `annotation_extract` — Claude reads notes, returns structured Claim. |
| `GET`  | `/samples/{id}/history` | Sample lineage + every Record that touched a Sample. |
| `GET`  | `/export/ro-crate` | RO-Crate 1.1 JSON-LD export (ELN Consortium interop). |
| `GET`  | `/export/prov` | W3C PROV-O shaped JSON export. |

### CLI

```bash
pixi run autolab serve                             # boot the service
pixi run autolab status                            # pretty-print /status
pixi run autolab verify --root .autolab-runs/...   # rehash every Record
pixi run autolab replay --root .autolab-runs/... --campaign <id>
pixi run autolab export --root .autolab-runs/... --fmt ro-crate > campaign.json
```

`autolab replay` is the credibility anchor — for every Record in a
campaign it re-canonicalises the payload, recomputes the SHA-256, and
reports any drift from the stored checksum.

### Bootstraps (`AUTOLAB_BOOTSTRAP`)

| Mode | Registers |
|---|---|
| `superellipse` (default) | `superellipse_hysteresis` capability + `pc-1` computer Resource. |
| `mammos` | All 6 MaMMoS Operations + `mammos_sensor` WorkflowTemplate + `vm-primary` VM Resource. |
| `all` | Both of the above. |
| `demo_quadratic` | Trivial stub Operation (no domain viz). |
| `none` | Empty Lab — register resources/tools via REST. |
| `module:fn` | Dotted path to a user-supplied `bootstrap(lab)` function. |

### Still planned

- Re-execution-style replay (running cached Operation outputs), not just checksum replay.
- LabIMotion-style Segments (typed metadata blocks attachable to Records).

## Repo layout

| Path | What it is |
|---|---|
| [`src/autolab/`](src/autolab/) | The Python package. |
| [`tests/`](tests/) | pytest unit + integration. |
| [`docs/design/`](docs/design/) | Design synthesis, glossary, scenarios, thesis. |
| [`docs/architecture/`](docs/architecture/) | Concrete architecture docs (as written). |
| [`docs/examples/`](docs/examples/) | Documented example workflows. |
| [`frontend/`](frontend/) | React + Vite Campaign Console source, built via pixi tasks. |
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
