## Context

The Conversions area now has a clean split between Analytics and Uploads, but neither page answers the daily reconciliation question that operators actually ask: how many uploads did we send on a given day, and how many did Google report back for that same day or week for each conversion event we care about. The current Uploads page is row-level and grouped by `estimate_created_at`, while the cached Google upload-health payloads live separately as raw `daily_summaries` arrays in `gads_action_upload_health` and `gads_client_upload_health`.

The required inputs already exist:
- `gads_conversion_uploads` records local upload attempts, statuses, and `uploaded_at`
- `gads_conversion_config` maps each local `conversion_type` to a Google Ads conversion action
- `gads_action_upload_health` stores action-level `daily_summaries` snapshots from Google Ads
- `vw_conversion_candidates` already exposes the source signals needed to classify uploads into operator-facing buckets

The main constraint is grain: Google `daily_summaries` are aggregated by date and conversion action, not by local upload row. That means this feature can provide date-level reconciliation, but not row-level proof that a specific upload row was accepted or attributed by Google.

## Goals / Non-Goals

**Goals:**
- Add a dedicated Conversions reporting surface for daily and weekly upload reconciliation.
- Drive the report's top-level event sections from dashboard conversion settings so seeded `booking`, `qualified`, and `converted` sections appear now and future configured actions extend the reporting catalog automatically.
- Show local uploaded counts alongside cached Google successful counts and failed counts on a shared date grain.
- Show prior-period comparison for both daily and weekly groupings.
- Segment local upload totals into stable source buckets such as `form`, `calls`, `thumbtack`, and `other`.
- Keep the page fully cache-backed so it renders from stored Supabase data instead of live Google Ads queries.
- Only render active event sections when an enabled configured action has local or Google data in the selected period.

**Non-Goals:**
- Row-by-row proof that Google accepted or attributed a specific local upload.
- Replacing the existing Analytics page or the Uploads workbench.
- Requiring new Google Ads queries on dashboard load.
- Solving every historical source taxonomy problem in the first version.
- Forcing pending rows into a dated reconciliation row when they do not yet have an upload date.

## Decisions

### D1: Add a dedicated Reporting child page under Conversions

The reconciliation UI will live on its own route, proposed as `/conversions/reporting`, alongside the existing Analytics and Uploads pages. This keeps Analytics focused on health/config telemetry and keeps Uploads focused on row-level operations.

**Alternative considered:** add the reporting grid as another Analytics panel. Rejected because daily and weekly reconciliation is table-heavy, period-oriented, and would crowd the summary-first Analytics page.

### D2: Build one daily base dataset and derive the page from it

The backend will expose a daily reconciliation dataset, preferably as a SQL view such as `vw_gads_upload_reconciliation_daily`, that joins:
- local uploaded rows from `gads_conversion_uploads`
- conversion action mapping from `gads_conversion_config`
- latest Google action-health `daily_summaries` from `gads_action_upload_health`
- source signals from `vw_conversion_candidates`

The page will read this daily dataset and derive the visible event sections, day rows, week rows, totals, and prior-period comparisons from it. The dataset will therefore need a config-driven `event_key` field, an operator-facing `event_label`, and date-grained metrics that can support local-only and Google-only rows without forcing both sides to exist.

**Alternative considered:** parse raw `daily_summaries` JSON directly in React and join everything client-side. Rejected because it duplicates reconciliation logic in the UI, makes testing harder, and ties page behavior to raw payload shape.

### D3: Use enabled config rows as the reporting catalog and data-backed tabs as the UI rule

The reporting page will group records first by a config-driven event key, then by day and week inside each event section. The event catalog will be derived from enabled rows in `gads_conversion_config`, which is already managed through dashboard settings. With the current seeded config, the page will render `booking`, `qualified`, and `converted`, but future configured actions extend the reporting catalog automatically without requiring UI code changes.

The event key is resolved by using `conversion_type` as the canonical local key and `conversion_action_id` as the canonical Google-side join key. Both sides are then translated into the same config-driven event section.

The UI will not render a configured event as an active tab solely because it exists in settings. A section becomes active only when the selected period has local uploaded counts or Google summary counts for that enabled configured event. This keeps the catalog extensible without implying that every configured action already has end-to-end local pipeline coverage.

For v1, the existing config fields are sufficient for the reporting catalog. The page will use `conversion_type` as the stable event key, `conversion_action_id` as the Google-side join key, and a deterministic label derived from `conversion_action_name` with a fallback to the conversion type. No separate reporting-metadata table is required in the first pass.

**Alternative considered:** hardcode three lifecycle tabs in the UI. Rejected because it creates unnecessary maintenance and would force code changes every time the dashboard settings gain a new reporting action.

### D4: Reconcile on upload date, not estimate date

The local side of the comparison will use the day the upload actually happened (`uploaded_at` normalized to the reporting timezone), not `estimate_created_at` or `conversion_datetime`. This is the only local timestamp that matches the operational question "what did we upload that day".

Google-side rows will use the date contained in the latest action-level `daily_summaries` entry. The joined row therefore represents a single reporting day, not an estimate cohort.

**Alternative considered:** reuse the Uploads page grouping by `estimate_created_at`. Rejected because that groups lead creation, not upload/reporting activity.

### D5: Use the latest configured action-level daily summaries as the Google side of the comparison

The Google side will be flattened from the latest `gads_action_upload_health` snapshot per `conversion_action_id`, then summed by reporting date. The reporting row will carry distinct Google `successfulCount` and `failedCount` values rather than collapsing them into one overloaded "reported" number. Action-level summaries are a better fit than client-level summaries because local uploads can already be mapped to conversion actions through `gads_conversion_config`.

The reporting view will explicitly filter those action summaries through enabled `gads_conversion_config` rows before surfacing them in the page. That keeps raw Google telemetry available in Analytics while ensuring the reporting page only shows actions that are part of the dashboard's configured reporting catalog.

Client-level health remains useful for system-health panels, but it is too coarse to serve as the canonical source for reconciliation totals.

**Alternative considered:** use `gads_client_upload_health` totals for the reconciliation grid. Rejected because it cannot be aligned cleanly with local action/type counts.

### D6: Source bucketing will be exclusive and local-only in v1

Each local uploaded row will be classified into exactly one reporting bucket so bucket subtotals always add up to the local total. The initial precedence will be:
1. `thumbtack` when explicit Thumbtack signals are present in source fields
2. `form` when booking-form signals are present
3. `calls` when call-only signals are present
4. `other` for everything else

This bucket is derived from stored local source signals such as `lead_source`, `callrail_sources`, `first_touch_medium`, `has_form`, and `call_count`. Google successful and failed counts remain unsegmented in v1 because Google daily summaries are not source-aware.

**Alternative considered:** allow the same row to count in multiple source buckets. Rejected because it makes the bucket totals exceed the daily total and weakens operator trust in the report.

Using `form` instead of `booking` in the source taxonomy is intentional. It avoids a naming collision between top-level event sections like `booking` and local-source subtotals, which represent different concepts.

### D7: Pending backlog stays outside the dated reconciliation table

Pending rows do not have a stable upload date, so they will not be forced into the daily comparison table. Instead, the page will show a separate backlog summary for current pending rows, retrying rows, and skipped rows.

This keeps the day/week reconciliation honest while still exposing the operational backlog that the user asked about.

**Alternative considered:** assign pending rows to `conversion_datetime` or estimate date. Rejected because it mixes backlog state with upload activity and produces misleading date totals.

### D8: Weekly rollups and prior-period comparisons derive from the daily dataset in the app layer

The page will group daily rows into weeks inside each event section using the same week/fiscal-period utilities already used elsewhere in the dashboard. Prior-period comparison will be computed from the immediately preceding equivalent period:
- day rows compare to the previous day
- week rows compare to the previous week

Keeping period comparison in the app layer avoids proliferating narrowly tailored SQL views and makes it easy to reuse the same derived dataset for filters and drill-downs.

**Alternative considered:** precompute separate weekly and prior-period SQL views. Rejected because the daily base dataset is already small and the extra SQL surfaces would add maintenance without solving a real scale problem.

## Risks / Trade-offs

- [Timezone mismatch between local `uploaded_at` and Google summary dates] -> Normalize local timestamps into the same reporting timezone used for the Google day key and label the page clearly when data freshness or timezone assumptions matter.
- [Google `daily_summaries` payload shape changes or differs between accounts] -> Flatten only the fields needed for v1 and keep the raw payload available for diagnostics if the parser needs adjustment.
- [Source bucketing misclassifies edge cases] -> Keep the precedence rules explicit, start with a small dictionary, and show row-level drill-down from the report back into Uploads.
- [Users assume reconciliation equals attribution] -> Copy must state that the page compares local uploads with Google successful and failed upload summaries, not downstream attribution credit.
- [Latest snapshot is stale] -> Surface snapshot freshness in the reporting page header and degrade gracefully when the newest Google summary data is older than expected.

## Migration Plan

1. Add a daily reconciliation view that flattens latest Google action summaries and joins them to local uploaded rows plus source-bucket enrichment.
2. Use enabled `gads_conversion_config` rows as the event catalog so dashboard-configured actions define and extend the reporting catalog automatically, while active tabs remain data-backed.
3. Add a new Conversions reporting route and sidebar child entry.
4. Build the reporting page on top of the daily dataset, including event sections, daily rows, weekly rollups, prior-period comparisons, and backlog summary tiles.
5. Link the reporting page back to Uploads for row-level investigation and to Analytics for freshness/health inspection.
6. Roll back by removing the reporting page and route while keeping the new view unused if the UI needs to be reverted first.

## Open Questions

- Should the first version stop at the three raw columns `uploaded`, `successful`, and `failed`, or also add optional derived columns such as `processed` or `delta`?
- Should the new navigation label be `Reporting`, `Summaries`, or `Reconciliation`?
- Do we want the first source taxonomy to stop at `thumbtack`, or should it also reserve explicit buckets for sources like Local Services or website form campaigns in the first pass?