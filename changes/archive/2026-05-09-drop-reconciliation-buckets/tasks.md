## 1. Database Migration

- [x] 1.1 Create migration file `supabase/migrations/20260508000001_drop_reconciliation_buckets.sql`
- [x] 1.2 In the migration, write `DROP VIEW IF EXISTS` then `CREATE VIEW public.vw_gads_upload_reconciliation_daily WITH (security_invoker = true)` — keep all existing CTEs (`enabled_config`, `latest_action_health`, `google_daily`) unchanged
- [x] 1.3 In the `local_classified` CTE, remove the `source_bucket` CASE expression entirely
- [x] 1.4 In the `local_daily` CTE, remove all 12 bucket aggregate columns; keep `local_uploaded_count`, `gclid_count`, and `amount`
- [x] 1.5 In the `combined_daily` CTE, remove all 12 `COALESCE(ld.bucket_col, 0) AS bucket_col` lines; keep the non-bucket fields
- [x] 1.6 In the final `SELECT`, remove all 12 bucket column references from the output

## 2. TypeScript Interface Cleanup

- [x] 2.1 In `horizon-dashboard/src/lib/uploadReport.ts`, remove 12 bucket fields from `UploadReportDailyRow` interface (`form_uploaded_count`, `calls_uploaded_count`, `thumbtack_uploaded_count`, `other_uploaded_count`, `form_gclid_count`, `calls_gclid_count`, `thumbtack_gclid_count`, `other_gclid_count`, `form_amount`, `calls_amount`, `thumbtack_amount`, `other_amount`)
- [x] 2.2 Remove 12 bucket fields from `UploadReportAggregates` interface (`formUploadedCount`, `callsUploadedCount`, `thumbtackUploadedCount`, `otherUploadedCount`, `formGclidCount`, `callsGclidCount`, `thumbtackGclidCount`, `otherGclidCount`, `formAmount`, `callsAmount`, `thumbtackAmount`, `otherAmount`)
- [x] 2.3 Remove 12 bucket field initializers from `emptyAggregates()` return value
- [x] 2.4 Remove 12 bucket field accumulations from `addRow()` return value
- [x] 2.5 Remove 12 bucket field merges from `mergeAggregates()` return value

## 3. Dead Code Deletion

- [x] 3.1 Delete `horizon-dashboard/src/components/pages/ConversionReportingPage.tsx`
- [x] 3.2 Verify no imports of `ConversionReportingPage` remain (App.tsx has none — confirmed)

## 4. Verification

- [x] 4.1 Run TypeScript type check (`tsc --noEmit`) in `horizon-dashboard/` — build succeeded with zero errors
- [x] 4.2 Apply the migration to the local Supabase instance and confirm the view returns no bucket columns — 14 columns confirmed, no form/calls/thumbtack/other bucket columns
- [x] 4.3 Navigate to `/conversions/upload-report` in the dashboard and confirm the page loads and renders correctly with no console errors
