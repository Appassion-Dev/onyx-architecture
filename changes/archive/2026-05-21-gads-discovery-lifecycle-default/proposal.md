## Why

After the recent Google Ads upload edge function refactor, the uploader picks up rows by filtering on the new `lifecycle` column (`lifecycle IN ('queued', 'retrying')`). The two discovery functions (`discover_pending_conversions` and `discover_pending_conversions_for_estimate`) were never updated when the `lifecycle` column was introduced — they still insert with `status = 'pending'` only and leave `lifecycle = NULL`. Newly discovered conversions are therefore invisible to the new uploader and never get sent to Google Ads.

## What Changes

- Backfill any existing rows in `gads_conversion_uploads` that have `lifecycle = NULL`, mapping `upload_attempts = 0` → `'queued'` and `upload_attempts > 0` → `'retrying'` (mirrors the original lifecycle backfill mapping).
- Add a column-level `DEFAULT 'queued'` on `gads_conversion_uploads.lifecycle` as a safety net for any future inserter.
- Rewrite both discovery functions (`discover_pending_conversions` and `discover_pending_conversions_for_estimate`) so the INSERT column list explicitly includes `lifecycle` with literal `'queued'`. This removes the reliance on the column default and makes the assignment visible in the function body.
- Function bodies are otherwise byte-identical to the versions in `20260504000002_gads_conversion_datetime_type.sql` — only the INSERT column list and SELECT projection change.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `conversion-populate`: Discovery wrapper `discover_pending_conversions()` must populate `lifecycle = 'queued'` on inserted rows so the new disposition-driven uploader can pick them up.
- `per-estimate-discovery`: Per-estimate variant `discover_pending_conversions_for_estimate(text)` must also populate `lifecycle = 'queued'` (mirrors the wrapper's behavior).

## Impact

- **Code**: `supabase/migrations/20260520000001_gads_lifecycle_default.sql` (already added) and `supabase/migrations/20260520000002_gads_discover_set_lifecycle.sql` (new).
- **Data**: One-time backfill of any `lifecycle = NULL` rows (latest count seen was 18 stranded `pending` rows plus subsequent fresh inserts).
- **Behavior**: Re-establishes the discovery → upload handoff. No API or external interface change. The legacy `status = 'pending'` is unchanged and continues to satisfy the `(lifecycle, status)` parallel-write CHECK constraint introduced in `20260518000001`.
- **Risk**: Low. The `'queued'` literal is already allowed by both the lifecycle CHECK constraint and the parallel-write CHECK constraint. The backfill is idempotent (`WHERE lifecycle IS NULL`).
