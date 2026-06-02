> Tasks below are organized so each group implements one or more of the seven proposal points (see `proposal.md` § What Changes and `design.md` § Mapping to the seven proposal points). Group headers cite the relevant point number(s).

## 1. Resolver and gate rewrite — implements proposal points #1, #4, #5, #7

- [ ] 1.1 Create migration `supabase/migrations/<timestamp>_qualified_lead_gate_approved_priced_option.sql` that `CREATE OR REPLACE FUNCTION public.get_pending_qualified_lead_conversions()` with: gate = `EXISTS (estimate_options eo WHERE eo.estimate_id = e.id AND eo.approval_status IN ('approved','pro approved') AND eo.total_amount > 0)`, no `work_status` filter, **no GCLID subquery** (`gclid` column returns NULL; the discovery wrapper supplies it), `conversion_value = COALESCE(SUM(eo.total_amount)/100.0, 0)` summed across `estimate_options` rows for the estimate that satisfy the same approval+priced filter, `conversion_datetime = MAX(eo.updated_at)` across those same rows, retain `NOT EXISTS (gads_conversion_uploads ... qualified_lead)` gate, retain GRANT to `service_role`.
- [ ] 1.2 Create migration `supabase/migrations/<timestamp>_converted_lead_gate_job_exists.sql` that `CREATE OR REPLACE FUNCTION public.get_pending_converted_lead_conversions()` with: gate = `EXISTS (jobs j WHERE j.original_estimate_id = e.id)`, no `approval_status` filter on options, most-recent job selected via LATERAL `ORDER BY j.created_at DESC LIMIT 1` for `job_id`, `conversion_value = j.total_amount/100.0`, `conversion_datetime = j.updated_at`, **no GCLID subquery** (column returns NULL; wrapper supplies), retain `NOT EXISTS` gate, retain GRANT to `service_role`.
- [ ] 1.3 Create migration `supabase/migrations/<timestamp>_resolve_estimate_gclid.sql` defining `CREATE OR REPLACE FUNCTION public.resolve_estimate_gclid(p_estimate_id text) RETURNS text` (LANGUAGE sql STABLE SECURITY DEFINER) implementing the DESC newest-in-window resolver anchored on `GREATEST(e.updated_at, MAX(jobs.updated_at))` minus 90 days. Returns NULL when no in-window GCLID exists. GRANT EXECUTE to `service_role`.

## 2. Discovery wrapper rewrite (shared resolver + re-attribution) — implements proposal points #2 and #7

- [ ] 2.1 Create migration `supabase/migrations/<timestamp>_discover_with_shared_resolver.sql` that `CREATE OR REPLACE FUNCTION public.discover_pending_conversions()` to: (a) keep the existing `customer_gclids` pre-pass (booking_tags + callrail_leads), (b) run the re-attribution `UPDATE gads_conversion_uploads u SET gclid = resolve_estimate_gclid(u.estimate_id) WHERE u.status = 'pending' AND u.gclid IS NULL AND u.conversion_type IN ('qualified_lead','converted_lead')`, (c) execute the three stage detection functions and INSERT into `gads_conversion_uploads`, but for each estimate compute `resolve_estimate_gclid(e.id)` ONCE (e.g., via a CTE keyed on estimate_id) and apply that value to all three stage inserts so booking/qualified/converted rows for the same estimate share the same `gclid`.
- [ ] 2.2 In the same migration, also `CREATE OR REPLACE FUNCTION public.discover_pending_conversions_for_estimate(p_estimate_id text)` with the equivalent shape: pre-pass scoped to the estimate, single re-attribution UPDATE scoped to `u.estimate_id = p_estimate_id`, single `resolve_estimate_gclid(p_estimate_id)` call, value applied to all three stage inserts.
- [ ] 2.3 Verify both wrapper functions retain `SECURITY DEFINER` and the existing GRANT to `service_role`. Verify the per-stage detection functions are NOT modified by this migration beyond the changes in 1.1/1.2 (the resolver hoisting is in the wrapper, not the detection functions).

## 3. One-time backfill — supports proposal point #2

- [ ] 3.1 Create migration `supabase/migrations/<timestamp>_backfill_null_gclid_pending.sql` that runs `UPDATE gads_conversion_uploads u SET gclid = resolve_estimate_gclid(u.estimate_id) WHERE u.status = 'pending' AND u.gclid IS NULL AND u.conversion_type IN ('qualified_lead','converted_lead')`. Include a comment block recording the pre-update count of NULL-gclid pending rows for forensic reference.
- [ ] 3.2 Confirm idempotency by mentally re-applying: a second run over the same data should set the same values to the same values (no row count change). Document this in the migration header.

## 4. Upload edge function — per-stage window check + cadence — implements proposal points #3 and #7

- [ ] 4.1 In `supabase/functions/google-ads-conversion-upload/`, before each upload payload is constructed, look up `customer_gclids.first_seen_at` for the row's stored `gclid` (joined via the row's `customer_id` derived from `estimate_id`) and compare to the row's `conversion_datetime`. If the GCLID is NOT in window (`first_seen_at < conversion_datetime - 90 days`), omit the GCLID from the outbound payload (send as enhanced-conversion-only) WITHOUT modifying the stored row. Log a structured event for audit (`gclid_dropped_for_stage_window`).
- [ ] 4.2 If the lookup fails (no matching `customer_gclids` row for the stored gclid), also omit the GCLID and log `gclid_first_seen_unresolved`.
- [ ] 4.3 Locate the current cron schedule for `google-ads-conversion-upload` (check `supabase/config.toml`, any `pg_cron` migrations, and any deployment-time cron config).
- [ ] 4.4 Update the schedule to fire once per day at 09:00 America/New_York (after the discovery cron). If the discovery cron is on a different schedule, also document the recommended ordering.
- [ ] 4.5 Confirm the bulk-upload UI path (`POST /functions/v1/google-ads-conversion-upload` with `estimate_ids` in the body) remains functional and applies the same per-stage window check at upload time.

## 5. Conversions page badge — per-stage rendering — implements proposal point #6

- [ ] 5.1 In `horizon-dashboard/src/components/pages/ConversionsPage.tsx`, locate the GCLID badge JSX inside `PipelineRowItem` (currently keyed on `row.all_gclids?.length`). Refactor to read from a per-mode source:
  - `pre-discovery`: `row.all_gclids` (current behavior)
  - `booking`: `row.booking_gclid`
  - `qualified`: `row.qualified_gclid`
  - `converted`: `row.converted_gclid`
- [ ] 5.2 Render the primary `GCLID` badge only when the per-mode source is non-empty (non-null for stage modes; non-empty array for `pre-discovery`). Stage-mode badges show no `×N` count (always one value); `pre-discovery` continues to show `GCLID ×N`.
- [ ] 5.3 Update the badge tooltip: `pre-discovery` lists every value in `all_gclids`; stage modes show the single per-stage value.
- [ ] 5.4 Add a muted "n in pool" indicator that renders ONLY when (a) we're in a stage mode, (b) the stage's stored gclid is NULL, and (c) `row.all_gclids` is non-empty. Tooltip lists every value in the pool.
- [ ] 5.5 Visual QA at three densities: spot-check that the per-stage badge aligns with the column-level GCLID total in week and month rollups.

## 6. View / dashboard alignment — supports proposal points #4, #5, #6

- [ ] 6.1 Inspect `vw_conversion_candidates` for any computed column whose meaning depends on the prior qualified or converted gate definitions (e.g., `is_closed`). If any do, update the view definition; if none do, document that no view change was needed.
- [ ] 6.2 Inspect `vw_gads_upload_reconciliation_daily` for the same. Update or document.
- [ ] 6.3 No schema change is needed for the badge fix — `booking_gclid`, `qualified_gclid`, `converted_gclid`, `all_gclids` are already exposed by `vw_conversion_candidates`.

## 7. Tests — covers all proposal points #1–#7

- [ ] 7.1 Update `supabase/tests/gclid_lookback_window_test.sql` (or add a sibling test file) to cover the new DESC-in-window resolver: customer with multiple in-window GCLIDs returns the newest; customer with stale + fresh returns fresh; customer with only stale returns NULL.
- [ ] 7.2 Add a pgTAP test covering the new qualified gate: (a) estimate with `work_status = 'created job from estimate'` and at least one option that is both approved (`approval_status IN ('approved','pro approved')`) and priced (`total_amount > 0`) IS discovered as qualified; (b) estimate with priced options but no approved option is NOT discovered; (c) estimate with approved options but `total_amount = 0` is NOT discovered; (d) estimate with no options is NOT discovered.
- [ ] 7.3 Add a pgTAP test covering the new converted gate: estimate with a row in `jobs` referencing it IS discovered as converted (regardless of option `approval_status`); estimate with approved options but no job is NOT discovered.
- [ ] 7.4 Add a pgTAP test for `resolve_estimate_gclid(eid)`: anchor uses `GREATEST(e.updated_at, MAX(jobs.updated_at))`; returns newest in-window; returns NULL when none in window.
- [ ] 7.5 Add a pgTAP test covering shared-resolver discovery: when `discover_pending_conversions_for_estimate(eid)` inserts booking, qualified, AND converted rows in the same run, all three rows have identical `gclid` values.
- [ ] 7.6 Add a pgTAP test covering the re-attribution pass: a `pending` qualified row with `gclid IS NULL` and an in-window `customer_gclids` entry has its gclid populated by `discover_pending_conversions()`; an `uploaded` row with `gclid IS NULL` is left unchanged; a `pending` row with `conversion_type = 'booking_lead'` is left unchanged.
- [ ] 7.7 Add a pgTAP test covering backfill idempotency: run the backfill UPDATE twice and assert zero affected rows on the second run.
- [ ] 7.8 Add a Deno test (or extend the existing one) for the upload edge function's per-stage window check: a row with stored gclid in window sends GCLID; a row with stored gclid out-of-window for that stage sends payload WITHOUT gclid AND does NOT modify the stored row.

## 8. Local verification

- [ ] 8.1 Apply all migrations against the local Supabase instance (do NOT run against remote per safety rules — hand off to user for remote deploy).
- [ ] 8.2 Run `SELECT count(*) FROM gads_conversion_uploads WHERE status = 'pending' AND gclid IS NULL AND conversion_type IN ('qualified_lead','converted_lead');` before and after the backfill migration; record both numbers.
- [ ] 8.3 Run `SELECT * FROM discover_pending_conversions();` and confirm the qualified_leads / converted_leads counts now include rows whose estimates have `work_status = 'created job from estimate'` and an approved priced option.
- [ ] 8.4 Spot-check the previously diagnosed estimates (7363, 7372, 7406, **7536 — Darren Anthony**) and confirm:
  - Each has booking, qualified, converted rows with the same `gclid` value (or all-NULL for 7536, which has no attributable source data)
  - 7363 qualified row's `gclid` is now populated
  - 7372 qualified row now exists with the correct gclid
  - 7406 qualified row now exists with the correct gclid
  - 7536 qualified row now exists (gclid expected NULL — customer has no booking_tags, no callrail_leads, no `customer_gclids` entry; row should upload as enhanced-conversion-only, matching the existing converted_lead row)
- [ ] 8.5 In the dashboard, switch between conversion modes and confirm:
  - `pre-discovery` mode: badge still shows `GCLID ×N` from the pool
  - `qualified` mode: badge shows for rows where `qualified_gclid IS NOT NULL`; muted `n in pool` indicator appears for rows where it's NULL but the pool is non-empty
  - The week/month GCLID column total equals the count of visible badges (excluding the muted pool indicator)
- [ ] 8.6 Run all pgTAP tests under `supabase/tests/` and the upload edge-function tests; confirm green.

## 9. Handoff

- [ ] 9.1 Summarize for the user: number of NULL-gclid pending rows recovered by the backfill, number of newly-discoverable qualified rows under the new gate, list of migration files added, the badge-rendering change in the dashboard, and the recommended deploy order.
- [ ] 9.2 Flag the Smart Bidding learning-period implication for the marketing ops owner (qualified events will arrive earlier in the funnel than today; converted events will fire on job creation rather than option approval).
- [ ] 9.3 Hand off remote `supabase db push`, edge function deploy, and any cron schedule change to the user (do not run against remote per safety rules).

