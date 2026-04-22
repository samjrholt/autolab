# frontend — autolab Campaign Console

A Vite + React frontend for the autolab Console. The source of truth now lives here; production assets are built into `src/autolab/server/static/` and served by the FastAPI app.

## Direction

The Console is no longer treated like an internal science dashboard. The current implementation biases toward:

- **Editorial luxury** — serif-led headlines, warm metallic accents, deliberate whitespace.
- **Futurist product feel** — glass surfaces, motion in the resource lanes, live signal spotlighting.
- **Progressive disclosure** — orchestration, plan mutation, campaign design, intervention, and ledger inspection without putting every control on the main canvas at once.

## Current surfaces

- **Hero stage** — active campaign framing and high-level lab state.
- **Resource motion** — the shared-resource lanes remain visible because they are a core demo beat.
- **Adaptive plan** — live campaign and experiment progression.
- **Signal spotlight** — latest completed result promoted into a visual anchor.
- **Intent launch** — free-text campaign design and approval.
- **Intervention + ledger** — secondary, but still accessible and provenance-visible.

## Tooling

The frontend is managed through pixi from the repo root:

- `pixi run frontend-install`
- `pixi run frontend-dev` — Vite dev server with API + WebSocket proxy to `http://localhost:8000`
- `pixi run frontend-build` — emits the production bundle into `src/autolab/server/static/`

If you prefer to work directly inside `frontend/`, `npm install`, `npm run dev`, and `npm run build` still work. The Python server continues to serve the already-built bundle.
