## Why

`gads_conversion_uploads.conversion_datetime` is typed as `text` but holds ISO 8601 timestamps derived from `timestamptz` columns. This causes range queries (including the new 90-day upload window filter) to rely on accidental lexicographic ordering rather than proper temporal semantics. Fixing the type makes the column semantically correct, enables real index range scans, and removes an implicit cast dependency throughout the pipeline.

## What Changes

- `gads_conversion_uploads.conversion_datetime` column type changed from `text` to `timestamptz`
- `discover_pending_conversions()` function updated to remove the now-unnecessary `::text` casts on insert (value flows directly as `timestamptz`)
- The v2 prepass discover function (`20260501000003`) updated identically
- The 90-day expiry filter in the edge function remains correct — PostgREST comparison against an ISO string works against a real `timestamptz` column

## Capabilities

### New Capabilities
<!-- None — this is a schema correction, no new user-facing capability -->

### Modified Capabilities
- `conversion-upload`: The `conversion_datetime` field stored in `gads_conversion_uploads` changes type from `text` to `timestamptz`. The value written and read is semantically identical; the wire format from PostgREST changes from `"2026-04-06 02:13:47+00"` to `"2026-04-06T02:13:47+00:00"`. Existing consumers (`getWeekInfo`, `new Date()`) handle both formats.

## Impact

- **Migration**: Single `ALTER TABLE ... ALTER COLUMN ... TYPE timestamptz USING ...` — safe on existing data since all values are valid ISO strings
- **DB functions**: `discover_pending_conversions()` — remove `::text` cast on `conversion_datetime` in all three insert blocks (booking, qualified, converted)
- **Edge function**: No change — comparison uses ISO string against timestamptz column which PostgREST handles correctly
- **Dashboard (ConversionsPage)**: No change — `formatDateTime()` and `getWeekInfo()` both handle the new ISO 8601 wire format natively
- **Diagnostic queries**: `::timestamptz` cast in ad-hoc queries can be dropped after migration
