# Visual Shell Redesign — Anthropic-Style Navigation

**Status:** Design, pending implementation plan
**Date:** 2026-04-22
**Subsystem:** 1 of 6 (shell first; onboarding, remote execution, real mammos, Playwright coverage, equipment connectors to follow)

## Context

The current frontend is tab-based (`TabNav.jsx`, `Shell.jsx`) with slide-overs for secondary actions. The user wants to move toward the Anthropic console aesthetic (dark, sidebar-driven, card/table landing pages, workspace-scoped resources) while keeping the CLAUDE.md demo commitments intact — specifically the Gantt-lane + plan-tree + physics-cards Campaign detail view and the `react()`-visible reasoning stream.

This spec covers **only the navigation shell and page structures** — the outer chrome of the product. It does not cover the onboarding wizard, the remote execution layer, the mammos integration, or Playwright coverage. Those are separate specs, and the shell is designed to host them without re-litigation.

## Goals

1. Give the product a recognisably Anthropic-console shell: dark theme, left sidebar, workspace (Lab) scoping, top-right primary CTAs on list pages.
2. Keep CLAUDE.md's locked Campaign detail invariant (Gantt lanes + plan tree + physics cards) intact, and add a pinned right-rail reasoning stream so `react()` cause-and-effect is visible in one frame.
3. Scale to a populated lab (50+ campaigns, dozens of workflows/tools) without redesign — table-style list pages, not card grids.
4. Surface **Ledger** as a top-level sidebar item. It is the product's moat; it does not get hidden inside a detail view.
5. Leave room for the onboarding wizard (subsystem 3) and remote-host UX (subsystem 2) to plug in without shell changes.

## Non-Goals

- First-run / onboarding flow. The shell provides an empty-state hook; subsystem 3 fills it in.
- Real WSL/SSH connection handling. Resources page shape only.
- Real mammos tools. Tools page shape only.
- Playwright coverage. Spec'd in subsystem 6; shell must be stable enough to test but the tests themselves are elsewhere.
- Equipment connector implementation. Interface stub only.

## Navigation Structure

**Sidebar (top to bottom):**

```
LAB
◆ default  ▾                     ← Lab selector (single lab for now; dropdown for forward compatibility)

Campaigns                         ← primary surface, user's landing page
Library                           ← expandable header group
  · Workflows
  · Resources
  · Tools
  · Agents                        ← Planner + PolicyProvider configurations
Ledger                            ← top-level; honors "ledger is the moat"

WORKSPACE
Settings                          ← API keys, Setup Assistant entry, lab-level config
```

- Library is expandable; its children are peers in the sidebar, not a separate Library landing page.
- The Lab selector is a dropdown in shape but functionally a display of the current Lab's name + status indicator. Multi-lab is out of scope this week; the dropdown exists so the layout doesn't shift when we add it.
- The sidebar collapses to an icon-only rail on narrow viewports. Keyboard nav: `g c` → Campaigns, `g l` → Ledger, `g s` → Settings (consistent with Anthropic's conventions).

**Top bar (horizontal, above main content):**

- Breadcrumbs on the left (`Campaigns / Find Hc ≥ 800 hard magnet`).
- Connection / lab-status pill on the right (`● live` or `● disconnected`).
- User avatar menu far right (profile, help, log out).

## Theme

Dark-only. Backgrounds: `#0f0f0f` canvas, `#141414` panels, `#1a1a1a` cards, `#262626` borders. Accent: `#c96342` (Anthropic terracotta) for primary CTAs, active-tab underlines, and in-progress pills. Status colours: `#7fd67f` running/ok, `#888` neutral/completed, `#d66` failed. Typography: system stack (`-apple-system, system-ui, sans-serif`); 11–14 px in chrome, 16 px titles.

## List Page Pattern (Campaigns, Workflows, Resources, Tools, Agents)

Table-style, scientist-native, sortable. Shared shell across all five list pages:

- Page header: page title (left), primary CTA (`+ New campaign` / `+ Register resource` / `+ Import tool` / …) in top-right (terracotta).
- Search / filter input below the header.
- Table: 4–6 columns per page, status column uses coloured dot + label, rightmost column reserved for row hover actions (⋯ menu: edit, duplicate, delete).
- Row click → detail page.
- Empty state: centred message with primary CTA. On the Campaigns page specifically, the empty state's CTA is *"Start your first campaign"* and routes to the onboarding wizard (defined in subsystem 3 spec; for now the shell shows the CTA and routes to a placeholder).

**Campaigns table columns:** Goal · Status · Ops (done/total) · Started · Planner · ⋯
**Workflows table columns:** Name · Steps · Last run · Used by · ⋯
**Resources table columns:** Name · Kind · Capabilities · In use · ⋯
**Tools table columns:** Capability · Module · Declared · ⋯
**Agents table columns:** Name · Planner type · Policy provider · Default for · ⋯

## Campaign Detail View

The hero of the demo. Four tabs inside the detail page, Plan is the default:

- **Plan** (default) — the three-zone layout CLAUDE.md locks, plus a right rail. The page is a two-column grid: **left column ≈ two-thirds** width, **right column ≈ one-third**.
  - Left column, row 1 (side-by-side at ≥ 1200 px, stacked below): **Resource lanes (Gantt)** on the left — one lane per registered Resource instance, Operations as pills, time flows left-to-right, live WebSocket updates — and **Plan tree** on the right — Campaign → Experiments → Operations, pill status mirrors the Gantt.
  - Left column, row 2: **Physics cards** — one card per live-renderable artefact (structure viewer, Ms(T) curve, hysteresis loop, PXRD). Cards appear when the relevant Operation completes and persist thereafter.
  - Right column, full height: **Reasoning rail** — pinned, always visible at ≥ 1024 px, chronological stream of agent messages, vision claims with confidence, `react()` decisions (Action + reason). This is *not* a tab and *cannot* be dismissed during the Plan view at desktop widths; it collapses to a toggle button below 1024 px. Beat 2 of the demo (vision → Claim Record → `react()` → scheduler reshuffle) plays out as a single readable frame because of this.
- **Ledger** — records table filtered to this campaign, same shape as the top-level Ledger page.
- **Report** — the auto-generated report (renders progressively as the campaign runs; complete and exportable as PDF when the campaign ends).
- **Settings** — campaign-level config: acceptance criteria editor (dict-of-rules per CLAUDE.md §locked-decisions), budget, planner + policy-provider selection, human-intervention controls, stop button.

All four tabs read from the same WebSocket event stream; they are different projections of the same ledger state.

## Top-Level Ledger Page

Table of records across all campaigns, newest first. Columns: Time · Campaign · Operation · Status · Module · Hash (truncated) · ⋯. Filters: campaign, operation capability, status, date range. Row click → record detail (JSON viewer + linked artefacts + vision-rendered PNG if present + parent/child record navigation).

## Settings Page

Sections, all in one scrollable page with a left sub-nav:

- **Lab** — name, description, base directory. Read-only for now; multi-lab is v2.
- **API keys** — Anthropic API key (only; we are Claude-native this week per CLAUDE.md).
- **Setup Assistant** — the "Describe your lab" entry point (subsystem 3 lives here).
- **Integrations** — WSL / SSH host connections and credentials (subsystem 2 lives here).
- **Provenance** — ledger file paths, replay controls, export.
- **About** — version, build, links to docs.

## Components and Isolation

| Unit | Purpose | Depends on |
|---|---|---|
| `AppShell` | Full-page chrome: sidebar + top bar + outlet | router only |
| `Sidebar` | Nav tree, lab selector, expandable Library group | router only |
| `TopBar` | Breadcrumbs, lab status, user menu | lab-status hook, auth hook |
| `ListPage` | Generic list-page shell: header + search + table slot + empty-state slot | — |
| `CampaignDetail` | Tabs + routing between Plan/Ledger/Report/Settings | campaign-store hook |
| `PlanTab` | The three-zone + rail hero layout | event-stream hook |
| `ResourceLanes` | Gantt-lane renderer | event-stream hook |
| `PlanTree` | Tree renderer | event-stream hook |
| `PhysicsCards` | Artefact card grid | event-stream hook |
| `ReasoningRail` | Pinned stream renderer | event-stream hook |
| `LedgerTable` | Shared between top-level Ledger page and Campaign→Ledger tab | ledger-query hook |
| `RecordDetail` | JSON + artefact + parent/child viewer | ledger-query hook |

Each unit consumes a small, named hook. `event-stream` subscribes to `WS /stream`; `ledger-query` wraps `GET /ledger`. No component reaches directly into another's internals. Existing components that fit this model (`SlideOver`, `StatusIndicator`, `MetricCard`, `KeyValue`) are reused; ones that don't (`TabNav` as currently implemented, `Overview`) are replaced or absorbed into `AppShell` / `ListPage`.

## Data / Event Flow

One WebSocket connection at the `AppShell` level, multiplexed via a pub/sub hook (`useEventStream(channel)`). Channels: `records`, `plan-tree`, `agent-messages`, `resource-state`, `claims`. The Plan tab, Reasoning rail, Ledger table, and physics cards all subscribe. REST (`GET /ledger`, `POST /campaigns`, …) remains for point queries and mutations.

## Error Handling

- Connection lost → top-bar pill flips red (`● disconnected`); a non-blocking banner offers retry. Live views freeze their last state rather than clearing.
- Failed operations appear as red pills in the Gantt and red-dot rows in the Ledger. Per CLAUDE.md §invariants, failures are records, not exceptions.
- Empty data → every list page has an explicit empty state with a guiding CTA; empty Campaigns routes to onboarding.

## Testing

Component-level tests live with components (Vitest). The full-flow Playwright suite is spec'd in subsystem 6. For this subsystem, a smoke test updates: "can navigate to every top-level page and see a valid empty state or populated table."

## Rollout / Migration

- Keep the current `App.jsx` reachable at `/legacy` during the hackathon window in case we need a fallback; delete after demo.
- Existing slide-over components (`NewCampaignSlideOver`, `InterventionSlideOver`, `EscalationsSlideOver`) are ported into the new shell as-is; they are triggered from the new CTAs / row actions.
- The existing `Provenance.jsx` is retired; its job is split between the top-level Ledger page and the Campaign→Ledger tab.

## Open Questions Deferred to Later Subsystems

- How the empty Campaigns CTA routes into the onboarding wizard — subsystem 3.
- What the Resources page actually shows for a WSL host (live ping? free RAM?) — subsystem 2.
- What the Tools page shows for a `mammos-*` capability (version? last-known-good run?) — subsystem 4.
- What the Playwright full-flow test asserts on — subsystem 6.
