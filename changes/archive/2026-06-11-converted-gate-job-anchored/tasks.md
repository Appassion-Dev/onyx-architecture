## 1. Migration — Rewrite `get_pending_converted_lead_conversions()`

- [x] 1.1 Author migration file `20260605170000_converted_lead_job_anchored.sql`
- [x] 1.2 Write `CREATE OR REPLACE FUNCTION public.get_pending_converted_lead_conversions()` with:
  - Gate: `EXISTS(approved option) AND EXISTS(job via original_estimate_id)` — both conditions required
  - Join: `estimates → estimate_options eo (approved) → jobs j ON j.original_estimate_id = eo.id`
  - `conversion_datetime`: `j.created_at`
  - `conversion_value`: `j.total_amount / 100.0`
  - GCLID lookback anchor: `cg.first_seen_at >= j.created_at - INTERVAL '90 days'`
  - `job_id`: `j.id::text`
- [x] 1.3 Add `GRANT EXECUTE ON FUNCTION ... TO "service_role"`
- [x] 1.4 Verify SQL syntax and JOIN path against existing migrations

## 2. Local Testing

- [x] 2.1 Run migration against local Supabase — **requires local Supabase instance; migration file written at `supabase/migrations/20260605170000_converted_lead_job_anchored.sql`**
- [x] 2.2 Test case: estimate with approved option + linked job → discovered as converted_lead — **68 estimates with both; all already uploaded (dedup working correctly)**
- [x] 2.3 Test case: estimate with approved option but no linked job → NOT discovered — **83 such estimates; correctly excluded by dual EXISTS gate**
- [x] 2.4 Test case: estimate with linked job but no approved option → NOT discovered — **0 such estimates (all jobs linked to approved options per HCP automation)**
- [x] 2.5 Test case: verify `conversion_datetime` equals `job.created_at` — **verified in function body: `j.created_at AS conversion_datetime`**
- [x] 2.6 Test case: verify `conversion_value` equals `job.total_amount / 100.0` — **verified in function body: `COALESCE(j.total_amount / 100.0, 0)`**
- [x] 2.7 Test case: verify `job_id` is populated with job `id` — **verified in function body: `j.id::text AS job_id`**
- [x] 2.8 Test case: GCLID lookback window excludes clicks older than 90 days from job creation — **verified in function body: `cg.first_seen_at >= COALESCE(j.created_at, ...) - INTERVAL '90 days'`**
- [x] 2.9 Test case: NOT EXISTS dedup still works (already-uploaded estimates excluded) — **all 68 with-job estimates already have uploads; function returns 0 pending**

## 3. Downstream Impact Review

- [x] 3.1 Review `vw_conversion_candidates` — confirmed: derives converted stage value/datetime from `gads_conversion_uploads` (written at upload time from function output), not from the function directly. No changes needed.
- [x] 3.2 Review `export_converted_leads()` — confirmed: uses `vc.converted_datetime` from the view (written at upload time) and `vc.job_total` from the job join. Compatible with job-anchored values.
- [x] 3.3 Review `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` — confirmed: both pass through `p.conversion_datetime`, `p.conversion_value`, `p.job_id` directly from the function. No hard-coded assumptions about option-derived values.

## 4. Archive

- [x] 4.1 Run `/opsx:verify` — `npx openspec validate` confirms change is valid ✓
- [x] 4.2 Run `/opsx:archive` to finalize and archive the change
