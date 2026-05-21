## Context

`gads_conversion_upload_batches` now carries `request_body jsonb` (an object `{ conversions: [...], partialFailure: true }`) and `response_body jsonb` (either Google's parsed response, or `{ network_error, captured_at }` for transport failures). The Workbench Batches panel — [BatchesPanel.tsx](horizon-dashboard/src/components/conversions/batches/BatchesPanel.tsx) — already lists batches and expands to constituent rows via [useBatches.ts](horizon-dashboard/src/components/conversions/batches/useBatches.ts). This change layers a viewer on top of that existing structure; no schema, RLS, or backend work.

## Goals / Non-Goals

- **Goals**: One-click inspection of the exact JSON Google saw and returned, both per batch (full payload) and per estimate (sliced payload). Robust handling of legacy NULL payloads and partial-failure response shape.
- **Non-Goals**: Editing payloads, replaying batches, diffing across batches, syntax-highlighted folding tree (basic monospace pretty-print is enough for first pass), or exposing payloads outside the Workbench.

## Decisions

### Decision: Slice request by orderId match, response by operation index

`request_body.conversions[i]` corresponds 1:1 to `response_body.results[i]` (when present) and is referenced by index in `response_body.partialFailureError.details[*].errors[*].location.fieldPathElements` (the path includes `conversions` with `index = i`).

For the per-estimate slice:
- **Request slice**: filter `request_body.conversions[]` by `entry.orderId === row.estimate_id`. The matched indices `I` form the row's operation indices.
- **Response slice**: for each `i ∈ I`, collect (a) `response_body.results[i]` if it exists, and (b) any `errors[]` from `partialFailureError.details[*]` whose `fieldPathElements` contains `{ fieldName: "conversions", index: i }`.

Rationale: the payload builder writes `orderId: row.estimate_id` on **every** conversion entry, regardless of `conversion_type` or whether `gclid` is set. This makes `orderId` the only universally-present identifier and the only key guaranteed to match exactly the constituent row. (gclid was considered first but rejected: it may be null on user-data-only uploads, and the same gclid can legitimately appear under multiple conversion types in one batch.)

**Alternative considered**: persist a `payload_index int` column on `gads_conversion_uploads` at write time. Rejected — adds backend churn for a UI concern, and `request_body.conversions` is small (dozens of entries) so a client-side scan is trivial.

### Decision: Modal viewer, not inline expansion

Cell click opens a `<Dialog>` (already used elsewhere in the dashboard) with a `<pre><code>` block containing `JSON.stringify(payload, null, 2)`. No syntax-highlight library is added in v1 — monospace + indentation is sufficient for triage and avoids a new dependency. Copy button uses `navigator.clipboard.writeText`.

Rationale: payloads can be multiple KB; inline expansion would crowd the table and break per-row layout. A modal is consistent with other detail views in the Workbench.

**Alternative considered**: a side drawer. Equivalent UX; modal is already used for similar inspection flows in the codebase.

### Decision: Cell affordance shows size, not a preview

Each cell renders `View · <size>` where size is `formatBytes(JSON.stringify(payload).length)`. NULL payload renders `—` with a tooltip "No payload captured". An empty slice (estimate not found in payload) renders `—` with "No payload slice for this row".

Rationale: operators scanning the table benefit more from a quick size hint (signals "small batch" vs "fat batch") than a truncated JSON preview that's unreadable at a column width.

### Decision: Fetch full payloads in the existing list query

`useBatches` already selects `*` from `gads_conversion_upload_batches`; with the new columns this automatically pulls them. We keep `select('*')` rather than narrowing because the row count is paginated (50/page) and the typical payload is < 50 KB — total page weight stays well under a megabyte.

The per-constituent slice is computed client-side from the parent batch's `request_body` / `response_body`. To make that accessible to `ConstituentRows`, the parent `BatchesPanel` passes the batch object (not just `batchId`) to the expanded component. No additional network call needed.

The constituent query needs the row's `gclid` to perform the match. Today `useBatchConstituents` selects `id, estimate_id, conversion_type, lifecycle, error_code` — we extend it to also select `gclid` from `vw_gads_conversion_uploads`.

### Decision: Capability boundary

This is a new capability `gads-batch-payload-viewer` rather than a delta on `gads-conversion-batches` because the latter's spec lives in an un-archived change (`gads-conversion-error-dispositions`). Creating a new capability avoids cross-change archival ordering hazards. If/when both changes archive, the two capabilities can be merged in a follow-up.

## Risks / Trade-offs

- **Duplicate orderId**: if the same `estimate_id` appears twice in a batch (e.g. retried before the batch landed), the slice will contain both entries. Acceptable; the viewer simply shows both.
- **Future schema drift**: if Google adds new top-level keys to `response_body`, the response slicing logic must be tolerant (treat unknown shapes as "no slice available" rather than throwing).

## Migration Plan

None. The columns already exist (rows written before `capture-raw-batch-payloads` shipped are NULL and the viewer's "no payload captured" state covers them).

## Open Questions

- None blocking. Conversion types beyond gclid-based may need follow-up if/when they ship.
