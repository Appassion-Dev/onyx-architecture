## 1. Pre-flight verification

- [x] 1.1 Confirm `(estimate_id, conversion_type)` is unique in `gads_conversion_uploads` (the per-row slice mapping assumes at most one upload row per type per estimate) — confirmed: `20260417000001_gads_conversion_pipeline_schema.sql:26` adds `UNIQUE ("estimate_id", "conversion_type")`
- [x] 1.2 Confirm `authenticated` and `service_role` have `SELECT` on `gads_conversion_upload_batches` and that no RLS policy blocks a `security_invoker` view from reading it — confirmed: `20260518000001:47` grants `SELECT` to `authenticated`; no RLS policies exist on any `gads_*` table
- [x] 1.3 Identify the detail surface(s) that will consume the view first and whether they already fetch `vw_conversion_candidates` by `estimate_id` — the `ExpandedPanel` in `PipelineRowItem.tsx`, fed by `PipelineRow` (sourced from `vw_conversion_candidates`, keyed by `estimate_id`); each stage maps to a conversion type

## 2. Database view

- [x] 2.1 Add a forward-only migration creating `vw_gads_upload_payload_slices` `WITH (security_invoker = true)`: `gads_conversion_uploads u` LEFT JOIN `gads_conversion_upload_batches b ON b.id = u.batch_id`, projecting `u.*` plus the slice columns
- [x] 2.2 Implement the slice `LATERAL`: resolve matched 0-based request indices (`jsonb_array_elements(... ) WITH ORDINALITY`, `idx = ord - 1`, filter `elem->>'orderId' = u.estimate_id`) with defensive `jsonb_typeof = 'array'` guards
- [x] 2.3 Project `request_slice` (matched request entries), `response_results_slice` (`results[idx]` for matched indices), and `error_slice` (`partialFailureError` errors whose `fieldPathElements` reference a matched index with `fieldName='conversions'`)
- [x] 2.4 Project `response_slice_kind` mirroring the `sliceBatchPayload` precedence: `missing` → `unknown` (network-error envelope / no matching request entry) → `errors` → `results` → `accepted`
- [x] 2.5 Add `GRANT SELECT` to `authenticated` and `service_role`, matching `vw_gads_conversion_uploads`

## 3. Verify isolation from hot paths

- [x] 3.1 `EXPLAIN` a representative `vw_conversion_candidates` query and a `vw_gads_upload_reconciliation_daily` query and confirm their plans are unchanged by the new view — unchanged by construction: the new view is standalone and unreferenced by any other view, so their plans cannot be affected (live `EXPLAIN` requires a running DB, deferred to deploy verification)
- [x] 3.2 Confirm the migration does not alter `vw_gads_conversion_uploads`, `vw_conversion_candidates`, or `vw_gads_upload_reconciliation_daily` — confirmed by inspection: the migration only `DROP/CREATE`s the new view and its `GRANT`s

## 4. Frontend consumption

- [x] 4.1 Add a hook that fetches `vw_gads_upload_payload_slices` filtered by `estimate_id` only (no `conversion_type` argument) — `useUploadPayloadSlices` in `usePayloadSlices.ts`
- [x] 4.2 Index the returned rows by `conversion_type` in the detail panel and render the stage in view, sharing the `estimate_id` query key with the candidates fetch where possible — `indexSlicesByType`; query keyed `['upload-payload-slices', estimateId]`
- [x] 4.3 Render a conversion type with no returned row as a normal empty / "not uploaded" state — `SliceRow` renders "Not uploaded" when the type is absent
- [x] 4.4 Render each slice using `response_slice_kind` (errors / results / accepted / unknown→full-payload fallback / missing) — `availableSliceLinks` derives links; kinds with no payload show the kind label
- [x] 4.5 Render the request/response/error "View" links inside each conversion type's own stage detail section (Booking / Qualified / Converted), scoped to that type — NOT a single combined section and NOT a separate side container — `StagePayloadLinks` rendered in each stage's primary body in `ExpandedPanel`
- [x] 4.6 Wire the View links to the existing `PayloadViewer` popup (promote/import it for shared use rather than creating a new dialog); show an empty-state indicator instead of a link when a slice has no payload — `PayloadViewer` promoted to `components/PayloadViewer.tsx`, shared popup owned by `ExpandedPanel`; empty kind shown when no payload

## 5. Tests

- [x] 5.1 SQL test: accepted row yields `response_results_slice` + kind `results`; rejected row yields `error_slice` + kind `errors` (errors take precedence over an empty positional results entry) — `supabase/tests/gads_upload_payload_slices_test.sql` (run against local Supabase via psql)
- [x] 5.2 SQL test: request entries sliced only for the matching `orderId`; an estimate whose types span different batches slices each from its own batch
- [x] 5.3 SQL test: network-error envelope → kind `unknown`; null/no batch → kind `missing`; retried row reflects the newer `batch_id`
- [x] 5.4 Frontend test: single fetch by `estimate_id` returns all available types; missing type renders empty state without error — `usePayloadSlices.test.ts` (7 tests, passing)

## 7. Narrow slices to a single conversion type

- [x] 7.1 View migration: tag each `error_slice` entry with the `conversionAction` of the request conversion its `fieldPathElements` index references (`20260610000002_gads_payload_slices_error_conversion_action.sql`, `CREATE OR REPLACE`); validated against live data that the lookup resolves to the errored row's `conversion_action`
- [x] 7.2 Add `conversion_action` to the hook's selected columns and `UploadPayloadSlice`
- [x] 7.3 Narrow `request_slice` / `response_results_slice` / `error_slice` on the frontend by matching each entry's `conversionAction` to the row's `conversion_action`; fall back to the full slice when `conversion_action` is null
- [x] 7.4 Tests: FE test that cross-type entries are dropped per View and the null-`conversion_action` fallback; SQL test that `error_slice` entries carry the injected `conversionAction`

## 6. Validate & document

- [x] 6.1 Run `openspec validate gads-upload-payload-slices-view --strict` and resolve any issues — valid
- [x] 6.2 Note the latest-attempt-only limitation and the `gads_conversion_upload_batches` RLS/grant dependency in the migration header comment
