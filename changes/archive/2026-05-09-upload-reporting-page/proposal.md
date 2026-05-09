## Why

We upload conversion events to Google Ads but have no way to verify how many records Google actually received vs. what we sent. A dedicated upload reporting page, keyed on `uploaded_at`, gives us a clean reconciliation view: local uploads vs. Google-confirmed receipts, broken down by source and grouped by day/week/month.

## What Changes

- Add `gclid_count` and `amount` columns to the existing `vw_gads_upload_reconciliation_daily` view
- New page: **Upload Report** under the Conversions section
- The page has three tabs — Booking Leads, Qualified Leads, Converted Leads — one per Google Ads conversion action
- Each tab shows a month → week → daily hierarchy (client-side grouping from daily view data)
- Week/month header rows show aggregate stats: uploaded count, gclid count, Google received, Google failed, conversion amount
- Expanding a week reveals per-source breakdown rows (form / calls / thumbtack / other) with local stats only (Google-side not split by source)

## Capabilities

### New Capabilities

- `upload-report-page`: Upload reporting page with tab-per-conversion-type, date hierarchy (month/week), and local vs. Google reconciliation stats per row

### Modified Capabilities

- `conversion-upload`: Add `gclid_count` (uploaded rows with a gclid) and `amount` (`SUM(conversion_value)`) to the daily reconciliation view

## Impact

- **DB migration**: `vw_gads_upload_reconciliation_daily` updated to include two new columns (`gclid_count`, `amount`)
- **New frontend page**: `UploadReportPage.tsx` under `horizon-dashboard/src/components/pages/`
- **Routing**: New route wired into the app router
- **Data fetch**: Queries `vw_gads_upload_reconciliation_daily` (existing view, already permissioned); no new edge function needed
- **No breaking changes** to existing reconciliation page or daily view consumers
