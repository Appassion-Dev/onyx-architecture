## Why

`vw_gads_upload_reconciliation_daily` carries 12 legacy "bucket" columns (`form_*`, `calls_*`, `thumbtack_*`, `other_*`) that collapse the 7-channel taxonomy introduced in `lead-channel-taxonomy` back into 4 coarse categories. Now that the `channel` column is authoritative and the only consumer of these bucket columns — `ConversionReportingPage` — is unrouted dead code, the buckets serve no purpose and create maintenance surface with no benefit.

## What Changes

- **BREAKING**: Remove 12 bucket columns from `vw_gads_upload_reconciliation_daily`: `form_uploaded_count`, `calls_uploaded_count`, `thumbtack_uploaded_count`, `other_uploaded_count`, `form_gclid_count`, `calls_gclid_count`, `thumbtack_gclid_count`, `other_gclid_count`, `form_amount`, `calls_amount`, `thumbtack_amount`, `other_amount`
- Remove the `source_bucket` CTE from the view SQL that mapped 7 channels to 4 buckets
- Remove the corresponding 12 fields from `UploadReportDailyRow` and `UploadReportAggregates` TypeScript interfaces in `uploadReport.ts`, plus all dead accumulation logic (`emptyAggregates`, `addRow`, `mergeAggregates`)
- Delete `ConversionReportingPage.tsx` — unrouted since the conversions section was redesigned; the only page that ever rendered the bucket UI

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `conversion-candidates-view`: The reconciliation view (`vw_gads_upload_reconciliation_daily`) no longer exposes source-bucket breakdown columns; reporting is now done at the channel level via `vw_conversion_candidates`

## Impact

- `supabase/migrations/` — new migration to `CREATE OR REPLACE` the view without bucket columns
- `horizon-dashboard/src/lib/uploadReport.ts` — `UploadReportDailyRow`, `UploadReportAggregates`, `emptyAggregates()`, `addRow()`, `mergeAggregates()` all shed bucket fields
- `horizon-dashboard/src/components/pages/ConversionReportingPage.tsx` — deleted (unrouted, all bucket UI lives here)
- `UploadReportPage.tsx` is unaffected — it never reads bucket columns from the aggregates
