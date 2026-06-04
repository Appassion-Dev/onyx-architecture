## 1. Schedule import fix (code)

- [x] 1.1 In `import-estimates.ts`, change `transformSchedule` to emit the deterministic id `sch_${estimateId}` (matching `hcp-booking`) and return `null` when `schedule.scheduled_start` is null/absent
- [x] 1.2 Add a `schedules` entry to the Phase 7 `batchUpsertRelated` map — `extractRecords: (e) => { const s = transformSchedule(e.schedule, e.id); return s ? [s] : []; }`, `conflictColumns: 'id'`, upsert (default)
- [x] 1.3 Confirm `transformSchedule` is now called (no longer orphaned); leave `transformWorkTimestamps` untouched (out of scope) and note it stays orphaned

## 2. Gate migration (file)

- [x] 2.1 Rename `supabase/migrations/20260526000002_booking_lead_repeat_customer_gclid.sql` → `20260526000002_booking_lead_schedule_gate.sql`
- [x] 2.2 Rewrite the header comment to describe the schedule gate (replacing the repeat-customer-GCLID rationale)
- [x] 2.3 Replace the `WHERE` eligibility in `get_pending_booking_lead_conversions()` with the schedule gate: `EXISTS(schedules.scheduled_start IS NOT NULL)` AND `EXISTS(estimate_assignments)`; keep the `NOT EXISTS` already-uploaded guard
- [x] 2.4 Comment out (retain, do not delete) the attribution source-signal OR-block, including the `customer_gclids` **eligibility** branch
- [x] 2.5 Keep the 3-branch GCLID `COALESCE` resolver (`booking_tags`, `callrail_leads`, `customer_gclids`) and keep `conversion_datetime = e.created_at`
- [x] 2.6 Keep `GRANT EXECUTE ON FUNCTION ... TO "service_role"`

## 3. Live-system rollout (operational — requires explicit go-ahead; run strictly in order)

- [x] 3.1 Deploy `hcp-import-data` with the import fix
- [x] 3.2 Backfill: run the estimate import across all pages to populate `schedules` from current HCP data
- [x] 3.3 Verify `schedules` coverage (one deterministic `sch_<id>` row per genuinely-scheduled estimate) before any deletion
- [x] 3.4 Dedupe legacy rows: `DELETE FROM schedules WHERE id LIKE 'sched_est_%'` (only after 3.3 passes)
- [x] 3.5 Apply the renamed gate migration (ONLY after `schedules` is populated, to avoid a window of zero booking discovery)
- [x] 3.6 Verify `booking_lead` discovery volume on the new gate matches expectations
