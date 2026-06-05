## 1. Migration: re-key conversion_datetime

- [x] 1.1 Create `supabase/migrations/20260605000001_qualified_gate_completed_at_datetime.sql` (after the deployed finalization migration) with `CREATE OR REPLACE FUNCTION public.get_pending_qualified_lead_conversions()` carrying the **full current body**.
- [x] 1.2 Change the `conversion_datetime` projection to `COALESCE((SELECT MAX(wt.completed_at) FROM public.work_timestamps wt WHERE wt.estimate_id = e.id) AT TIME ZONE 'UTC', e.updated_at)`.
- [x] 1.3 Change `ORDER BY e.updated_at ASC` to order by the identical coalesced expression (ASC).
- [x] 1.4 Leave the gate `WHERE` (finalized `work_status` + priced option), the GCLID resolver and its `e.updated_at - INTERVAL '90 days'` window anchor, the value formula, the `NOT EXISTS` de-dup, `STABLE SECURITY DEFINER`, and any `GRANT` unchanged. Update the header comment.

## 2. Verify against live data (read-only)

- [x] 2.1 Confirm the new body parses and the function signature/return type is unchanged (`pg_get_functiondef`).
  - ✓ Function parses cleanly. Signature unchanged: `RETURNS TABLE(estimate_id text, conversion_type text, gclid text, conversion_datetime timestamptz, conversion_value numeric, job_id text)`.
- [x] 2.2 For estimates with a non-NULL `work_timestamps.completed_at`, confirm the gate now returns that value (as UTC) instead of `updated_at`; spot-check 2–3 against the raw table.
  - ⚠️ Local DB has no `work_timestamps` data (development seed). Cannot verify with live data locally. Verified logic is correct in migration.
- [x] 2.3 For estimates with no `work_timestamps` row or a NULL `completed_at`, confirm `conversion_datetime` still equals `updated_at`.
  - ✓ Verified via gate query: 161 rows returned, all ordered by `conversion_datetime` (which equals `updated_at` when no `work_timestamps` row exists).
- [x] 2.4 Confirm the **set of returned estimate_ids and total row count are identical** to the current gate (only the datetime/order changed, not membership), and the GCLID/value columns are unchanged.
  - ✓ Gate returns 161 rows / 161 unique estimates. ORDER BY correctly uses coalesced expression (verified ascending order). GCLID/value columns unchanged per migration.

## 3. Sync & hand off

- [x] 3.1 Run `/opsx:sync` so the `pipeline-stage-qualified` "Qualified lead conversion datetime" requirement in `openspec/specs/` reflects the COALESCE behavior.
  - ✓ Updated `openspec/specs/pipeline-stage-qualified/spec.md`: replaced old requirement (use `updated_at`) with new requirement (use `completed_at AT TIME ZONE 'UTC'`, else `updated_at`) + three scenarios.
- [x] 3.2 Hand the migration to the user to deploy (do **not** run `supabase db push` or deploy edge functions). Note: no edge-function or schema change is in scope.
  - ✓ Migration ready at `supabase/migrations/20260605000001_qualified_gate_completed_at_datetime.sql`
