## Context

The ConversionsPage currently renders a month → week → estimate hierarchy from `vw_gads_conversion_pipeline`. Each row has three conversion stages (booking, qualified, converted) with per-stage status badges, a `booking_source` column ('form'/'call'), `job_id`/`job_invoice_number` columns, and per-stage value columns. The companion change `pipeline-stage-criteria-v3` redefines stage criteria and drops the jobs table from the pipeline. This change updates the dashboard to match the new view contract.

Current component map:
- `ConversionsPage.tsx` — main pipeline table (PipelineRow interface, computeStats, status badges)
- `BookingManagerPage.tsx` — form-submitted bookings management (route `/bookings`)
- `App.tsx` — route definitions and imports
- `Sidebar.tsx` — nav items

## Goals / Non-Goals

**Goals:**
- Update ConversionsPage to consume the revised pipeline view (no job columns, new source fields, unified value)
- Render lead sources as multiple badges per estimate, using both estimate-level `lead_source` and CallRail-level sources
- Rename BookingManagerPage → OnlineBookingsPage with updated route and sidebar entry
- Ensure weekly/monthly totals sum `display_value` once per estimate

**Non-Goals:**
- Changing the ConversionConfigPage (unchanged by pipeline-stage-criteria-v3)
- Changing the upload edge function behavior
- Modifying the OnlineBookingsPage query or filtering logic (it stays form-only)
- Changing the batch upload or manual upload flows

## Decisions

### 1. Source badges from view columns, not separate queries

**Decision**: The pipeline view will expose `has_form` (boolean), `call_count` (integer), `lead_source` (text), and `callrail_sources` (text[] or comma-separated). The ConversionsPage renders badges purely from these columns without additional queries.

**Rationale**: Keeps the page a single-query component. The view already joins all necessary tables.

**Badge rendering logic**:
- If `has_form = true` → render "Form" badge
- If `call_count > 0` → render "Call (N)" badge
- If `lead_source IS NOT NULL` → render `lead_source` value as badge (e.g., "Google Ads", "Google Local Services", "Thumbtack")
- If CallRail leads have distinct sources → render each unique source as a badge

**Alternative considered**: Fetching CallRail lead details in a separate query per estimate. Rejected — N+1 problem, unnecessary complexity.

### 2. CallRail sources exposed as aggregated array from view

**Decision**: The pipeline view will aggregate distinct `callrail_leads.source` values for each estimate into a `callrail_sources` column (text array or comma-separated string).

**Rationale**: CallRail leads carry their own `source` field representing the attribution channel (Google Ads, Google Local Services, GMB, etc.). This is distinct from `estimates.lead_source`. Both should be shown. Aggregating in the view avoids per-row subqueries in the frontend.

### 3. Drop per-stage value columns, keep only display_value

**Decision**: Remove `booking_value`, `qualified_value`, `converted_value` from the PipelineRow interface. `display_value` = SUM of approved/pro-approved estimate options, shared across all stages.

**Rationale**: All stages now use the same value formula. Showing different values per stage column was meaningful when booking=NULL, qualified=quoted, converted=job revenue. Now booking=NULL and qualified/converted use the same approved-options sum. A single `display_value` column suffices.

### 4. Rename route from /bookings to /online-bookings

**Decision**: Change the route path, file name, component name, and sidebar label simultaneously.

**Rationale**: "Bookings" is now ambiguous — the booking conversion stage covers all channels. "Online Bookings" makes it clear this page is specifically for form-submitted bookings from the online booking widget.

### 5. Weekly totals unchanged in logic

**Decision**: `computeStats` already sums `display_value` once per row (which is one per estimate). No logic change needed — only the underlying value semantics change (now always approved options sum).

**Rationale**: The function iterates `PipelineRow[]` where each row is one estimate. The math is already correct.

## Risks / Trade-offs

- **CallRail sources could be noisy** → If an estimate has many correlated calls with different sources, the badge row could get crowded. Mitigation: cap at 3-4 unique source badges, show "+N more" if exceeded.
- **lead_source may duplicate CallRail source** → An estimate with `lead_source = 'Google Ads'` and a CallRail lead with `source = 'Google Ads'` would show duplicate badges. Mitigation: deduplicate sources in the rendering logic (collect all unique source strings, then render).
- **Bookmark/link breakage** → Users with `/bookings` bookmarks will get a 404 after rename. Mitigation: the catch-all route `<Route path="*">` redirects to `/`. Acceptable for an internal dashboard.
