# autolab

**An autonomous lab with provenance as its foundation.**

autolab is a closed-loop, resource-aware framework for autonomous science. A long-running Lab service orchestrates experimental and computational workflows. An agent (Claude Opus 4.7) proposes and reacts. A typed pool of Resources executes. **Every step — including the agent's reasoning, every failed attempt, and every interim figure — lands as an append-only hashed Record on the Ledger.** Adaptive mid-workflow replanning, live scheduler visualisation, and first-class provenance are the foundation, not afterthoughts.

The framework scope is experimental + computational science. The shipped demo runs computationally — micromagnetic sensor design end-to-end, head-to-head between Claude as Planner and Optuna TPE. Same workflow, same resource, same budget; you watch the ledger fill in real time.

> **Apache-2.0** · public from commit one · alpha. Test suite passes. CI runs lint + tests + frontend build on every push.

---

## Why this is different

Four axes of differentiation, called out explicitly because the same words mean different things in adjacent tools:

1. **`react()` — adaptive mid-experiment replanning.** A Planner proposes, the Lab executes one Operation, and the policy reads the *just-finished* Record (its outputs, its rendered figure, the trend so far) and chooses one of nine structured Actions: `continue`, `add_step`, `retry_step`, `replan`, `branch`, `accept`, `escalate`, `ask_human`, or `stop`. No public autonomous-lab framework supports clean per-step replanning today; the others run fixed DAGs inside an experiment.

2. **Resource-aware, cross-experiment, cross-campaign scheduling with live visualisation.** Operations from different Experiments interleave on shared typed Resources (compute workers, GPU partitions, instruments) while the resource-lane Gantt and plan tree update in real time over a WebSocket.

3. **Framework-enforced, write-ahead, hashed, append-only provenance, with byte-for-byte replay.** Operations never write Records directly — the orchestrator wraps every call and persists a write-ahead Record *before* the operation runs. Failures are Records (`status: "failed"`) with a `failure_mode`, not exceptions. Every Record carries a SHA-256. `autolab replay` re-canonicalises every Record's payload and reports any drift.

4. **Opus 4.7 vision driving `react()`.** Any Operation that emits a `*_png` artefact has its rendered figure passed to Opus alongside the structured DecisionContext. The agent reads a hysteresis loop the way a scientist reads it — visually, then numerically — and proposes the next step on that basis.

The sensor demo exercises all four.

---

## Run the demo in three commands

```bash
pixi install                              # set up Python 3.12 + Node toolchain (pinned)
cp .env.example .env                      # add ANTHROPIC_API_KEY to enable Claude
pixi run serve                            # boot the Lab on :8000 (FastAPI + WebSocket + Console)
```

In a second terminal:

```bash
pixi run sensor-demo                      # register the demo against the running Lab
```

This:

1. POSTs the `sensor_shape_opt` bootstrap (registers `vm-primary` Resource, the two MaMMoS sensor Operations, and the workflow).
2. Creates two prepared comparison Campaigns (`sensor-shape-opt (optuna)` and `sensor-shape-opt (claude)`) with the same budget, bounds, and objective — `autostart=false` so you start them yourself from the Console.

Open [http://localhost:8000](http://localhost:8000) and start one or both campaigns. If `ANTHROPIC_API_KEY` is unset, autolab boots cleanly and the Optuna campaign works fine — Claude integrations fall back to a deterministic offline stub. Set the key to enable Claude as Planner / PolicyProvider / Campaign Designer.

---

## The shipped demo

`sensor_shape_opt` is a 5-D micromagnetic sensor design problem driven by real OOMMF.

| | |
|---|---|
| **Search space** | material ∈ {Fe16N2, Ni80Fe20, Fe2.33Ta0.67Y} × T_K ∈ [100, 650] × sx_nm ∈ [5, 150] × sy_nm ∈ [5, 150] × thickness_nm ∈ [1, 40] |
| **Objective** | maximise `Hmax_A_per_m` — the half-width of the linear region on the M-H half-sweep along the hard axis (the sensor's linear sensing range) |
| **Workflow** | `material` step (Ms(T), A(T), K1(T) from Kuzmin fit on `mammos_spindynamics` DB) → `fom` step (build elliptical mesh, run OOMMF `HysteresisDriver`, fit linear segment) |
| **Resource** | `vm-primary` — a WSL pixi env with `ubermag` + `oommfc` + `mammos-*` |
| **Budget** | 12 trials per planner |

**Physics quality** (everything below is on by default):

- Magnetocrystalline anisotropy K1(T) wired through from the Kuzmin fit and added as `mm.UniaxialAnisotropy` along the geometric long axis. Soft-magnet limit recovered exactly when K1 ≈ 0.
- Adaptive z-discretisation: `nz = round(thickness / lex)` where `lex = sqrt(2·A / (µ₀·Ms²))` is computed per trial. Thick films get multi-cell z-resolution instead of a single cell.
- Odd in-plane cell counts forced (`n_x = n_y = 2k+1`), so the central cell sits on (0, 0) and is always inside any non-degenerate ellipse — no more sub-cell-sized geometry artefacts.
- Degenerate-sample guard: if `(my_max - my_min) / Ms < 5%`, the trial fails with `failure_mode="process_deviation"` and the planner sees it in history.

**What you should expect to see in the Console:**

- Resource-lane Gantt with both campaigns interleaving on `vm-primary`.
- Plan tree mutating live as `react()` returns `continue` / `branch` / `replan` decisions.
- A "spotlight" card for each completed FOM trial with the rendered hysteresis-loop PNG and the linear-segment overlay.
- Per-trial reasoning: every Claude call is persisted as a hashed `claim` Record / Annotation, so the rationale ("best so far is at high AR thin film, push thickness next") is a citable artefact, not a chat log.

A representative reference run (12 + 12 trials, real OOMMF, fresh ledger): Optuna best ≈ **0.92 T**; Claude best ≈ **1.56 T** at trial 5 with `Fe16N2, sx=150, sy=5, t=40, T=100K`. Claude reaches the optimum in 5 trials by reading prior figures and reasoning about thickness; Optuna explores broadly and lands at ~0.9 T at trial 11. Both are well below the µ₀Ms ≈ 2 T physical ceiling for Fe16N2.

---

## Architecture

Three layers from outside:

1. **Brain** — Claude Opus 4.7 as Planner and PolicyProvider, reading records and rendered figures and deciding what to do next.
2. **Hands** — Capability-named tools and operations that execute scientific work on typed resources.
3. **Ledger** — Append-only, hashed, replayable scientific record with tags and free-text annotations on every entry.

Five layers under the hood: Interface, Orchestration, Expertise, Tools (MCP gateway + capability-named registry), Provenance.

**The Lab is a service, not a script.** One Lab instance = one persistent FastAPI + WebSocket service. Resources, Tools, Workflows, and Campaigns are registered against a running Lab. The Ledger belongs to the Lab and accumulates across campaigns.

The two work-bearing abstractions are:

- **Operation** — `async run(inputs) → OperationResult`, declares its capability + resource_kind + module version. Returns `status` + `outputs`. Failures are Records, not exceptions.
- **Planner** — `plan(history, resources)` for batch proposals + `react(record, plan)` for mid-experiment adaptation. Decisions are routed through an interchangeable **PolicyProvider** (heuristic, LLM, or human).

For the full design contract see [docs/design/autolab-ideas-foundation.md](docs/design/autolab-ideas-foundation.md), [docs/design/GLOSSARY.md](docs/design/GLOSSARY.md), and [CLAUDE.md](CLAUDE.md).

---

## Quickstart for development

```bash
pixi install                              # Python 3.12 + Node 22 toolchain
pixi run frontend-build                   # build the Console bundle into src/autolab/server/static/
pixi run serve                            # boot uvicorn on :8000 with --reload
```

Open [http://localhost:8000](http://localhost:8000) for the live Campaign Console.

For frontend hacking with hot reload:

```bash
pixi run frontend-install                 # npm install in frontend/
pixi run frontend-dev                     # Vite dev server on :5173 against the running Lab
```

CI / quality gates:

```bash
pixi run lint                             # ruff check + format check
pixi run typecheck                        # mypy
pixi run test                             # pytest unit + integration
pixi run e2e-headless                     # Playwright against the built Console
pixi run check                            # all of the above + frontend-build
```

---

## CLI

```bash
pixi run autolab serve                                     # boot the service
pixi run autolab apply-bootstrap sensor_shape_opt          # apply a named pack to a running Lab
pixi run autolab status                                    # pretty-print /status
pixi run autolab verify --root .autolab-runs/default       # rehash every Record, report drift
pixi run autolab replay --root .autolab-runs/default --campaign <id>
pixi run autolab export --root .autolab-runs/default --fmt ro-crate > campaign.json
```

`autolab replay` is the credibility anchor — for every Record in a campaign it re-canonicalises the payload, recomputes the SHA-256, and reports any drift from the stored checksum.

---

## HTTP surface

The Console talks to the same endpoints any client does. Selected highlights (full list at runtime via `GET /openapi.json`):

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/status` | Lab overview: resources, tools, campaigns, record counts, ETAs. |
| `POST` | `/bootstraps/apply` | Apply a named example pack to a running Lab. |
| `POST` | `/resources` · `/tools/register-yaml` · `/workflows` · `/campaigns` | Register entities. |
| `POST` | `/campaigns/design` | Claude turns free text into a draft Campaign + workflow. |
| `POST` | `/campaigns/{id}/intervene` · `/pause` · `/resume` · `/cancel` | Human controls — every intervention is a hashed Record. |
| `GET`  | `/ledger?filter=…` | Query the Ledger with an MLflow-style DSL. |
| `GET`  | `/estimate/eta?campaign_id=…` | Projected finish time from the per-operation duration model. |
| `POST` | `/records/{id}/annotate` · `/extract` | Append notes; let Claude turn notes into structured Claims. |
| `GET`  | `/verify` | Recompute every Record's SHA-256, flag mismatches. |
| `GET`  | `/export/ro-crate` · `/export/prov` | RO-Crate 1.1 / W3C PROV-O exports. |
| `GET`  | `/samples/{id}/history` | Sample lineage + every Record that touched it. |
| `WS`   | `/events` | Live event stream — records, campaigns, resources, escalations. |

---

## Bootstraps (`AUTOLAB_BOOTSTRAP`)

Apply at boot via env var, or against a running Lab via `pixi run autolab apply-bootstrap <mode>`.

| Mode | Registers |
|---|---|
| `none` (default) | Empty Lab — register everything via REST. |
| `sensor_shape_opt` | **The shipped demo.** `vm-primary` VM Resource + `mammos.sensor_material_at_T` and `mammos.sensor_shape_fom` Operations + `sensor_shape_opt` workflow. |
| `mammos` | The full 6-step MaMMoS multiscale chain (composition → relax → 0K intrinsics → finite-T → mesh → hysteresis → FOM). |
| `superellipse` | Older single-stage sensor example with a closed-form surrogate fallback. |
| `all` | `superellipse` + `mammos` together. |
| `demo_quadratic` | Trivial stub Operation for clicking around with no external deps. |
| `shell_command` | `shell_command` capability + `local-worker` Resource — full round-trip with a local subprocess backend. |
| `wsl_ssh_demo` | `wsl` SSH resource + `add_two`, `cube`, `add_two_then_cube` workflow + `wsl_ssh_add_cube_optuna` planner. |
| `module:fn` | Dotted path to a user-supplied `bootstrap(lab)` function. |

---

## Repo layout

| Path | What it is |
|---|---|
| [`src/autolab/`](src/autolab/) | The Python package — Lab, Orchestrator, Ledger, Planners, agents, server. |
| [`frontend/`](frontend/) | React + Vite Campaign Console source; built bundle ships in `src/autolab/server/static/`. |
| [`examples/`](examples/) | Registered demo packs. The headline is `mammos_sensor/`. |
| [`tests/`](tests/) | pytest unit + integration suites. |
| [`docs/design/`](docs/design/) | Foundation, glossary, scenarios, thesis — the design contract. |
| [`docs/architecture/`](docs/architecture/) | Concrete architecture documents. |
| [`docs/guides/`](docs/guides/) | Five-minute task-shaped how-tos: quickstart, adding a resource, adding an operation, etc. |
| [`scripts/`](scripts/) | Helper scripts that POST against a running Lab (`register_sensor_demo.py`, `seed_demo_ledger.py`, `clean_local_state.py`). |
| [`pixi.toml`](pixi.toml) | Environment + task manifest — every CLI entry point above is a pixi task. |
| [`pyproject.toml`](pyproject.toml) | Python package metadata + lint/type/test config. |
| [`CLAUDE.md`](CLAUDE.md) | Current-state design contract, invariants, locked decisions. |

---

## Design contract

Before changing framework code, read in this order:

1. [docs/design/autolab-ideas-foundation.md](docs/design/autolab-ideas-foundation.md) — the load-bearing design synthesis. §2 (the five moats), §3 (Operation / Planner), §6 (provenance), §21 (locked decisions).
2. [docs/design/GLOSSARY.md](docs/design/GLOSSARY.md) — canonical terms. Use these exactly; do not coin synonyms.
3. [docs/design/scenarios.md](docs/design/scenarios.md) — real scientist-workflow pressure tests.
4. [CLAUDE.md](CLAUDE.md) — current-state design contract, invariants, locked decisions, ambition level.

---

## Licence

Apache-2.0 — see [LICENSE](LICENSE).
