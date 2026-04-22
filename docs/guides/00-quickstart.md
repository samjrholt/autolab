# Quickstart

Boot the Lab, open the Console, watch a demo campaign run — five minutes.

## 1. Install

The repo is managed with [pixi](https://pixi.sh) — one command installs the
Python 3.12 environment and the editable `autolab` package:

```bash
pixi install
```

No Node tooling is required. The Console is a single HTML file the server
renders straight from `src/autolab/server/static/index.html`; it pulls
React and Tailwind from public CDNs. You can swap in a Vite build later
without changing the server contract.

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
set `AUTOLAB_BOOTSTRAP=my_package.my_module:my_bootstrap_fn`.

## 3. Open the Console

Open `http://localhost:8000/` in a browser. You should see four rows of
panels — **Gantt + Plan tree**, **Ledger feed + Event stream**,
**Campaigns + Designer + Intervention**, **Add resource + Duration
estimates**.

The top-right badges show Claude's status (*configured* if
`ANTHROPIC_API_KEY` is set, otherwise *offline stub*) and the live WS
connection state.

## 4. Run a campaign

From the Console: paste a sentence into the **Design campaign from free
text** box and click *Design campaign*. Claude (or the offline stub)
returns a draft `Campaign`. Review it, then click *Approve & submit*.

Watch the **Resources → live Gantt** panel fill with `demo_quadratic`
pills and the **Ledger feed** stream records with their SHA-256
checksums.

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
