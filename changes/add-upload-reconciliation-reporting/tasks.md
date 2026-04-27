## 1. Reporting Dataset

- [x] 1.1 Flatten the latest `gads_action_upload_health.daily_summaries` payloads into per-day Google successful and failed counts keyed by reporting date and enabled configured conversion action.
- [x] 1.2 Aggregate local `gads_conversion_uploads` by upload date and conversion type, resolve the top-level event key from `gads_conversion_config`, and derive an exclusive source bucket for each uploaded row using the precedence `thumbtack` -> `form` -> `calls` -> `other`.
- [x] 1.3 Create the daily reconciliation query surface that joins local uploaded totals with Google daily-summary totals by config-driven event key, preserves local-only and Google-only rows, and exposes separate backlog counts plus snapshot freshness metadata.

## 2. Navigation And Queries

- [x] 2.1 Add a dedicated Conversions reporting route and sidebar entry alongside Analytics and Uploads.
- [x] 2.2 Add the frontend data-loading layer for the reporting page, including the enabled event catalog from dashboard settings, event-grouped daily reconciliation rows, backlog summary counts, and snapshot freshness metadata.

## 3. Reporting UI

- [x] 3.1 Build the reporting view with top-level event sections derived from enabled dashboard-configured conversion events, rendering only events with local or Google data in the selected period; with current seeded config this renders booking, qualified, and converted.
- [x] 3.2 Add weekly rollups and previous-period comparison for the same displayed metrics inside each event section using the same grouping rules already used elsewhere in the dashboard.
- [x] 3.3 Add explanatory copy or tooltips that make the aggregate-reconciliation model clear, distinguish event sections from local source buckets, and link users to Uploads for row-level investigation and Analytics for health/freshness context.

## 4. Validation And Documentation

- [ ] 4.1 Validate the reporting page against local data for matched days, local-only days, Google-only days, configured-but-empty events, and rows without `uploaded_at`.
- [x] 4.2 Document the event-catalog rules, source-bucket precedence, and the distinction between dated reconciliation totals and backlog totals so future changes do not silently change the reporting contract.