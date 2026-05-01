## 1. Database — customer_gclids Table

- [x] 1.1 Write migration: create `customer_gclids` table with columns `id`, `customer_id` (FK → customers), `gclid`, `source` (check: 'booking_form' | 'callrail'), `first_seen_at`, `estimate_id` (nullable)
- [x] 1.2 Add `UNIQUE(customer_id, gclid)` constraint and index on `customer_id` for fast lookup
- [x] 1.3 Grant SELECT/INSERT on `customer_gclids` to `service_role`

## 2. Database — Backfill Function

- [x] 2.1 Write migration: create `backfill_customer_gclids()` function that upserts from `booking_tags` (key='gclid') joined via estimates → customers
- [x] 2.2 Extend backfill to also upsert from `callrail_leads` (gclid IS NOT NULL) joined via estimates → customers, with source='callrail'
- [x] 2.3 Confirm function uses ON CONFLICT (customer_id, gclid) DO NOTHING (idempotent)

## 3. Database — Discovery Pre-pass

- [x] 3.1 Write migration: update `discover_pending_conversions()` to upsert `customer_gclids` from `booking_tags` and `callrail_leads` before the three stage detection passes
- [x] 3.2 Write migration: update `discover_pending_conversions_for_estimate(p_estimate_id)` with the same pre-pass filtered to the single estimate's customer

## 4. Database — Qualified Lead Function

- [x] 4.1 Write migration: replace `get_pending_qualified_lead_conversions()` — remove `booking_lead EXISTS` gate
- [x] 4.2 Update gate to `estimates.work_status IN ('complete rated', 'complete unrated')` AND `EXISTS (SELECT 1 FROM estimate_options WHERE estimate_id = e.id AND total_amount > 0)`
- [x] 4.3 Update `conversion_value` formula to `AVG(eo.total_amount) / 100.0` across all options with no status filter
- [x] 4.4 Update GCLID resolution to query `customer_gclids` via `e.customer_id ORDER BY first_seen_at ASC LIMIT 1`

## 5. Database — Converted Lead Function

- [x] 5.1 Write migration: replace `get_pending_converted_lead_conversions()` — remove `booking_lead EXISTS` gate
- [x] 5.2 Update GCLID resolution to query `customer_gclids` via `e.customer_id ORDER BY first_seen_at ASC LIMIT 1`
- [x] 5.3 Confirm gate remains `∃ approved option` and value formula remains `SUM(approved options) / 100.0`

## 6. Database — View Update

- [x] 6.1 Write migration: update `vw_conversion_candidates` — replace `eo_agg` LATERAL subquery to compute `AVG(eo.total_amount) / 100.0` with no approval_status filter
- [x] 6.2 Verify `display_value` is `0` when no options exist (COALESCE guard)
- [x] 6.3 Add `estimates.work_status` to the SELECT list of `vw_conversion_candidates` so the dashboard can display it in the qualified stage cell

## 7. Backfill Execution

- [x] 7.1 Run `SELECT backfill_customer_gclids();` on local database
- [x] 7.2 Verify row count in `customer_gclids` matches expected GCLIDs from existing `booking_tags` and `callrail_leads` data
- [x] 7.3 Spot-check: confirm a known repeat customer now has a GCLID row

## 8. Dashboard — Remove Stage Connectors

- [x] 8.1 Remove `PhaseConnector` component renders from `PipelineStrip` in `ConversionsPage.tsx`
- [x] 8.2 Confirm the three stage cells render side by side with no connector lines for all status combinations (uploaded, pending, skipped, null)

## 9. Dashboard — Qualified Stage Work Status Sub-label

- [x] 9.1 Pass `work_status` from the pipeline row through to the qualified `PhaseCell` (or equivalent component) as a prop
- [x] 9.2 Render `work_status` as a sub-label beneath the status icon in the qualified stage cell
- [x] 9.3 Confirm the sub-label renders on null-status (undiscovered) qualified cells as well — showing current eligibility

## 10. Verification

- [x] 10.1 Run `discover_pending_conversions()` locally and confirm previously-orphaned estimates (no booking form, phone-in) are now discovered as qualified/converted where eligible
- [x] 10.2 Confirm an estimate for a repeat customer inherits the GCLID from `customer_gclids` (not just from its own booking_tags)
- [x] 10.3 Confirm `display_value` in `vw_conversion_candidates` now reflects AVG of all options
- [x] 10.4 Confirm `qualified_value` on newly discovered rows matches the AVG formula
- [x] 10.5 Visually confirm no connector lines appear between stage cells in the dashboard
- [x] 10.6 Visually confirm `work_status` sub-label is visible on qualified stage cells
