## Context

`vw_gads_upload_reconciliation_daily` was introduced with a `source_bucket` CTE that maps the 7-channel taxonomy back to 4 legacy categories (form / calls / thumbtack / other). This mapping was preserved during the `lead-channel-taxonomy` migration to avoid breaking existing consumers. Investigation revealed the only consumer of the bucket columns — `ConversionReportingPage.tsx` — is not routed in `App.tsx` and never actually renders. `UploadReportPage` (the live page) goes through `useCombinedUploadReport` → `buildCombinedHierarchy()`, which calls `addRow()` and accumulates bucket fields into `UploadReportAggregates`, but `sumAgg()` in the page component only reads 5 fields (`uploaded`, `confirmed`, `failed`, `gclid`, `amount`). The 12 bucket columns are carried silently and dropped at the last step.

## Goals / Non-Goals

**Goals:**
- Remove the `source_bucket` CTE and 12 derived bucket columns from `vw_gads_upload_reconciliation_daily`
- Remove the corresponding 12 fields from `UploadReportDailyRow`, `UploadReportAggregates`, `emptyAggregates()`, `addRow()`, and `mergeAggregates()` in `uploadReport.ts`
- Delete `ConversionReportingPage.tsx` (unrouted; all bucket rendering lived here)
- Leave `UploadReportPage.tsx` and all live functionality completely untouched

**Non-Goals:**
- Adding channel-level breakdown to `UploadReportPage` (separate change if ever desired)
- Modifying `vw_conversion_candidates` (unchanged)
- Touching the upload edge function or any Google Ads upload logic

## Decisions

### Decision: CREATE OR REPLACE vs. DROP + RECREATE the view

Both achieve the same schema result. `CREATE OR REPLACE` is preferred because it avoids the CASCADE dependency risk — if any other object unexpectedly depends on the reconciliation view, `DROP ... CASCADE` would silently remove it. `CREATE OR REPLACE` will fail loudly instead. This is the right behavior for a column-removal change.

> Alternative considered: `DROP VIEW ... CASCADE` followed by `CREATE VIEW`. Rejected because it silently removes dependencies; the previous migration already demonstrated this risk.

### Decision: Delete ConversionReportingPage.tsx outright vs. keep as dead code

The page is unrouted, will never be seen, and references 12 columns that will no longer exist in the view schema. Keeping it means it will bitrot (TS type errors after the interface change) and mislead future readers. Deletion is correct. The file is in Git history if it's ever needed.

> Alternative considered: Leave file but remove bucket field references. Rejected — a file not reachable from any route has no reason to exist.

### Decision: Keep `UploadReportAggregates` and `emptyAggregates`/`addRow`/`mergeAggregates` helpers

These helpers are still needed by `buildCombinedHierarchy()` — the week/month roll-up math uses them for the non-bucket fields (`localUploadedCount`, `gclidCount`, `googleSuccessfulCount`, `googleFailedCount`, `amount`). Only the 12 bucket-specific fields inside them are removed.

## Risks / Trade-offs

- **[Risk] View column removal is a breaking schema change** → Mitigation: Verified no live code reads bucket columns. `UploadReportPage` calls `SELECT *` from the view — TypeScript types must be updated before or alongside the migration to avoid a runtime mismatch. Deploy migration and frontend together.

- **[Risk] ConversionReportingPage deletion is irreversible** → Mitigation: Git history preserves the file. The page was never reachable by users. If bucket-level reporting is ever wanted again, it would be rebuilt from the 7-channel taxonomy rather than restored.

## Migration Plan

1. Write new migration: `CREATE OR REPLACE VIEW public.vw_gads_upload_reconciliation_daily` — identical to existing view minus the `source_bucket` CTE and the 12 bucket SELECT columns
2. Update `uploadReport.ts` TypeScript interfaces and helpers to remove bucket fields
3. Delete `ConversionReportingPage.tsx`
4. Verify `UploadReportPage` still type-checks and renders correctly
5. User applies migration to local Supabase, then deploys frontend

**Rollback**: Restore the previous view definition from `20260507000001_lead_channel_taxonomy.sql` lines 283–406, revert `uploadReport.ts`, and restore `ConversionReportingPage.tsx` from Git.

## Open Questions

- None — the consumer analysis is complete and the scope is well-bounded.
