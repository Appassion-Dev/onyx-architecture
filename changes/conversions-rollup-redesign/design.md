## Context

The Conversions page (`src/components/conversions/`) renders a Month → Week → SourceGroup → Row hierarchy built from `vw_conversion_candidates`. Today the page is single-stage: a `conversionMode` of `pre-discovery | booking | qualified | converted` is selected and every rollup at every level (`MonthCard`, `WeekBlock`, `SourceGroupBlock`) shows the same five-cell rail computed by `computeStats(rows, mode)` — `Rows | GCLID | Uploaded | Sync | Value`. Per-estimate rows in `PipelineRowItem` add a heavy card on the right containing the active stage's `PhaseCell` and a framed value.

A parallel page — Upload Report (`src/components/pages/UploadReportPage.tsx`, hooks in `src/lib/uploadReport.ts`) — reads `vw_gads_upload_reconciliation_daily` and tracks four numbers per `event_key` (`booking_lead | qualified_lead | converted_lead`) per day:
- `local_uploaded_count` (rows we sent)
- `gclid_count` (rows we sent with a GCLID)
- `google_successful_count` (rows Google accepted)
- `google_failed_count` (rows Google rejected)

The current Conversions page rollup is unaware of `google_successful_count` / `google_failed_count` — so users have no in-context signal for Google-side acceptance, which is the metric that actually determines Smart-Bidding signal quality.

In parallel, the per-row upload card duplicates an affordance that is now available at every rollup level (the bulk-upload buttons on Month / Week headers) and from inside the expanded detail panel, so it adds visual weight without adding capability.

Other in-progress changes overlap this work:
- `conversion-attribution-overhaul` (in-progress, 0/38 tasks) restructures GCLID resolution, qualified/converted gates, and the per-stage GCLID badge logic.
- `gads-conversion-error-dispositions` (in-progress, 83/95) introduces the disposition workflow used by the expanded StageDetail panel.
- `gads-upload-fix-and-refactor` (in-progress, 42/47) is the upload-function refactor that defines the payload-builder classification this change reuses for the Method column.

This change is scoped to the **rollup rail** and **per-estimate row layout** on the existing Conversions page. It does not change the upload function, the discovery gates, or the disposition workflow.

## Goals / Non-Goals

**Goals:**
- One rollup rail definition that works at Month, Week, and SourceGroup levels.
- One column model that works in both single-stage and `all` modes — `all` mode renders three sub-values per column without introducing a separate component tree.
- Acceptance metric is sourced from `vw_gads_upload_reconciliation_daily` — the same view that powers the Upload Report page — so the two pages agree by construction.
- Method classification logic is shared with `supabase/functions/google-ads-conversion-upload/payload-builder.ts` so the dashboard cannot drift from what the upload function actually sends.
- Bulk upload is reachable from exactly one place: the top-of-page Upload button in `ConversionsHeroHeader`, which uploads pending rows across the currently filtered hierarchy. Per-row upload (single-estimate retry) lives inside the expanded StageDetail panel. The per-Week and per-Month rollup Upload buttons described in the existing `bulk-upload-scoped` spec are removed.
- Estimate label is a one-click link into HCP and customer identity fields are visible inline in the detail panel.

**Non-Goals:**
- Re-architecting the upload function, payload builder, or discovery gates. The Method classifier in the dashboard is a *reader* of the same inputs the upload function uses, not a re-implementation.
- Replacing the WorkbenchTabs (`Pipeline | Needs Attention | Batches | Configure`) — only the inner `STEP_TABS` mode toggle is extended.
- Touching the `pre-discovery` mode's specialized layout (simplified row, no value cell). It remains as-is. The new `all` mode does NOT include pre-discovery; pre-discovery rows have no stage to aggregate.
- A new "All Stages" page distinct from the existing Conversions page.
- Live polling for acceptance: acceptance is fetched once per page load (same TTL as `useUploadReport`) and reflects the daily reconciliation cadence.

## Decisions

### Decision 1: `all` is a mode, not a separate page

**What**: Add `'all'` to the `ConversionMode` union and `STEP_TABS`. The internal mode value is `'all'`; the user-facing tab label is `All Conv` (short for "All Conversions" — disambiguates from generic "All" and signals that the tab covers only the three conversion stages, not pre-discovery). The mode tab strip becomes a 5-segment control in this order: `Pre-Discovery · All Conv · Booking · Qualified · Converted` — `All Conv` sits in second position, immediately after `Pre-Discovery` and before the three single-stage tabs. `'all'` is the default landing mode (replaces today's `'qualified'`).

**Why**: We already have a rich filtering / hierarchy / bulk-upload infrastructure keyed on `conversionMode`. Adding a fifth mode keeps the page's mental model intact and lets every existing piece (filters, expand state, fiscal grouping) reuse its current wiring. The only widening is `MODE_CONFIG['all']`, a different hierarchy-builder branch (see Decision 1b), and a small amount of conditional rendering in the rollup cells.

**Alternatives considered**:
- *Make `all` the only mode and remove the others.* Rejected — single-stage focus is useful for triage; reviewers asked for both views.
- *New `/conversions/all` route.* Rejected — duplicates header / filter UI without earning anything.

### Decision 1b: In `all` mode the hierarchy unit is `(estimate, stage)`, dated per-stage

**What**: In `all` mode, the leaf entity flowing through `buildHierarchy` is NOT a single `PipelineRow` per estimate but a `StageEvent = { row: PipelineRow, stage: 'booking' | 'qualified' | 'converted', eventDate: ISOString }`. For each `PipelineRow` we emit up to three `StageEvent`s — one for each stage whose `{stage}_status` is non-null — each carrying the corresponding `*_datetime`. The hierarchy buckets `StageEvent`s by `eventDate` into Month → Week. The Source-group bucketing still uses the existing channel classifier on the underlying row. Rollup aggregations (Stage / Method / Push / Value) compute over the `StageEvent`s in the bucket. The body renders one visible row per `StageEvent`, decorated with a small `Booked` / `Qualified` / `Won` stage badge. Acceptance still keys off `event_key` matching the stage, so the Acceptance triple still aligns naturally.

In single-stage modes (`booking` / `qualified` / `converted` / `pre-discovery`), the hierarchy unit remains one `PipelineRow` per estimate dated by the mode's existing date field — unchanged from today.

**Why**: Per-stage dates is the right answer because the rollup question is "what happened this week" and the answer is per-stage events on their own timeline, not "what estimates were created this week" projected through their downstream stages. The reference dashboard's archive view works the same way: flipping stage tabs re-dates the same rows by that stage's timestamp. Modeling the leaf as `(estimate, stage)` makes rollup totals = visible-row count, removes the mismatch between "12 visible rows but 27 events counted in the rail", and lets a single estimate appear in the weeks its events actually fell into (booked in W1, qualified in W3, converted in W7).

**Alternatives considered**:
- *Group by `estimate_created_at` in `all` mode.* (Original proposal.) Rejected because the rollup numbers then describe a cohort ("estimates created this week, here's their lifetime stage events") instead of an interval ("here's the events that occurred this week"), which makes Acceptance non-comparable to the Upload Report.
- *Keep body rows 1-per-estimate, but compute the rollup over long-format events.* Rejected — rollup totals would not equal visible-row counts in `all` mode, which is exactly the source of confusion this change is supposed to remove.
- *Group by `estimate_created_at` for the body, per-stage dates for the rollup.* Same problem as above plus inconsistency between body and headers.

**Consequences for downstream components**:
- `PipelineRowItem` in `all` mode receives a `StageEvent` rather than a bare row. The row shows that stage's date + status + value, plus a stage badge.
- **Expansion is single-stage scoped in `all` mode.** When a `StageEvent` row is expanded, the detail panel renders the CustomerInfoBlock plus ONLY the StageDetail for that row's own stage (e.g. a `Qualified` row shows only the Qualified Lead section). The other two stages' StageDetails are NOT rendered — not as full sections, not as collapsed summaries. Each `StageEvent` row is treated as a fully independent record with no awareness of its sibling appearances.
- The per-row Value column in `all` mode is therefore **single-valued** (it shows the value of *this* stage event — `—` for booking events, `qualified_value` for qualified events, `converted_value` for converted events). The earlier tri-cell-at-row-level proposal is dropped. Tri-cells continue to be used in the rollup rail headers, not on rows.
- **No grouping by underlying estimate.** Rows in `all` mode are independent first-class records. There is no parent wrapper, no `estimate_id` de-duplication, no aggregation header collapsing sibling events. The three rows for a single estimate that progressed through all stages may end up in entirely different Month / Week / SourceGroup buckets depending on where each `*_datetime` lands.
- Rollup totals count `StageEvent`s, not unique `estimate_id` values. A single estimate with three stages contributes `+1` to each of the three stage columns of whichever rollup buckets contain its events — there is no de-duplication.
- Source-group classification reads the underlying row (channel doesn't depend on stage), so a single estimate that produces three `StageEvent`s lands in the same source-group three times, which is correct.

### Decision 2: Single column model with per-stage sub-cells in `all` mode

**What**: One declarative column definition list — `[Stage, Method, Push, Acceptance, Value]` — drives Month / Week / SourceGroup rendering. Each column receives either one value (single-stage mode) or a `{ booking, qualified, converted }` triple (`all` mode). A single `RollupMetricCell` variant handles both by accepting a tuple and rendering one or three sub-spans behind a shared label.

**Why**: Two components (single-stage rail + all-mode rail) drift; one rail with two render shapes does not. It also keeps Month / Week / SourceGroup using the same `ROLLUP_METRIC_RAIL_CLASS` grid so the columns line up visually across hierarchy levels.

**Alternatives considered**:
- *Three separate cards in `all` mode, one per stage.* Rejected — wastes horizontal space, breaks vertical alignment with single-stage rails, and forces three copies of every label.
- *Tabbed inside the rollup row.* Rejected — interaction cost on every row.

### Decision 3: Method classifier is computed client-side from per-stage GCLID + customer identifiers exposed on the candidates view

**What**: For each row at each stage, classify into:
- `with_gclid` — `{stage}_gclid IS NOT NULL` on the candidates view
- `user_data_only` — `{stage}_gclid IS NULL` AND (customer email present OR customer mobile present)
- `none` — neither

The candidates view (`vw_conversion_candidates`) must expose `customer_email` (or `customer_has_email` bool) and `customer_mobile` (or `customer_has_mobile` bool). The dashboard does not need the raw values for classification — booleans suffice — but the detail panel will use the raw values for the new customer-info block, so exposing the raw columns once is simpler than maintaining both.

**Why**: Mirrors `supabase/functions/google-ads-conversion-upload/payload-builder.ts` lines 44-54 exactly: GCLID OR identifiers from hashed email/phone, else skip. Computing client-side avoids round-tripping per page load and keeps the source of truth in one query.

**Alternatives considered**:
- *Server-side method column on the view.* Workable but couples the view to the classifier. Rejected — classifier rules will tighten when the upload function gets richer (e.g., adding hashed address). Better to keep the rule in one place per layer.
- *Three pre-computed counts per stage on the view.* Premature aggregation — loses the row-level granularity needed for filtering and detail panels.

### Decision 4: Acceptance comes from `vw_gads_upload_reconciliation_daily`, not from the candidates view

**What**: Add a hook `useReconciliationByPeriod(fromDate, toDate)` that fetches reconciliation rows scoped to the hierarchy's date span. Build a Month-key and Week-key index using the same `getWeekInfo` helper and `America/New_York` TZ that `useUploadReport` uses. The hook returns aggregates per `{ monthKey, weekKey, event_key }` so the rollup cells can look up Acceptance without recomputing it per render.

**Why**: This is the only metric that does NOT come from `vw_conversion_candidates`. The reconciliation view is the authoritative source for what Google accepted (sourced from the per-day reconciliation job). Reusing the same view ensures the Acceptance number on a Month rollup equals the Upload Report's totals for that month, full stop. Source-group level acceptance is NOT included because reconciliation has no source attribution.

**Alternatives considered**:
- *Compute acceptance from candidates by treating "status = uploaded AND error_message IS NULL" as accepted.* Rejected — that conflates "we got an OK from the API" with "Google attributed the click to a campaign," which is the actual question.
- *Materialize acceptance into the candidates view.* Costly join; the daily reconciliation view already does this work; reading from two views is fine.

### Decision 5: Push column reads existing per-stage fields, not the reconciliation view

**What**: Push counts come from `vw_conversion_candidates` per-stage columns:
- `total_sent` = rows where `{stage}_status IN ('uploaded')` OR `{stage}_upload_attempts > 0`
- `sent_no_error` = rows where `{stage}_status = 'uploaded'` AND `{stage}_error_message IS NULL`
- `sent_with_error` = rows where `{stage}_error_message IS NOT NULL` (or latest attempt is an error per disposition logic)

**Why**: Push describes *our* side of the wire (we tried to send, did Google's API return an error?), so the candidates view that records every attempt is the right source. Acceptance is *Google's* side (their reconciliation says yes/no the click matched). Keeping them sourced separately is what makes the gap between Push and Acceptance meaningful.

### Decision 6: The per-row PhaseCell is removed from the row layout, not from the codebase

**What**: `PipelineRowItem` no longer renders the right-side upload card. The `PhaseCell` component is preserved and still rendered inside the expanded `StageDetail` panel where it makes sense for retry workflows (per `phase-cell-upload` spec). The right-side framed value cell becomes an inline value at the row level.

**Why**: PhaseCell carries the disposition + countdown + dry-run logic that we need to keep working; deleting it would orphan the disposition work in `gads-conversion-error-dispositions`. Moving it inside the detail panel preserves the affordance for users who need it, while making the default row layout scan-friendly.

### Decision 6b: Bulk upload collapses to a single page-level button

**What**: The existing `bulk-upload-scoped` spec defines per-Week and per-Month Upload buttons. These SHALL be removed. The Conversions page exposes exactly one bulk-upload affordance — the existing Upload button in `ConversionsHeroHeader` — which uploads pending rows across the **currently filtered, visible hierarchy** (not all data on the page). The Dialog confirm modal + 5-second countdown toast flow already implemented by `useBulkUpload` is retained verbatim; only its origin point changes (one button instead of every rollup header). In `all` mode the batch spans booking + qualified + converted pending IDs and the dialog shows per-stage counts.

**Why**: The per-Week / per-Month buttons were aspirational — not currently in the rendered code, only in the spec — and adding them was rejected on review for two reasons: (a) they duplicate scoping that filters already provide (narrow by channel/campaign/mode then click upload = same result), (b) they add UI weight on rollup headers that the rest of this change is trying to make denser and quieter. Collapsing to one button reduces the number of upload origin points from "1 per visible month + 1 per visible week + 1 page-level" (potentially dozens) to exactly one.

**Alternatives considered**:
- *Keep the page-level button AND add per-Month buttons (but drop per-Week).* Rejected — partial removal still implies "the rollup row is something you can act on" which contradicts the read-only-rollup mental model this redesign is committing to.
- *Make every rollup row clickable to scope the top-of-page button.* Possible future ergonomic improvement, out of scope here.

**Consequences for downstream components**:
- `MonthCard`, `WeekBlock`, `SourceGroupBlock` render no upload control. Their job is purely informational rollup display.
- `ConversionsHeroHeader`'s existing Upload button keeps its current behavior; the underlying `useBulkUpload` hook gets a small extension to accept multi-stage targets for `all` mode.
- The `bulk-upload-scoped` capability's four existing requirements (week/month buttons, dialog modal, countdown toast, bucket scoping) are formally REMOVED in this change's delta spec and replaced with new requirements describing the same flow originating from the single page-level button.

### Decision 7: HCP link directly on the estimate label

**What**: `#{estimate_number}` becomes an `<a target="_blank" rel="noopener noreferrer" href="https://pro.housecallpro.com/app/estimates/{estimate_id}">` so clicking the visible label opens HCP. The chevron-toggle that currently expands the row remains on the rest of the button area; the link captures clicks only on the estimate label itself (stop-propagation on the link click so the row does not toggle).

**Why**: This is the existing convention in this codebase — `WeeklySalesBreakdownTable.tsx` line 132 does `https://pro.housecallpro.com/app/jobs/${row.job_id}` and `conversions-qualified-enrichment/spec.md` uses `https://pro.housecallpro.com/app/estimates/{option.id}` on the option icon. Keeping the URL shape consistent.

### Decision 8: Customer info block in the detail panel

**What**: Add a small `CustomerInfoBlock` rendered at the top of the expanded detail panel showing: customer name, email (mailto: link), mobile (tel: link), service address (one line). Sourced from the same customer fields newly exposed on `vw_conversion_candidates` (see Decision 3).

**Why**: Triage workflows currently bounce to HCP just to read the phone number. Surfacing it inline reduces context-switching. The customer name is already on the row, but the rest is hidden.

## Risks / Trade-offs

- **Risk**: View migration for `vw_conversion_candidates` may have cross-cutting impact on existing consumers. → *Mitigation*: additive only — we add columns, never remove. Existing consumers ignore the new columns.
- **Risk**: Method classifier diverges from `payload-builder.ts` over time. → *Mitigation*: a single Jest/Vitest test calls a shared classifier function with rows from a fixture and compares the bucket against a snapshot of what `payload-builder.ts` would produce (`gclid OR identifiers`).
- **Risk**: Acceptance fetch adds a second Supabase query on page load. → *Mitigation*: the reconciliation view is already cached by `useUploadReport`; we reuse the same React Query key namespace and TTL. One additional small request scoped by date range is acceptable.
- **Risk**: Per-row upload removal surprises power users who used the per-row PhaseCell as the primary entry point. → *Mitigation*: the affordance moves *into* the expanded row (one click further) and the rollup-level bulk button (still one click). Announce in release notes.
- **Trade-off**: The new five-column rail is denser than today's five-column rail (because Method and Push each contain three sub-values). Acceptable because (a) the labels collapse into a single header per column, (b) the SourceGroup level drops Acceptance which is the densest column.
- **Trade-off**: `all` mode loses the "show zero values" toggle's meaning (since Booking has no value, but Qualified/Converted do). The toggle SHALL be hidden in `all` mode like it already is in Pre-discovery/Booking.

## Migration Plan

1. Database: extend `vw_conversion_candidates` to expose `customer_email`, `customer_mobile`, `customer_address_*` columns (additive — no breaking change to existing consumers).
2. Frontend types: widen `ConversionMode` to include `'all'`. Update `MODE_CONFIG` with an `'all'` entry (`label: 'All Conv'`). Update `STEP_TABS` to insert the `'all'` tab in **second position** — after `pre-discovery`, before `booking` — with display label `All Conv`.
3. Frontend stats: replace `RollupStats` with a per-stage shape `{ booking, qualified, converted } where each is { stageCount, methodCounts, pushCounts, value }`. `computeStats(rows, mode)` returns the active-stage slice for single-stage modes and the full triple for `'all'` mode.
4. Frontend hook: add `useReconciliationByPeriod`. Reuse `getWeekInfo` and the `America/New_York` TZ from `lib/uploadReport.ts`. Returns an index `Map<periodKey, AcceptanceTriple>`.
5. Frontend hierarchy: `buildHierarchy` accepts `'all'` and operates over a `StageEvent[]` derived from the input rows (one to three events per row based on which `{stage}_status` columns are non-null), bucketing by per-stage `*_datetime`. Single-stage modes keep their existing 1-row-per-estimate behavior.
6. Frontend rail: rewrite `MonthCard` / `WeekBlock` / `SourceGroupBlock` to render the new 5-column rail; SourceGroupBlock omits the Acceptance column.
7. Frontend row: rewrite `PipelineRowItem` row layout — remove the upload-card right side; render the value inline; wrap the estimate label in an HCP link.
8. Frontend row detail: add `CustomerInfoBlock`; render at top of the expanded panel.
9. Tests: snapshot test for the new rail in both single-stage and `all` modes; classifier parity test; acceptance fetch test.
10. Default mode flip: `'qualified'` → `'all'` after the rest lands.

**Rollback**: revert in two steps — (a) flip default mode back to `'qualified'` and hide the `'all'` tab via a feature flag, (b) revert the row-layout commit. Both are independent of the data-layer migration which is purely additive.

## Open Questions

- **Q1**: Does `vw_conversion_candidates` already expose `customer_email` / `customer_mobile`? Today the dashboard uses `customer_name` from the view but the underlying join may not include contact fields. **Action**: confirm by reading the view definition before authoring tasks.
- **Q2**: Should "sent with error" count include rows whose latest attempt errored but where a later attempt then succeeded? Proposed default: NO — count current state only (latest known status). Surface "ever failed" separately if asked.
- **Q3**: Acceptance percent — what color thresholds? Proposed: green ≥95%, amber 80–94, red <80, mirroring the existing `SyncBadge`. Reuse `SyncBadge`'s color logic.
- **Q4**: **Resolved.** In `all` mode the single page-level Upload button pushes pending rows across all three uploadable stages, with the confirm dialog grouping them by `conversion_type` (e.g. "5 booking, 3 qualified, 2 converted"). Requires a small extension to `useBulkUpload` to accept a multi-`conversion_type` target. Per-bucket Upload buttons on Month / Week / SourceGroup rollups are removed entirely (see Decision 6b).
- **Q5**: HCP estimate URL — confirmed pattern is `https://pro.housecallpro.com/app/estimates/{estimate_id}` where `{estimate_id}` is the HCP estimate id we already store. ✓
