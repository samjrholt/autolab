# Quickstart

Boot the Lab, open the Console, watch a demo campaign run — five minutes.

## 1. Install

The repo is managed with [pixi](https://pixi.sh) — one command installs the
Python 3.12 environment and the editable `autolab` package:

```bash
pixi install
```

pixi also manages the frontend toolchain. If you want the latest Console
bundle from source, build it before serving:

```bash
pixi run frontend-build
```

For frontend development, use `pixi run frontend-install` once and then
`pixi run frontend-dev`.

## 2. Boot the Lab

```bash
pixi run serve
```

This runs `uvicorn autolab.server.app:app --reload --port 8000`. On boot
the server:

- creates (or re-opens) the Ledger directory under `./.autolab-runs/default/`,
- pre-registers a demo Operation (`demo_quadratic`) and one Resource (`pc-1`)
  so the UI is not empty,
- launches the `CampaignScheduler` as a background task,
- starts a single WebSocket fan-out for live events.

Override the on-disk root by setting `AUTOLAB_ROOT=/path/to/dir`. To skip
the demo stubs, set `AUTOLAB_BOOTSTRAP=none`. To wire your own bootstrap,
set `AUTOLAB_BOOTSTRAP=my_package.my_module:my_bootstrap_fn`. Keep bootstrap
selection explicit in the command you run; the repo `.env` is reserved for
`ANTHROPIC_API_KEY`.

For packs you want to test through the normal UI/REST registration path,
prefer a clean lab plus a runtime apply instead of a startup bootstrap:

```powershell
pixi run serve-clean
pixi run apply-bootstrap -- wsl_ssh_demo
```

Shortcut for the WSL SSH example:

```powershell
pixi run apply-wsl-ssh
```

For a truly blank manual smoke-test ledger, use a dedicated root:

```powershell
pixi run serve-clean --root .autolab-runs/manual-wsl-smoke
pixi run apply-wsl-ssh
```

## 3. Open the Console

Open `http://localhost:8000/` in a browser. The Console is a sidebar-nav
single-page app. The left sidebar has five sections:

- **Campaigns** — list and inspect goal-directed runs; create new ones.
- **Library** — Resources, Capabilities, and Workflows registered against
  this Lab.
- **Ledger** — queryable feed of every Record with SHA-256 checksums.
- **Setup → Assistant** — Claude-driven onboarding: describe your lab in
  plain language and review the proposed resources and operations.
- **Settings** — Lab metadata and connection status.

The top bar shows breadcrumbs and a WebSocket connection badge. A yellow
`claude: offline stub` badge means no `ANTHROPIC_API_KEY` is set; the
designer and Planner policy will return scripted responses.

If you apply a pack while the UI is already open, the Console should refresh
automatically from websocket events. If you rebuilt the frontend bundle itself,
hard-refresh the browser once.

## 4. Run a campaign

From **Campaigns**, click **+ New campaign**. A slide-over opens with a
free-text field — paste a sentence like *"Maximise the score of the demo
quadratic tool; stop at score ≥ 0.9"* and click **Design**. Claude (or
the offline stub) proposes a draft Campaign. Review it, then click
**Approve & submit**.

Navigate into the new campaign to see the **Resource lanes** (Gantt view
of Operations filling resource slots), the **Plan tree** (Campaign →
Operations), and a **Ledger feed** streaming records with their SHA-256
checksums as steps complete.

## 5. Manual smoke test

Before applying `wsl_ssh_demo`, make sure the SSH alias works from the same
machine that will run the Lab:

```powershell
ssh wsl2 echo ok
```

Then verify the running Lab after `pixi run apply-wsl-ssh`:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/debug/bootstrap | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8000/status | ConvertTo-Json -Depth 8
```

Expected backend state:

- `/debug/bootstrap` reports `bootstrap_mode: "wsl_ssh_demo"` and `bootstrap_error: null`
- `/status.resources` contains `wsl`
- `/status.tools` contains `add_two` and `cube`
- `/status.workflows` contains `add_two_then_cube`
- `/status.planners_available` contains `wsl_ssh_add_cube_optuna`

Expected UI state:

- `Library -> Resources` shows `wsl`
- `Library -> Capabilities` shows `add_two` and `cube`
- `Library -> Workflows` shows `add_two_then_cube`
- `Campaigns -> New campaign` shows planner `wsl_ssh_add_cube_optuna`

If the backend looks correct but the browser still looks stale, reload the
page once before debugging further.

## 6. Verify replayability

```bash
curl http://localhost:8000/verify
```

Every record's checksum recomputes live from SQLite + JSONL — a clean
response is the integrity proof.

## Where to next

- [Add a Resource](01-adding-a-resource.md) — register an instrument.
- [Add an Operation](02-adding-an-operation.md) — register a new capability.
- [Design a Campaign from free text](03-free-text-campaign-design.md) — the
  two-click launcher behind the Campaign Designer panel.
- [Architecture overview](../architecture/overview.md) — how the
  service, scheduler, Claude agents, and Ledger fit together.
