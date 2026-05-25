## 1. Pre-deploy verification

- [x] 1.1 Run the affected-row count query from design.md §Migration Plan step 1 and record the baseline (expected: 3 — Curt Chandler's 3 estimates). A materially different count requires re-checking precedence assumptions before proceeding. **Recorded: 3 ✓**

## 2. Migration

- [x] 2.1 Create `supabase/migrations/20260522000002_vw_conversion_candidates_call_forwarding_direct.sql` patterned exactly on `supabase/migrations/20260522000001_vw_conversion_candidates_callrail_by_customer.sql` (same `DROP VIEW … CASCADE` + recreate-both shape).
- [x] 2.2 Copy the current `vw_conversion_candidates` body verbatim, then add a single new branch in the channel CASE immediately before the existing `WHEN EXISTS (… LIKE '%direct%' …) THEN 'Direct'` branch:
  ```sql
  WHEN EXISTS (
      SELECT 1 FROM unnest(COALESCE(call_agg.callrail_sources, ARRAY[]::text[])) src(value)
      WHERE LOWER(src.value) LIKE '%call forwarding%'
  ) THEN 'Direct'::varchar
  ```
- [x] 2.3 Copy the `vw_gads_upload_reconciliation_daily` body from the May-22 migration verbatim (no changes to that view).
- [x] 2.4 Re-grant SELECT on both views to `authenticated` and `service_role`, mirroring the May-22 migration.

## 3. Tests

- [x] 3.1 Add a pgTAP test under `supabase/tests/vw_conversion_candidates_channel_call_forwarding_test.sql` that inserts a fixture estimate + customer + `callrail_leads` row with `source = 'Call forwarding'`, queries `vw_conversion_candidates`, and asserts `channel = 'Direct'`.
- [x] 3.2 Add a second assertion in the same test covering the precedence scenario from the spec: a customer with both a `'Google Local Services'` and a `'Call forwarding'` CallRail row resolves to `channel = 'GLS'`.

## 4. Verify (deferred to operator — MCP is read-only)

- [ ] 4.1 Apply the migration locally (`supabase db reset` or equivalent) and re-run the affected-row count query — expect 0.
- [ ] 4.2 Spot-check the production fixture from the explore session: estimate `csr_02760bb8d5fc4a208bf723ce16c909ea` (Curt Chandler #7543) — expect `channel = 'Direct'`.
- [ ] 4.3 Run the full pgTAP suite to confirm no existing channel-classification tests regressed.
