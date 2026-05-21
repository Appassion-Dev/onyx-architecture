## Context

The Google Ads conversion pipeline has two halves:

1. **Discovery** — `discover_pending_conversions()` (cron-driven) and `discover_pending_conversions_for_estimate(text)` (UI on-demand) read from `get_pending_{booking,qualified,converted}_lead_conversions()` and insert new rows into `gads_conversion_uploads` with `status = 'pending'`.
2. **Upload** — the `google-ads-conversion-upload` edge function selects rows from `gads_conversion_uploads`, batches them, and calls the Google Ads API.

The recent disposition / lifecycle refactor (migrations `20260518000001`..`20260518000005`) introduced a new state-machine column `lifecycle` on `gads_conversion_uploads` with values `queued`, `sending`, `sent`, `retrying`, `needs-attention`, `failed`, `excluded`, `expired`. A parallel-write `CHECK` constraint links `lifecycle` ↔ legacy `status` (`queued` pairs with `pending`, etc.). A backfill migration populated existing rows.

The new uploader picks up work via `pickup.ts`:

```ts
.in("lifecycle", ["queued", "retrying"])
```

The discovery functions were **not** updated — they were last redefined in `20260504000002_gads_conversion_datetime_type.sql`, before the lifecycle column existed. Their INSERT column lists omit `lifecycle`, and the column has no DEFAULT. New rows therefore land with `lifecycle = NULL` and are silently filtered out by the uploader.

Observed state at investigation time:

```
lifecycle | status   | count
----------+----------+-------
expired   | expired  | 10308
failed    | failed   | 36
sent      | uploaded | 2289
NULL      | pending  | 18      ← stranded discoveries
```

## Goals / Non-Goals

**Goals:**
- Restore the discovery → upload handoff so newly discovered conversions are picked up by the new uploader.
- Make the lifecycle assignment **visible at the call site** (inside the discovery functions), not buried in column metadata.
- Backfill the stranded `lifecycle = NULL` rows so the next uploader run drains them.

**Non-Goals:**
- Re-spec the upload-side lifecycle state machine (already covered by the disposition migrations).
- Refactor the `get_pending_*_conversions()` helpers — they return projection rows, not lifecycle.
- Update the `conversion-upload` capability spec to reflect the new lifecycle column — that's a separate doc-debt change, not in scope here.
- Drop the legacy `status` column. The (`lifecycle`, `status`) parallel-write CHECK is intentional for the one-release deprecation window.

## Decisions

### Decision 1: Set `lifecycle = 'queued'` explicitly in the INSERT column list

**What:** Add `lifecycle` to the column list of all six `INSERT INTO gads_conversion_uploads` statements across both discovery functions and project the literal `'queued'` for it.

**Alternatives considered:**
- *Rely on column DEFAULT only.* Initially tried in `20260520000001_gads_lifecycle_default.sql`. Fresh discoveries continued to land with `lifecycle = NULL` after that migration shipped, suggesting either the migration wasn't applied or the DEFAULT didn't take effect in the SECURITY DEFINER context. Either way, an explicit value removes the doubt.
- *Add a BEFORE INSERT trigger mapping `status → lifecycle`.* More machinery than needed, hides the assignment further from readers of the discovery functions, and creates a second source of truth that can drift from the CHECK constraint.

**Rationale:** The discovery functions are the canonical inserter for new rows, and `lifecycle` is now load-bearing for the new uploader. Putting the value in the SQL is the smallest change that closes the gap and is the easiest for the next person to read and reason about. The DEFAULT from `20260520000001` is retained as a safety net but is no longer the primary mechanism.

### Decision 2: Backfill via UPDATE in the same migration

**What:** Open the migration with `UPDATE … SET lifecycle = CASE WHEN upload_attempts = 0 THEN 'queued' ELSE 'retrying' END WHERE lifecycle IS NULL`.

**Rationale:** The mapping matches the original lifecycle backfill (`20260518000004_gads_lifecycle_backfill.sql`) so any row that slipped through the discovery gap is treated consistently with historical rows. The `WHERE lifecycle IS NULL` clause makes it idempotent — safe to re-run after the first apply.

### Decision 3: Recreate both discovery functions in full

**What:** `CREATE OR REPLACE FUNCTION` for both `discover_pending_conversions()` and `discover_pending_conversions_for_estimate(text)`, with bodies byte-identical to the `20260504000002` versions except for the INSERT column lists.

**Alternatives considered:**
- *Use `ALTER FUNCTION`.* Postgres doesn't allow body changes via ALTER FUNCTION — only attributes.
- *Wrap the existing functions and patch only the INSERTs in a second function.* Adds indirection for no real benefit.

**Rationale:** Full re-creation is the standard pattern for plpgsql definitions in this repo and keeps the diff easy to review against the prior version.

## Risks / Trade-offs

- **Risk: The CHECK constraint rejects the new INSERT.** → Mitigation: the `(lifecycle = 'queued' AND status = 'pending')` arm of the parallel-write CHECK is explicitly allowed by `20260518000001_gads_error_dispositions_schema.sql:91-92`. Both lifecycle and status are written in the same INSERT, so no transient invalid state.
- **Risk: A future migration recreates the discovery functions and drops the explicit `lifecycle` projection again.** → Mitigation: the column DEFAULT from `20260520000001` is retained as a safety net, so even if the explicit projection is lost, new rows still get `'queued'`.
- **Trade-off: Two safety mechanisms (explicit + DEFAULT) duplicate the source of truth.** → Accepted. The DEFAULT is a cheap insurance policy and doesn't conflict with the explicit value (both are `'queued'`). If they ever disagree, the explicit value wins.
- **Risk: The backfill races with the discovery cron.** → Mitigation: a row can only be in `(NULL, 'pending')` before the new discovery is in place. Once both the backfill and the function replacement are committed in the same migration transaction, no new NULL rows can appear, and the backfill drains the historical ones in the same statement.
