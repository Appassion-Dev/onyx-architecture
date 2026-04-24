## Context

The Conversions page (`ConversionsPage.tsx`) queries `vw_conversion_candidates` — a view that pivots `gads_conversion_uploads` into per-estimate booking/qualified/converted stage columns and joins basic estimate, customer, and call-aggregate data. The 90-day window of data is loaded once into React Query and the month/week hierarchy is built client-side.

Three gaps to close:
1. **No filtering** — operators cannot slice the view by funnel step, traffic source, assignee, or campaign
2. **Missing attribution context** — GCLIDs from `booking_tags` (form submissions) and `callrail_leads` (calls) are not unified; campaign names are not surfaced
3. **Thin Qualified Lead detail** — no assignee, no HCP links on estimate options

The `vw_booking_estimates` view already solves the assignee join pattern (lateral on `estimates_settings → employees`). The Calls page already has the GCLID tooltip pattern.

## Goals / Non-Goals

**Goals:**
- Rebuild `vw_conversion_candidates` to add five new columns: `callrail_campaigns[]`, `all_gclids[]`, `assigned_employee_id`, `assigned_employee_name`, `first_touch_medium`
- Add a filter bar above the hierarchy with five dropdowns: Step, Source, Medium, Campaign, Assignee
- Add a `GCLID ×N` badge with tooltip to each estimate row
- Show assigned employee (colored badge) and HCP option links in the Qualified Lead detail

**Non-Goals:**
- Server-side filtering — all filtering is client-side on the already-loaded 90-day dataset
- Changing any of the three pipeline stage columns or upload logic
- Modifying the CallsPage or BookingTagsTable

## Decisions

### D1: Combined GCLIDs in the view, not the component

**Decision:** Compute `all_gclids` — a deduplicated array merging GCLIDs from `booking_tags` (key = 'gclid') and `callrail_leads.gclid` — in the SQL view using `UNNEST` + `ARRAY_AGG(DISTINCT ...)`.

**Rationale:** The component should not need to know about two sources. Deduplication in SQL is idempotent and keeps the component simple. The alternative (fetching both sources separately in the component) doubles round-trips and requires joining on the frontend.

**Alternative considered:** Fetch `booking_tags` and `callrail_leads` GCLIDs in separate sub-queries per expanded row. Rejected — adds latency on every expand and spreads attribution logic into the UI layer.

### D2: Client-side filtering via `useMemo`

**Decision:** All five filter dropdowns operate on the full in-memory `rows` array via `useMemo`. No query parameter changes, no refetch on filter change.

**Rationale:** The 90-day dataset is already in memory. Adding WHERE clauses to the Supabase query would require a refetch on each filter change and complicate the query key. Client-side filtering is instantaneous and matches the existing pattern for the week/month hierarchy.

**Limitation:** Large datasets (>5,000 rows) could make the `useMemo` expensive. At 90 days of estimates this is not a concern.

### D3: Assignee from `useEmployees()`, not the view, for color resolution

**Decision:** The view exposes `assigned_employee_id` and `assigned_employee_name` (text). The `EmployeeBadge` color is resolved client-side by looking up `assigned_employee_id` in the `useEmployees()` cache (`vw_employees_with_roles` → `color_hex`).

**Rationale:** The view already carries the name string for display. Color resolution doesn't belong in SQL — it's a UI concern. `useEmployees()` is cached globally (5-minute stale time) and is already used by multiple components.

**Alternative considered:** Join `color_hex` into the view directly. Rejected — unnecessary coupling between a conversion pipeline view and employee display metadata.

### D4: `first_touch_medium` computed in SQL

**Decision:** Compute a `first_touch_medium` column (`'form'` or `'call'`) in the view:
- If `is_booking_form = true` AND no calls → `'form'`
- If calls exist AND no booking form → `'call'`
- If both exist: compare `MIN(callrail_leads.call_started_at)` vs `estimates.created_at` — whichever is earlier determines the medium
- If neither → NULL

**Rationale:** The "first touch" decision is a join-time calculation requiring both the estimate creation timestamp and the earliest call timestamp. Computing it in the view keeps the component free of temporal logic.

**Alternative considered:** Compute in the component using `row.has_form`, `row.call_count`, and a separate call timestamp query. Rejected — more complex, not available without the `first_call_at` timestamp from the lateral aggregate.

### D5: Dynamic source/campaign options computed from loaded rows

**Decision:** Source and campaign dropdown options are derived from the loaded `rows` array via `useMemo` — collecting all distinct non-null values from `callrail_sources` and `callrail_campaigns` arrays.

**Rationale:** This keeps options consistent with the visible time window, avoids a separate metadata query, and updates automatically when data refreshes.

### D6: Step filter uses "has any of" semantics, not "furthest reached"

**Decision:** The Step filter options are: All / Pre-discovery / Has Booking / Has Qualified / Has Converted / Closed. Selecting "Has Qualified" shows all estimates where `qualified_status IS NOT NULL`, regardless of whether they also have a converted stage.

**Rationale:** Operator use case is "show me everything that reached Qualified" (e.g., for reviewing upload errors), not "show me estimates where Qualified was the last stage". Inclusive semantics are more flexible and easier to explain.

## Risks / Trade-offs

- **View rebuild requires DROP + CREATE** → Migration must use `DROP VIEW IF EXISTS … CREATE VIEW` pattern (same as previous Conversions view migrations). Rollback is a re-migration to the previous view definition.
- **`UNNEST` on NULLable arrays** → Must use `COALESCE(arr, '{}')` before `UNNEST` to avoid NULL expansion errors. Covered in the SQL design.
- **Dynamic dropdown options vary with time window** → If the 90-day window contains no campaigns, the Campaign dropdown stays at "All (0)". Acceptable — users can still see the dropdown exists.
- **`all_gclids` array could be large** → In practice, 1-3 GCLIDs per estimate. No pagination needed for the tooltip.

## Migration Plan

1. Write migration `20260422000002_enrich_conversion_candidates.sql`
   - DROP + CREATE `vw_conversion_candidates`
   - Extend `call_agg` lateral with `callrail_campaigns`, `callrail_gclids`, `first_call_at`
   - Add `assign_agg` lateral (mirrors `vw_booking_estimates` pattern)
   - Add `form_gclid_agg` lateral for `booking_tags` GCLIDs
   - Compute `all_gclids` and `first_touch_medium` as SELECT expressions
   - Re-grant SELECT to `authenticated` and `service_role`
2. Apply migration to local Supabase instance
3. Update frontend `PipelineRow` interface and query
4. Implement filter bar and enriched detail sections

**Rollback:** Re-apply `20260421000002_conversion_candidates_view.sql` — the previous view definition is preserved in migrations.

## Open Questions

- None outstanding — all design decisions made during exploration.
