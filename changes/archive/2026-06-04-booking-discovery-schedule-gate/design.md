## Context

`get_pending_booking_lead_conversions()` currently treats an estimate as a `booking_lead` whenever it carries any attribution signal, dated at `estimates.created_at`. We are tightening this to a **schedule gate** (`scheduled_start` present AND an assigned employee) using durable signals, and dropping the attribution-signal requirement from eligibility (kept as commented-out code).

The gate depends on `schedule.scheduled_start`, which the HCP `/estimates` payload returns but the bulk importer **discards** — `transformSchedule` in `import-estimates.ts` is defined but never called. The `schedules` table is therefore only populated by `hcp-booking` (≈106 estimates) and a frozen, heavily-duplicated Dec-2025 backfill (`sched_est_<id>_<ts>`, ~276 rows/estimate over ~1,019 estimates). So the import must be fixed and the data backfilled/cleaned before the gate can be relied on.

Both discovery entry points — the bulk `gads_discover_pending_conversions()` and on-demand `discover_pending_conversions_for_estimate()` — `SELECT … FROM get_pending_booking_lead_conversions()`, so there is a single function to change.

## Goals / Non-Goals

**Goals:**
- Gate `booking_lead` discovery on `schedules.scheduled_start IS NOT NULL` AND a non-empty `estimate_assignments`.
- Keep `conversion_datetime = estimates.created_at` unchanged.
- Preserve the attribution source-signal conditions as commented-out code for future re-add.
- Make the estimate import populate `schedules` deterministically; backfill existing estimates; remove the legacy duplicate rows.
- Rename the unpushed migration to reflect its new purpose.

**Non-Goals:**
- Importing `work_timestamps` (still orphaned — explicitly out of scope).
- Importing/repairing **job** schedules (`sched_job_*`) — scope is estimates only.
- Capturing the moment an estimate *becomes* scheduled (impossible without an HCP webhook — explicitly ruled out).
- Changing upload mechanics or `conversion_datetime`.

## Decisions

### 1. Gate lives in the single SQL function, source signals commented out
Rewrite the `WHERE` of `get_pending_booking_lead_conversions()` to:
```
WHERE EXISTS (SELECT 1 FROM schedules s
              WHERE s.estimate_id = e.id AND s.scheduled_start IS NOT NULL)
  AND EXISTS (SELECT 1 FROM estimate_assignments a WHERE a.estimate_id = e.id)
  AND NOT EXISTS (SELECT 1 FROM gads_conversion_uploads u
                  WHERE u.estimate_id = e.id::text AND u.conversion_type = 'booking_lead')
-- Retained for future re-add (do not delete):
--   AND (
--        e.is_booking_form = true
--        OR EXISTS (SELECT 1 FROM booking_tags ...)
--        OR EXISTS (SELECT 1 FROM callrail_leads ...)
--        OR EXISTS (SELECT 1 FROM customer_gclids ...)
--   )
```
The `NOT EXISTS` already-uploaded guard and the `conversion_datetime = e.created_at` selection are unchanged. *Alternative considered:* gate on `estimates.work_status = 'scheduled'` (original request) — rejected: it is transient/point-in-time, so conversions age out and are lost if the cron misses the window.

### 2. GCLID resolution kept (3-branch COALESCE)
The `COALESCE(booking_tags.gclid, callrail_leads.gclid, customer_gclids.gclid)` resolver stays — it derives a *value*, not eligibility. So the `customer_gclids` change from the unpushed migration is split: its **eligibility** OR-branch is commented out, its **resolution** fallback stays.

### 3. Un-orphan schedule import with a deterministic id
In `import-estimates.ts`: change `transformSchedule` to emit id `sch_${estimateId}` (matching `hcp-booking`) and return `null` when `schedule.scheduled_start` is absent; add a `schedules` entry to the Phase 7 `batchUpsertRelated` map with `conflictColumns: 'id'` (upsert). This makes the import idempotent and convergent with `hcp-booking` on one row per estimate. *Alternative considered:* keep the `sched_est_<id>_<Date.now()>` id — rejected: it is the root cause of the 276×/estimate duplication.

### 4. Backfill by re-running the importer
Once the fix is deployed, run the estimate import across all pages to populate `schedules` for existing estimates from current HCP data. *Alternative considered:* a bespoke backfill script — rejected: the importer already fetches the full payload; reuse it.

### 5. Remove legacy duplicates after backfill
One-time SQL: `DELETE FROM schedules WHERE id LIKE 'sched_est_%'` after the backfill is verified. Backfill recreates accurate deterministic rows for estimates still scheduled in HCP, so the legacy rows are redundant. Satisfies the spec's "at most one row per estimate."

### 6. Sequencing (critical)
`schedules` must be populated **before** discovery relies on the gate, or booking discovery drops to ~0 during the gap. Order: (1) deploy import fix → (2) backfill → (3) verify coverage → (4) dedupe legacy rows → (5) apply the renamed gate migration. Until step 5, the live function keeps its current behavior.

### 7. Migration rename
Rename `20260526000002_booking_lead_repeat_customer_gclid.sql` → `20260526000002_booking_lead_schedule_gate.sql` (timestamp kept to preserve ordering; safe because unapplied), and rewrite its header comment.

## Risks / Trade-offs

- **Booking discovery stalls if the gate is applied before backfill completes** → enforce the sequencing in Decision 6; verify `schedules` coverage before applying the migration.
- **Backfill misses estimates whose HCP schedule no longer exists** → those lose a (stale) `scheduled_start`. Acceptable: the legacy value was frozen Dec-2025 data anyway. Verify counts before the `DELETE`.
- **Decoupling eligibility from attribution surfaces null-gclid booking_leads** (non-PPC/walk-in scheduled estimates) → see Open Questions; they may still upload via enhanced-conversion identifiers (email/phone) that `pickup.ts` already fetches.
- **`transformSchedule` rewrites `created_at` on every upsert** (timestamp without tz) → harmless; `updated_at` semantics are approximate.

## Open Questions

- **Cancellation exclusion** (default = include): `scheduled_start` persists after cancellation, so `user canceled` / `pro canceled` estimates currently qualify. Specs encode "include" as the default; whether to add `work_status NOT IN ('user canceled','pro canceled')` is unresolved.
- **Null-gclid booking_leads downstream**: do these upload via enhanced-conversion identifiers (email/phone), fail, or should they be filtered/marked before upload? To confirm against `payload-builder.ts` behavior.
