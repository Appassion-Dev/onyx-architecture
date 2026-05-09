## Context

`gads_conversion_uploads.conversion_datetime` was defined as `text NOT NULL` in the original schema migration (`20260330000001`) with the comment "formatted string sent to Ads API". This made sense at creation time — the value was always handed to `formatConversionDateTime()` in the edge function before being sent to Google.

Over time the column has grown a second role: it's the temporal anchor for the 90-day upload window filter, for date grouping in the dashboard, and for the `booking_datetime / qualified_datetime / converted_datetime` columns exposed in pipeline views. All of these benefit from true timestamp semantics.

The discover functions (`discover_pending_conversions` and the prepass variant) explicitly cast `timestamptz → text` on insert, which is the only seam that needs to change.

## Goals / Non-Goals

**Goals:**
- Change `conversion_datetime` column type to `timestamptz`
- Remove `::text` casts from all `discover_pending_conversions` variants so values flow as native timestamps
- Ensure the 90-day filter in the edge function works via true timestamp comparison
- Zero downtime migration on existing production data

**Non-Goals:**
- Changing `formatConversionDateTime()` in the edge function — it already receives the value as a string from PostgREST and reformats it for Google's API
- Adding indexes on `conversion_datetime` — not in scope (can be a follow-on)
- Changing any dashboard component code — confirmed safe as-is

## Decisions

**Decision 1: Single migration with USING clause**

Use `ALTER TABLE ... ALTER COLUMN ... TYPE timestamptz USING conversion_datetime::timestamptz` rather than a multi-step rename/backfill/rename strategy.

_Rationale_: All existing values in the column are valid ISO 8601 strings (confirmed by the data — they come from `estimates.created_at`, `estimates.updated_at`, `jobs.updated_at` which are all `timestamptz`). Postgres casts them correctly. A multi-step migration adds risk and complexity for no benefit.

_Alternative considered_: Add a new `timestamptz` column, dual-write, backfill, swap. Rejected — the table has no active concurrent writers other than `discover_pending_conversions`, so a direct `ALTER COLUMN` is safe and atomic.

**Decision 2: Drop `::text` casts in the discover functions via `CREATE OR REPLACE`**

Replace the function bodies in the same migration file using `CREATE OR REPLACE FUNCTION`. Since the column is now `timestamptz`, the cast is simply removed — no other logic changes.

_Rationale_: The `::text` cast was the only adaptation point. Removing it lets the assignment be type-correct end to end: `timestamptz` source → `timestamptz` column.

**Decision 3: No change to the edge function**

The edge function receives `conversion_datetime` as a JSON string from PostgREST (PostgREST serializes `timestamptz` as ISO 8601). The TypeScript type `string | null` remains correct. `new Date(iso)` and the 90-day cutoff `.gte("conversion_datetime", cutoffIso)` both work correctly against a `timestamptz` column.

_Alternative considered_: Update `PendingRow.conversion_datetime` to a more specific type. Rejected — it's not needed and the interface is accurate.

## Risks / Trade-offs

**[Risk] Migration locks the table briefly** → Mitigation: `ALTER COLUMN TYPE` on Postgres 17 acquires `ACCESS EXCLUSIVE` lock but completes in milliseconds for a column with a trivial cast. The `discover_pending_conversions` cron runs every 15 minutes; the migration window is well within a safe gap. Run during off-hours if preferred.

**[Risk] A stored value is not a valid ISO timestamp** → Mitigation: Extremely low — all values originate from `timestamptz` source columns and were cast through `::text` which always produces a valid parseable string. The `USING` clause will fail explicitly if any value is unparseable, making the failure observable and safe (no silent data corruption).

**[Risk] Dashboard format change breaks display** → Mitigation: Analyzed and confirmed safe. `formatDateTime(iso)` uses `new Date()`, `getWeekInfo()` normalizes Postgres format already. The format change from `"2026-04-06 02:13:47+00"` to `"2026-04-06T02:13:47+00:00"` is transparent to all consumers.

## Migration Plan

1. Write migration `20260504000002_gads_conversion_datetime_type.sql`:
   - `ALTER TABLE gads_conversion_uploads ALTER COLUMN conversion_datetime TYPE timestamptz USING conversion_datetime::timestamptz`
   - `CREATE OR REPLACE FUNCTION discover_pending_conversions()` — remove `::text` casts
   - Covers both the original function and the prepass variant in `20260501000003`

2. Apply locally: `supabase migration up`

3. Verify with: `\d gads_conversion_uploads` — confirm `timestamptz` type

4. Deploy to production via the Supabase dashboard SQL editor (since `supabase db push` is not used per safety rules)

**Rollback**: `ALTER COLUMN TYPE text USING conversion_datetime::text` and restore the `::text` casts. Trivially reversible.

## Open Questions

None — the explore session fully resolved all unknowns before this proposal.
