## 1. Database — Extend Daily Reconciliation View

- [ ] 1.1 Write new migration file to extend `vw_gads_upload_reconciliation_daily` with `gclid_count` and `amount` columns in the `local_classified` and `local_daily` CTEs
- [ ] 1.2 Add `gclid_count` per source bucket columns (form, calls, thumbtack, other) to `local_daily` CTE
- [ ] 1.3 Verify the updated view returns correct values locally (query Supabase Studio or psql)

## 2. Data Layer — Frontend Hook

- [ ] 2.1 Create `useUploadReport(eventKey: string)` hook that queries `vw_gads_upload_reconciliation_daily` filtered by `event_key`
- [ ] 2.2 Implement `buildUploadHierarchy(rows)` utility that groups daily rows into month → week structure, summing all numeric columns per group
- [ ] 2.3 Add `latest_google_synced_at` extraction (max value across all rows) for the freshness label

## 3. Page — UploadReportPage Component

- [ ] 3.1 Create `UploadReportPage.tsx` under `horizon-dashboard/src/components/pages/`
- [ ] 3.2 Implement three-tab layout (Booking Leads / Qualified Leads / Converted Leads) using existing tab pattern from the codebase
- [ ] 3.3 Wire active tab to `useUploadReport` hook with the corresponding `event_key`
- [ ] 3.4 Add Google data freshness label ("Google data as of [latest_google_synced_at]") near top of each tab

## 4. Table — Month/Week Hierarchy

- [ ] 4.1 Implement collapsible month header rows showing aggregate stats (uploaded, gclid, Google ✓, Google ✗, amount)
- [ ] 4.2 Implement collapsible week header rows showing aggregate stats (same columns as month)
- [ ] 4.3 Month rows collapsed by default; expand on click
- [ ] 4.4 Implement per-source breakdown rows (form / calls / thumbtack / other) inside expanded weeks
- [ ] 4.5 Source rows show local stats only (uploaded, gclid, amount); Google columns display — for source rows
- [ ] 4.6 Hide source rows where uploaded count is zero for that week

## 5. Amount Column Handling

- [ ] 5.1 Suppress amount column (display —) on Booking Leads tab at all levels
- [ ] 5.2 Display formatted currency amount on Qualified Leads and Converted Leads tabs

## 6. Routing

- [ ] 6.1 Add route for the Upload Report page in the app router
- [ ] 6.2 Add navigation link to the Conversions section nav
