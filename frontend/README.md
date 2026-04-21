# frontend — autolab Campaign Console

A React + Vite + Tailwind single-page app that consumes the Lab's REST + WebSocket API and renders the two-panel console.

## Panels (locked — see CLAUDE.md)

- **Left — resource-lane Gantt.** One horizontal lane per Resource instance. Operations are pills that fill their lane while running. Colour-coded by status (`pending`, `running`, `completed`, `failed`, `proposed`).
- **Right — plan tree.** Campaign → Experiments → Operations. Pill status matches the Gantt. Unchosen proposed Operations remain in the tree as breadcrumbs.
- **Below — live physics cards.** Appear when a relevant Operation completes: rendered hysteresis loops, PXRD patterns, 3-D structure viewers, streaming Hc estimates.
- **Intervention box.** Free-text input; each submission `POST`s to `/campaigns/{id}/intervene` and lands as a hashed Record.
- **Ledger panel.** Append-only feed of Records with checksum + status badges. Read-only.

## Status

Not scaffolded yet. Target: hackathon day-2 / day-3 window.

## Tooling

This directory is **outside pixi's Python environment**. It has its own `package.json` and is managed by plain npm / pnpm. The Python Lab serves the built bundle from `src/autolab/server/static/` in production; in development the Vite dev server proxies WebSocket + REST traffic to `:8000`.
