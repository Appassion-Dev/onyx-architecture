## Why

The `capture-raw-batch-payloads` change persists the exact JSON sent to and returned from Google Ads on every `gads_conversion_upload_batches` row, but those `request_body` / `response_body` columns are currently invisible in the app. Investigating a failed or partially-rejected batch still requires hand-querying Supabase. The Workbench Batches panel is where operators already triage uploads — that is where the raw payloads need to be readable.

## What Changes

- Add **Request** and **Response** columns to the batches table in [BatchesPanel.tsx](horizon-dashboard/src/components/conversions/batches/BatchesPanel.tsx). At the batch-row level, each cell opens a viewer with the **full** pretty-printed JSON of `request_body` / `response_body` for that batch.
- In the per-batch drill-down (constituent rows), add the same two columns. For each estimate row, slice the batch's `request_body.conversions[]` to the entry whose `gclid` (or order id) matches the row, and slice `response_body.partialFailureError.errors[]` / `response_body.results[]` to that row's index. The cell opens a viewer with just that estimate's slice.
- Viewer is a modal/popover with monospace, indented JSON, copy-to-clipboard, and a clear "no payload captured" state for legacy rows where the columns are NULL.
- Extend the `useBatches` / `useBatchConstituents` queries to fetch the new jsonb columns and (for constituents) the row's `gclid` and array index used for slicing.

No backend or schema changes. Read-only UI on existing columns.

## Capabilities

### New Capabilities
- `gads-batch-payload-viewer`: viewing the raw Google Ads request/response JSON captured on `gads_conversion_upload_batches`, both in full at the batch level and sliced to a single estimate at the constituent-row level.

### Modified Capabilities
<!-- None — the existing batches-panel spec lives in an un-archived change; this viewer is layered on top as a new capability. -->

## Impact

- **Code**: [BatchesPanel.tsx](horizon-dashboard/src/components/conversions/batches/BatchesPanel.tsx) and [useBatches.ts](horizon-dashboard/src/components/conversions/batches/useBatches.ts) gain new columns, types, and a viewer component (new file, e.g. `PayloadViewer.tsx`).
- **Data**: `useBatches` selects `request_body` / `response_body`; `useBatchConstituents` additionally selects the estimate's `gclid` and (if available from `vw_gads_conversion_uploads`) the row's position within its batch.
- **Schema**: none. The `request_body` / `response_body` columns are already provided by `capture-raw-batch-payloads`.
- **Tests**: component tests for slicing (gclid match, missing entry, missing payload) and for the viewer's empty state.
- **PII**: identifiers in `request_body` are SHA-256 hashed and GCLIDs are opaque; same posture as the existing constituent drill-down. The viewer is behind the same authenticated route as the rest of the Workbench.
