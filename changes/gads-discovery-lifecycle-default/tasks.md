## 1. Pre-flight diagnostics

- [x] 1.1 Confirm stranded rows exist: `SELECT lifecycle, status, COUNT(*) FROM gads_conversion_uploads GROUP BY 1, 2 ORDER BY 1, 2;` and verify the `(NULL, 'pending')` bucket is non-empty.
- [x] 1.2 Re-read the most recent definitions of `discover_pending_conversions()` and `discover_pending_conversions_for_estimate(text)` in `supabase/migrations/20260504000002_gads_conversion_datetime_type.sql` to capture the byte-for-byte baseline that the new migration replaces.
- [x] 1.3 Confirm the parallel-write CHECK constraint allows `(lifecycle = 'queued', status = 'pending')` by reading `supabase/migrations/20260518000001_gads_error_dispositions_schema.sql:91-92`.

## 2. Migration: column default safety net

- [x] 2.1 Create `supabase/migrations/20260520000001_gads_lifecycle_default.sql`.
- [x] 2.2 In that migration, idempotently backfill `lifecycle = NULL` rows using the `upload_attempts = 0 → 'queued'`, else `'retrying'` mapping (matches `20260518000004_gads_lifecycle_backfill.sql`).
- [x] 2.3 In the same migration, `ALTER TABLE public.gads_conversion_uploads ALTER COLUMN lifecycle SET DEFAULT 'queued';`.

## 3. Migration: explicit lifecycle in discovery functions

- [x] 3.1 Create `supabase/migrations/20260520000002_gads_discover_set_lifecycle.sql`.
- [x] 3.2 Open the migration with the same idempotent NULL backfill (covers any rows that slipped in between migration 20260520000001 and 20260520000002).
- [x] 3.3 `CREATE OR REPLACE FUNCTION public.discover_pending_conversions()` with the body from `20260504000002` modified so each of the three `INSERT INTO gads_conversion_uploads (...)` statements includes `lifecycle` in the column list and projects literal `'queued'`.
- [x] 3.4 `CREATE OR REPLACE FUNCTION public.discover_pending_conversions_for_estimate(text)` with the same explicit-lifecycle change applied to its three INSERTs.
- [x] 3.5 Re-`GRANT EXECUTE` on both functions to `service_role`.

## 4. Verification

- [x] 4.1 Apply migrations (`supabase db push` or equivalent for the target environment).
- [x] 4.2 Re-run the diagnostic query from 1.1 and confirm the `(NULL, 'pending')` bucket is gone.
- [x] 4.3 Trigger discovery once (either wait for the cron tick or call `SELECT * FROM discover_pending_conversions();` manually) and confirm any newly inserted rows have `lifecycle = 'queued'`.
- [x] 4.4 Trigger the upload edge function once and confirm the previously stranded rows transition from `(queued, pending)` to `(sent, uploaded)` (or to one of the disposition lifecycles — `retrying`, `needs-attention`, `failed` — depending on Google Ads response).

## 5. Documentation & follow-up

- [x] 5.1 Note in the team channel that any in-flight branches that recreate either discovery function must keep `lifecycle = 'queued'` in their INSERT column lists.
- [x] 5.2 (Optional follow-up, out of scope for this change) Update `openspec/specs/conversion-upload/spec.md` to reflect the lifecycle-based pickup rules introduced by the disposition refactor.
