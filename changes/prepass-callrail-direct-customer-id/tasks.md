## 1. Pre-deploy measurement

- [ ] 1.1 Run the diagnostic query from design.md §Migration Plan to count rows newly eligible. Record the result so the backfill delta after deploy can be sanity-checked.
- [ ] 1.2 Confirm the latest definitions of `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` live in `supabase/migrations/20260520000002_gads_discover_set_lifecycle.sql` (Source 2 blocks at lines 58-70 and 183-195). If a newer migration has been added since (e.g. via `conversion-attribution-overhaul`), rebase against it before writing the new migration.

## 2. Migration

- [ ] 2.1 Create a new migration under `supabase/migrations/` (timestamped after the current head) titled `<timestamp>_prepass_callrail_direct_customer_id.sql`.
- [ ] 2.2 In the migration, `CREATE OR REPLACE FUNCTION public.discover_pending_conversions()` with the full current body, replacing the Source 2 block so it reads `FROM callrail_leads cl WHERE cl.gclid IS NOT NULL AND cl.customer_id IS NOT NULL`, selects `cl.customer_id` (not `e.customer_id`) and `cl.estimate_id` (not `e.id::text`), and drops the `JOIN estimates` entirely. Leave Source 1 (booking_tags) unchanged.
- [ ] 2.3 In the same migration, `CREATE OR REPLACE FUNCTION public.discover_pending_conversions_for_estimate(text)` with the full current body, replacing the Source 2 block so it reads `FROM callrail_leads cl WHERE cl.gclid IS NOT NULL AND cl.customer_id = v_customer_id`, selects from `cl` directly, and drops the `JOIN estimates`. Leave Source 1 unchanged.
- [ ] 2.4 In the same migration, `CREATE OR REPLACE FUNCTION public.backfill_customer_gclids()` with the full current body, replacing the Source 2 block in the same way as 2.2. Preserve the return type and GET DIAGNOSTICS counts so the function's contract is unchanged.
- [ ] 2.5 Re-issue the existing GRANTs for all three functions to `service_role` (CREATE OR REPLACE FUNCTION does not re-grant on Supabase Postgres in all cases — verify by checking grants on a local apply).

## 3. Tests

- [ ] 3.1 Add a pgTAP test under `supabase/tests/` named `customer_gclids_prepass_callrail_customer_id_test.sql`.
- [ ] 3.2 In the new test, seed a `customers` row, an `estimates` row, and a `callrail_leads` row with `customer_id = <customer>`, `estimate_id = NULL`, `gclid = 'test-gclid-no-estimate'`. Call `SELECT discover_pending_conversions_for_estimate(<estimate id>)` and assert `customer_gclids` contains the GCLID with `source = 'callrail'` and `estimate_id IS NULL`.
- [ ] 3.3 In the same test, seed a second `callrail_leads` row with `customer_id = NULL`, `gclid = 'test-gclid-no-customer'`. Re-run the discovery and assert no row is inserted for this GCLID.
- [ ] 3.4 In the same test, call `SELECT * FROM backfill_customer_gclids()` and assert the `callrail_rows` count reflects the seeded rows (idempotency: second call returns 0 newly inserted CallRail rows).
- [ ] 3.5 Run the existing GCLID lookback / discovery pgTAP tests under `supabase/tests/` and confirm they remain green (no semantic change to the rest of the pre-pass).

## 4. Deploy

- [ ] 4.1 Push the migration to staging. Run `SELECT * FROM backfill_customer_gclids();` and capture the returned `(booking_form_rows, callrail_rows)`.
- [ ] 4.2 Spot-check 2-3 customers known to have CallRail leads with NULL `estimate_id` and confirm their GCLIDs now appear in `customer_gclids`.
- [ ] 4.3 Push to production. Run the backfill once. Record the row count delta vs the pre-deploy measurement from 1.1.

## 5. Coordination with `conversion-attribution-overhaul`

- [ ] 5.1 If `conversion-attribution-overhaul` has not landed yet: post a note in that change's `tasks.md` or `design.md` flagging that the Source 2 block in `discover_pending_conversions*` has been rewritten by this change, so the rebase preserves the `cl.customer_id` join.
- [ ] 5.2 If `conversion-attribution-overhaul` has landed first: rebase this change's migration onto the new function bodies (whichever orchestrator they ship) and re-verify the Source 2 block reads from `cl.customer_id` directly.
