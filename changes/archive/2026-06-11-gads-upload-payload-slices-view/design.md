## Context

The Google Ads conversion upload function stores the exact request and response of each batch as `request_body` / `response_body` jsonb on `gads_conversion_upload_batches` (migration `20260521000001`). Per-row **errors** are already extracted onto `gads_conversion_uploads` (`error_code`, `error_detail`), but per-row request entries and success results are not — they live only inside the batch payload.

Today the only per-estimate slicing is client-side in the Batches panel ([sliceBatchPayload.ts](horizon-dashboard/src/components/conversions/batches/sliceBatchPayload.ts)), which ships full batch payloads to the browser (`useBatches` does `select('*')`) and slices in JS keyed by batch. The estimate conversion detail panel needs the inverse: given one estimate, show its request/response/errors per conversion type — without downloading other customers' hashed identifiers from the same batch.

The join key already exists and is durable: the upload payload sets `orderId = estimate_id` ([payload-builder.ts](supabase/functions/google-ads-conversion-upload/payload-builder.ts)), so slicing is a lossless, reproducible function of data already stored.

## Goals / Non-Goals

**Goals:**
- A per-estimate-upload-row view that derives `request_slice`, `response_results_slice`, `error_slice`, and a `response_slice_kind` discriminator from the row's own batch payload.
- A single fetch-by-`estimate_id` contract for the detail panel; frontend maps rows to stages.
- Keep the per-row jsonb slicing out of every list/aggregate query path.
- Expose only the opened estimate's own data.

**Non-Goals:**
- Per-attempt history (the view is latest-attempt only via `batch_id`).
- Changing the Batches panel's existing batch-keyed client-side slicing (`gads-batch-payload-viewer`).
- Persisting slices in a stored column — they remain derived at read time.
- Modifying `vw_gads_conversion_uploads`, `vw_conversion_candidates`, or `vw_gads_upload_reconciliation_daily`.

## Decisions

### Decision: A new dedicated superset view, not the uploads or candidates view
`vw_gads_upload_payload_slices` is a new view = `gads_conversion_uploads u` LEFT JOIN `gads_conversion_upload_batches b` on `b.id = u.batch_id`, LEFT JOIN LATERAL the slice subquery, projecting `u.* + request_slice + response_results_slice + error_slice + response_slice_kind`.

- **Not `vw_gads_conversion_uploads`** — that view is joined three times by `vw_conversion_candidates` and read transitively by `vw_gads_upload_reconciliation_daily`. Adding a per-row `jsonb_array_elements` LATERAL there would push the slicing cost into those hot aggregate paths, and we cannot rely on Postgres to prune an unreferenced `LEFT JOIN LATERAL (…aggregates…) ON true` across three inlined join instances.
- **Not `vw_conversion_candidates`** — wrong grain (one row per estimate, stages flattened into columns) and it would mean 3 stages × 3 slices = 9 jsonb-exploding LATERALs per row on a view that `reconciliation_daily` reads.
- **Superset (`u.* + slices`), pointed at only by the detail surface** — so nothing accidentally pulls slices into a list/aggregate query, while the detail panel gets facts and slices in one row.

### Decision: Slice in SQL via index alignment
All three slices key off the position of this estimate's entries in the request `conversions` array. Resolve matched 0-based indices once from the request (`jsonb_array_elements(... ) WITH ORDINALITY`, `idx = ord - 1`, filter `elem->>'orderId' = u.estimate_id`), then:
- `request_slice` = `jsonb_agg` of matched entries.
- `response_results_slice` = `jsonb_agg(response_body->'results'->idx)` for matched indices.
- `error_slice` = errors under `partialFailureError.details[].errors[]` where some `fieldPathElements` element has `fieldName='conversions'` and `index ∈` matched indices.

Defensive `jsonb_typeof(...) = 'array' … ELSE '[]'::jsonb` wrapping mirrors the existing `vw_gads_upload_reconciliation_daily` style and guards malformed/absent payloads.

### Decision: `response_slice_kind` mirrors the existing tagged union
Reproduce [sliceBatchPayload.ts](horizon-dashboard/src/components/conversions/batches/sliceBatchPayload.ts) precedence as a computed column so the frontend does not re-derive it: `missing` (no response) → `unknown` (network-error envelope) → `errors` (error slice present) → `results` (results slice present) → `accepted` (partial-failure mode, no error references this row) → `unknown` otherwise. Errors take precedence over the positional (possibly empty `{}`) results entry.

### Decision: Fetch by `estimate_id` only, no `conversion_type` argument
The detail surface queries `WHERE estimate_id = $1`, returning ≤3 rows (one per existing upload type). The frontend indexes by `conversion_type`. Rationale: the type set is bounded and config-driven, all rows are the same customer (no extra PII), and a single `estimate_id` key aligns with the `vw_conversion_candidates` fetch so react-query caches both under one key and switching stages is a cache hit. Escape hatch if the type set ever grows or slices get large: add `AND conversion_type = $2` — same view, no new code path.

### Decision: `security_invoker = true`
Consistent with `vw_gads_conversion_uploads`. The view inherits the caller's grants/RLS on the underlying tables; dashboard `authenticated` role already has `SELECT` on `gads_conversion_upload_batches`.

## Risks / Trade-offs

- **Slice LATERAL leaks into a hot path** → Mitigated by isolating it in a dedicated view that only the detail surface selects from; `vw_gads_conversion_uploads` and downstream aggregate views are left byte-for-byte unchanged. Verify with `EXPLAIN` that no existing view's plan changes.
- **Latest-attempt only** → Documented as a non-goal; `batch_id` references the most recent batch, so retry history is not visible here. A future attempts/events table would address full history if needed.
- **RLS added to `gads_conversion_upload_batches` later** → A `security_invoker` view inherits it; confirm current grants suffice and note the dependency so a future RLS change accounts for this consumer.
- **Index-space assumption** (`results[i]` and `fieldPathElements.index` align with request `conversions[i]`) → True per the Google Ads partial-failure contract and already relied on by the shipping client-side slicer; covered by scenarios.

## Migration Plan

1. Add a forward-only migration creating `vw_gads_upload_payload_slices` (`CREATE VIEW … WITH (security_invoker = true)`), with `GRANT SELECT` to `authenticated` and `service_role` matching `vw_gads_conversion_uploads`.
2. Add the frontend hook/query that fetches by `estimate_id` and the detail-panel wiring that maps rows to stages.
3. Rollback: `DROP VIEW IF EXISTS vw_gads_upload_payload_slices;` — additive and isolated, no dependents, no data migration.

## Open Questions

- Which exact detail surface(s) consume this first (e.g. needs-attention panel vs a conversion detail drawer), and do any of them already fetch `vw_conversion_candidates` by `estimate_id` so the slice query can share the cache key?
- Confirm `(estimate_id, conversion_type)` uniqueness in `gads_conversion_uploads` (the per-row mapping assumes at most one upload row per type per estimate).
