## Context

The dashboard currently treats Conversions as a single flat destination. In [horizon-dashboard/src/App.tsx](horizon-dashboard/src/App.tsx), the Conversions section resolves to one `/conversions` route, and in [horizon-dashboard/src/components/common/Sidebar.tsx](horizon-dashboard/src/components/common/Sidebar.tsx) it appears as one sidebar item rather than a section with child pages.

That single page is doing two jobs at once:
- an operational uploads workbench built around the current estimate-per-row pipeline table and action buttons
- a partial analytics surface for conversion upload health and diagnostics

At the same time, the system already stores multiple feedback families that are not given dedicated display surfaces today, including:
- analytics runs and slice statuses in `gads_analytics_runs`
- client upload health in `gads_client_upload_health`
- action upload health in `gads_action_upload_health`
- attribution summaries in `vw_gads_attribution_summary`
- configuration drift snapshots in `gads_action_config_snapshots`
- row-level upload state and errors in local upload records and the uploads workbench

The requested change is not a new data-collection pipeline. It is an information architecture change that creates a proper display window for each available feedback type, puts all analytics into a new Analytics child page, and moves the current conversions table to a dedicated Uploads child page under the Conversions sidebar section.

## Goals / Non-Goals

**Goals:**
- Split the Conversions section into explicit child pages for Analytics and Uploads.
- Make Analytics the default landing destination for `/conversions`.
- Render each available conversion upload feedback family in its own dashboard panel or drill-down surface.
- Preserve the current uploads workbench behavior while moving it to the Uploads child page.
- Keep the Conversions sidebar state coherent across analytics, uploads, and secondary nested routes.

**Non-Goals:**
- Adding new Google Ads queries or new backend collection pipelines just to support the page split.
- Replacing the existing upload workbench interactions with a brand-new operational workflow.
- Persisting new categories of historical diagnostic data that are not already stored, such as GCLID verification history.
- Moving upload analytics ownership to Marketing or Admin instead of keeping it inside the Conversions section.

## Decisions

### D1: Split the route tree into a Conversions section with explicit child destinations

The dashboard will treat Conversions as a section rather than a single page:
- `/conversions` resolves to `/conversions/analytics`
- `/conversions/analytics` becomes the analytics landing page
- `/conversions/uploads` becomes the operational uploads workbench
- `/conversions/config` remains a secondary nested route but not a primary sidebar child entry

This gives the section a stable default landing page while preserving existing nested configuration behavior.

**Alternative considered:** keep `/conversions` as the uploads page and add analytics somewhere else. Rejected because the request explicitly calls for a collapsible Conversions section with Analytics and Uploads beneath it.

### D2: The sidebar parent owns Conversions section state

The Sidebar will render Conversions as a collapsible parent item with two visible child destinations: Analytics and Uploads. The parent remains active for any route under `/conversions`, including secondary routes such as configuration.

When the sidebar is collapsed, activating the Conversions control must still expose access to both child destinations rather than reducing the section back to a single flat link.

**Alternative considered:** expose Analytics, Uploads, and Config as three sibling child items. Rejected because the requested information architecture calls for Analytics and Uploads as the section's primary pages, while configuration remains secondary.

### D3: Analytics renders feedback by panel family, not as one monolithic card

The Analytics page will group feedback into distinct panel families that map to the grain of the underlying data:
- **System feedback**: latest analytics run, trigger, started/finished times, slice statuses, row counts, and latest failures
- **Upload health**: client-level health and action-level health, including status, alert summaries, daily summaries, and freshness
- **Attribution and drift**: attribution rate, Google conversions, action alive state, and configuration drift state
- **Upload outcomes**: aggregate counts of uploaded, pending, skipped, and retrying rows derived from local upload records
- **Diagnostic detail**: drill-down views for raw alerts, raw daily summaries, and stored error text

This keeps each feedback type in its own display window instead of collapsing unlike data into a single analytics card.

**Alternative considered:** reuse one dense card on the current page or flatten everything into one table. Rejected because the current problem is lack of dedicated rendering for individual feedback families.

### D4: Reuse existing telemetry sources before adding backend work

The first version of Analytics will be built from already collected data:
- `gads_analytics_runs` for run and slice diagnostics
- `gads_client_upload_health` for platform and client health
- `gads_action_upload_health` for per-action upload health detail
- `vw_gads_attribution_summary` for attribution and action-alive metrics
- `gads_action_config_snapshots` for drift and latest tracked settings
- local upload records for aggregate upload outcomes

No new data model is required to satisfy the display-window goal. The change is primarily route, layout, and panel composition work.

**Alternative considered:** create new aggregation tables or a new backend API for the analytics page. Rejected because the required signals already exist and the proposal is about surfacing them cleanly.

### D5: Uploads remains the row-level operational workbench

The current ConversionsPage behavior will move to the Uploads route with minimal behavior change. It remains the place for:
- scan and upload actions
- filters and grouped table behavior
- row expansion and stage-level detail
- row-level errors and retry visibility
- GCLID verification actions

This avoids a risky redesign and preserves the existing operator workflow while clarifying that Uploads is for row-level work, not analytics summary.

**Alternative considered:** split the current uploads workbench into multiple new operational pages. Rejected because the request is to relocate the current table, not redesign the entire workflow.

### D6: Analytics shows all stored feedback but only summarizes non-persisted diagnostics

Some diagnostics are stored and can be rendered directly, while others remain on-demand row actions. The Analytics page will fully render stored feedback families and summarize only what exists at an aggregate level. For diagnostics that are not persisted historically, such as GCLID verification results, Analytics will provide a clear path to the Uploads page rather than inventing aggregate history.

**Alternative considered:** persist new historical verification data as part of this change. Rejected because it expands the change from page architecture into backend behavior and storage.

## Risks / Trade-offs

- [Analytics density becomes noisy or overwhelming] -> Group panels by feedback family and default to summary-first views with expandable detail.
- [Raw alerts and daily summaries are too low-level for the main page] -> Render human-readable summaries first and keep raw payload inspection behind drill-down surfaces.
- [Operators confuse run freshness with business health] -> Separate system feedback panels from attribution and action-health panels.
- [The current GCLID verification response contract is inconsistent between frontend and backend] -> Fix the response shape during implementation before relying on that diagnostic surface.
- [Section split creates duplicate concepts between Analytics and Uploads] -> Keep Analytics summary-first and Uploads row-first, with each page linking to the other when detail crosses the boundary.

## Migration Plan

1. Update routing so `/conversions` resolves to `/conversions/analytics`, add `/conversions/uploads`, and keep secondary nested routes working.
2. Refactor the sidebar into a collapsible Conversions parent with Analytics and Uploads children and parent-level active state.
3. Move the current ConversionsPage behavior to the Uploads destination with updated page title, route, and section copy.
4. Build the Analytics page from existing Supabase-backed feedback sources and group the page into panel families and drill-down surfaces.
5. Add links between Analytics and Uploads so operators can move from summary to row-level investigation.
6. Rollback by restoring the single `/conversions` uploads route and reverting the sidebar to a flat Conversions item if the split causes regressions.

## Open Questions

- Should the Analytics page render raw alerts and daily summaries inline inside expandable cards, or open them in a dedicated side panel or drawer?
- Should Uploads preserve the existing component name internally for incremental refactoring, or be renamed during the move to make the page role explicit in code?