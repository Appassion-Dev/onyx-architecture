## Context

We have `vw_gads_upload_reconciliation_daily`, a Postgres view that returns one row per `(event_key, reporting_date)` containing local upload counts by source bucket and Google-side counts from stored health snapshots. The view already covers the reconciliation data we need — it's missing only `gclid_count` (uploaded rows that had a gclid) and `amount` (sum of `conversion_value`).

Each conversion type (`booking_lead`, `qualified_lead`, `converted_lead`) maps 1:1 to a Google Ads conversion action, so reconciliation stats from Google are only meaningful per type — not combined.

The existing `vw_gads_upload_reconciliation_daily` is already queried by the existing reconciliation panel. This change extends that view and adds a new page that consumes it.

## Goals / Non-Goals

**Goals:**
- Extend the daily view with `gclid_count` and `amount`
- New Upload Report page with tab-per-conversion-type
- Month → week hierarchy client-side from daily rows (no new DB view)
- Week/month header rows: uploaded, gclid, Google received, Google failed, amount
- Expanded week: per-source rows (form / calls / thumbtack / other) with local stats only

**Non-Goals:**
- Google-side count breakdowns per source bucket (structurally unavailable)
- Backlog / pending / skipped records on this page (separate concern, separate view)
- Modifying the existing reconciliation panel (different page, different purpose)
- New edge functions (all data available from existing view)

## Decisions

### Decision 1: Aggregate weekly/monthly in the frontend, not the DB

**Choice:** Query the existing daily view and group client-side into weeks/months.

**Rationale:** The daily view returns ~365 rows/year per tab — trivially small to hold in memory. A dedicated weekly view would be a second migration to maintain and would lose the flexibility to group by month at no extra cost. Frontend grouping keeps the DB layer thin.

**Alternative considered:** New `vw_gads_upload_reconciliation_weekly` view. Rejected because the daily view is already the right granularity and frontend aggregation is simpler to maintain.

### Decision 2: Extend existing daily view rather than create a parallel one

**Choice:** Add `gclid_count` and `amount` to `vw_gads_upload_reconciliation_daily` via a new migration.

**Rationale:** The existing view already has all the join complexity (local data + Google health data + source classification). Adding two aggregate columns to the `local_daily` CTE is minimal and avoids duplicating that complexity in a new view. Existing consumers of the view get the new columns for free and can ignore them.

**Alternative considered:** A new parallel view for this page only. Rejected — duplication of ~150 lines of CTE logic for no gain.

### Decision 3: Tabs per conversion type, not combined

**Choice:** Three tabs — Booking Leads, Qualified Leads, Converted Leads.

**Rationale:** Each type maps to a distinct Google Ads conversion action. Mixing them would make the Google-side counts (from `gads_action_upload_health` per `conversion_action_id`) ambiguous. Tabs also make the `amount` column coherent — Booking has no monetary value, Qualified has estimate value, Converted has invoice total.

### Decision 4: Google stats at week aggregate only, source rows show local only

**Choice:** Google received/failed columns blank (`—`) in per-source breakdown rows.

**Rationale:** Google's health API returns counts per conversion action per day. It has no knowledge of our source classification (form/call/thumbtack). Displaying Google counts at the source level would be meaningless or misleading.

## Risks / Trade-offs

- **View extension is additive but touches live SQL** → Migration is `CREATE OR REPLACE VIEW`, fully reversible. New columns are nullable/zero-defaulted so existing consumers are unaffected.
- **Client-side grouping depends on clean `reporting_date` values** → The view already guards against `NULL` reporting dates (`WHERE summary.reporting_date IS NOT NULL`). Safe.
- **Google counts use upload date from health snapshots; local counts use `uploaded_at`** → These should align well since health snapshots are fetched daily. Small same-day lag is acceptable for a reporting page. Documented in the UI with a "Google data as of `latest_google_synced_at`" label.
- **`booking_lead` amount is always null** → Amount column shows `—` on Booking tab. Expected and labeled.

## Migration Plan

1. New migration file: extend `vw_gads_upload_reconciliation_daily` with `gclid_count` and `amount`
2. Apply locally, verify columns appear in Supabase Studio
3. Deploy new frontend page and route
4. No rollback needed — view change is additive; page can be removed independently

## Open Questions

- None. All design decisions resolved during exploration.
