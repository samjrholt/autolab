# Architecture

Concrete architecture docs that map 1:1 onto code. Populated as the framework is built.

Planned entries:

- `provenance.md` — Record schema, hashing, write-ahead / append-only / annotation semantics, `autolab replay` semantics.
- `scheduling.md` — ResourceManager, cross-experiment and cross-campaign interleaving, capability matching, visual vocabulary (resource-lane Gantt + plan tree).
- `tool-interface.md` — the capability-named Tool YAML spec, adapter contract, MCP gateway wiring, declaration-hash provenance.
- `react.md` — the `react()` Action vocabulary with concrete examples against [docs/design/scenarios.md](../design/scenarios.md).
- `server.md` — the FastAPI + WebSocket surface, event stream schema, state rehydration on restart.

Until these files exist, the spec lives in [CLAUDE.md](../../CLAUDE.md) and [docs/design/](../design/).
