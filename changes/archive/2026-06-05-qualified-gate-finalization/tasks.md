## 1. Qualified gate — modify existing migration

- [x] 1.1 Rename `supabase/migrations/20260526000001_qualified_lead_gate_approval_status.sql` to `20260526000001_qualified_lead_gate_finalization.sql` (keep the `20260526000001` timestamp prefix to preserve ordering; safe because the migration is not yet deployed).
- [x] 1.2 In the renamed migration, replace the `WHERE` gate of `get_pending_qualified_lead_conversions()` with: `e.work_status IN ('complete rated','complete unrated','created job from estimate')` **AND** `EXISTS (SELECT 1 FROM estimate_options eo WHERE eo.estimate_id = e.id AND eo.total_amount > 0)`; remove the `approval_status IN ('approved','pro approved')` clause.
- [x] 1.3 Leave the rest of the function unchanged: `conversion_datetime = e.updated_at`, `conversion_value = COALESCE(AVG(eo.total_amount)/100.0, 0)` over all options, the GCLID resolver (oldest in-window, `ORDER BY first_seen_at ASC`), the `NOT EXISTS` qualified_lead de-dup, and the `GRANT EXECUTE ... TO service_role`.
- [x] 1.4 Update the file's header comment to describe the finalization gate (replace the prior approval-status rationale).

## 2. Clear work_timestamps bloat — new migration

- [x] 2.1 Create a new migration later than `20260526000001` (e.g. `20260605000001_truncate_work_timestamps.sql`) containing `TRUNCATE public.work_timestamps;` with a header comment recording the rationale (~6M rows, ~635× duplication, frozen 2025-12-04) and the safety basis (no inbound FKs, no dependent views/functions — no FK pre-cleanup needed).

## 3. Revive the importers — hcp-import-data

- [x] 3.1 In `supabase/functions/hcp-import-data/import-estimates.ts`, change the `transformWorkTimestamps` id from `ts_est_${estimateId}_${Date.now()}` to the deterministic `ts_est_${estimateId}`.
- [x] 3.2 In `import-estimates.ts`, add a `work_timestamps` entry to the `batchUpsertRelated` related-records block: `extractRecords` returns `transformWorkTimestamps(estimate.work_timestamps, estimate.id)` wrapped as `[row]` (or `[]` when the transform returns null), with `conflictColumns: 'id'` and a batch size consistent with the sibling entries.
- [x] 3.3 In `supabase/functions/hcp-import-data/import-jobs.ts`, change the `transformWorkTimestamps` id from `ts_job_${jobId}_${Date.now()}` to the deterministic `ts_job_${jobId}`.
- [x] 3.4 In `import-jobs.ts`, wire `work_timestamps` into the related-records phase the same way (extract from `job.work_timestamps`, `conflictColumns: 'id'`).
- [x] 3.5 Confirm estimate rows set `estimate_id` only and job rows set `job_id` only (satisfies the table's single-entity CHECK); remove any unused imports/vars created by the edits.

## 4. Verify

- [x] 4.1 Run the rewritten `get_pending_qualified_lead_conversions()` and confirm a `created job from estimate` estimate with a priced option IS returned, and an `in progress` / `needs scheduling` estimate with a priced option is NOT.
- [x] 4.2 Confirm a `complete rated`/`complete unrated` estimate with a priced-but-unapproved option IS returned (approval not consulted), and a finalized estimate with no priced option is NOT.
- [x] 4.3 Spot-check that `conversion_datetime` of a returned row equals that estimate's `updated_at`.
- [x] 4.4 After the truncate migration, confirm `work_timestamps` is empty; after a test import, confirm exactly one row per estimate/job (no `Date.now()` duplicates) keyed `ts_est_<id>` / `ts_job_<id>`. _(Verified post-deploy 2026-06-05: prior 6.67M-row bloat gone, table held only fresh rows (created_at=2026-06-05); test import = 2,000 rows (1,000 estimate + 1,000 job), 0 legacy `Date.now()` ids, each row exactly one of estimate_id/job_id.)_
- [x] 4.5 Hand deployment to the user — do not run `supabase db push` and do not deploy edge functions from the agent.
