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

If the server is already running, you can also apply a bootstrap pack at
runtime instead of restarting:

```bash
curl -X POST http://127.0.0.1:8000/bootstraps/apply \
  -H "Content-Type: application/json" \
  -d '{"mode":"wsl_ssh_demo"}'
```

Or, using the repo tasks:

```bash
pixi run serve-clean
pixi run apply-bootstrap -- wsl_ssh_demo
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

## 5. Verify replayability

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
