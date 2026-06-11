## Why

When an estimate's conversion detail panel is opened, operators want to see the exact Google Ads request, response, and per-row errors for that estimate's uploads — but today that data only lives as the full batch payload on `gads_conversion_upload_batches`, which bundles every other customer's hashed identifiers in the same batch. The Batches panel works around this by shipping whole batch payloads to the browser and slicing client-side, which both over-exposes PII and is keyed by batch, not by estimate. The estimate detail panel needs a per-estimate slice instead.

## What Changes

- Add a new view `vw_gads_upload_payload_slices` that projects each upload row (`gads_conversion_uploads.*`) plus three derived columns sliced from its batch's payload, keyed by `orderId = estimate_id`:
  - `request_slice` — the conversion entries this estimate contributed to the batch request.
  - `response_results_slice` — the positional `results[i]` entries for this estimate's request indices.
  - `error_slice` — the `partialFailureError` errors whose `fieldPathElements` reference this estimate's request indices.
  - plus `response_slice_kind` — a tagged-union discriminator (`missing` / `unknown` / `accepted` / `results` / `errors`) mirroring the existing client-side `sliceBatchPayload` precedence.
- Slicing is done in SQL via a `LATERAL` join over the row's own `batch_id`, so each conversion type slices its own batch independently.
- The estimate detail panel fetches all of an estimate's slices in a single request filtered by `estimate_id` only (no `conversion_type` argument); the frontend indexes the ≤3 returned rows by `conversion_type` and renders whichever stage is in view, treating a missing type as a normal empty state.
- The view is a superset (`u.* + slices`) and is pointed at **only** by the detail surface, kept separate from `vw_gads_conversion_uploads` so the per-row jsonb slicing never enters list/aggregate query paths.

## Capabilities

### New Capabilities
- `gads-upload-payload-slices`: a per-estimate-upload-row database view that slices the batch request/response/error payload down to a single estimate, and the estimate detail panel's fetch-by-`estimate_id` contract for consuming it.

### Modified Capabilities
<!-- None — additive. The batch-keyed client-side slicing (gads-batch-payload-viewer) is unchanged. -->

## Impact

- **Database**: new view `vw_gads_upload_payload_slices` (`security_invoker = true`) over `gads_conversion_uploads` + `gads_conversion_upload_batches`; new migration. No table or column changes. No change to `vw_gads_conversion_uploads`, `vw_conversion_candidates`, or `vw_gads_upload_reconciliation_daily`.
- **Frontend** (`horizon-dashboard`): the estimate conversion detail panel gains a hook that fetches slices by `estimate_id` and maps rows to stages.
- **Access/PII**: the detail surface receives only the opened estimate's own slices, never other customers' hashed identifiers from the same batch. View inherits caller RLS/grants on `gads_conversion_upload_batches` via `security_invoker`.
- **Constraints**: slices reflect the latest attempt only (`u.batch_id` points to the most recent batch); full per-attempt history is out of scope.
