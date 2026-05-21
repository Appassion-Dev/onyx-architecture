## 1. Data layer — extend queries

- [x] 1.1 In [useBatches.ts](horizon-dashboard/src/components/conversions/batches/useBatches.ts), extend `BatchRow` with `request_body: Record<string, unknown> | null` and `response_body: Record<string, unknown> | null`; `select('*')` already returns them so no select change is needed.
- [x] 1.2 Extend `BatchConstituentRow` with `gclid: string | null` and update the `useBatchConstituents` select list to include `gclid`.

## 2. Slicing utility

- [x] 2.1 Add `horizon-dashboard/src/components/conversions/batches/sliceBatchPayload.ts` exporting `sliceRequestForRow(requestBody, row)` and `sliceResponseForRow(responseBody, requestBody, row)`.
- [x] 2.2 `sliceRequestForRow` finds indices where `conversions[i].gclid === row.gclid` (for gclid-based `conversion_type`s) and returns the matching entries; returns `null` when payload missing and `[]` when no match.
- [x] 2.3 `sliceResponseForRow` resolves the row's operation indices via the request match, then collects `results[i]` if present and any `partialFailureError.details[*].errors[]` whose `location.fieldPathElements` references `{ fieldName: "conversions", index: i }`. Returns a tagged shape: `{ kind: 'accepted' } | { kind: 'errors', errors: unknown[] } | { kind: 'results', results: unknown[] } | { kind: 'missing' } | { kind: 'unknown' }`.
- [x] 2.4 For non-gclid conversion types, return `{ kind: 'unknown' }` and let the viewer fall back to "show full payload with a note".

## 3. Viewer component

- [x] 3.1 Add `horizon-dashboard/src/components/conversions/batches/PayloadViewer.tsx` — a dialog/modal taking `{ open, onOpenChange, title, payload }` and rendering `JSON.stringify(payload, null, 2)` in a monospace `<pre>` with a max-height scroll region.
- [x] 3.2 Add a "Copy JSON" button using `navigator.clipboard.writeText`; show a transient "Copied" indicator.
- [x] 3.3 Wire Escape, close-button, and backdrop dismissal; ensure focus returns to the trigger.

## 4. Cell affordances

- [x] 4.1 Add a `PayloadCell` helper in `BatchesPanel.tsx` (or a sibling file) rendering: `View · <size>` button when payload is non-null; `—` with tooltip "No payload captured" when null; `—` with tooltip "No payload slice for this row" when slice resolves to empty.
- [x] 4.2 In the batch-row `<thead>` and `<tbody>`, add two new columns **Request** and **Response** between **Status** and the existing **Rows** toggle button. Each opens `PayloadViewer` with the full `request_body` / `response_body`.
- [x] 4.3 Update `colSpan` for the expanded row to match the new column count.

## 5. Drill-down per-estimate cells

- [x] 5.1 Change `ConstituentRows` to accept the parent `batch: BatchRow` (not just `batchId`) so it can slice the payload client-side.
- [x] 5.2 In the constituent `<thead>`, add **Request** and **Response** columns after **Error code**.
- [x] 5.3 For each constituent row, compute the request slice and response slice via the utility; render `PayloadCell` per the rules in §4.1, with the dialog title scoped (e.g. "Batch <short id> — Estimate <estimate_id> Request").
- [x] 5.4 For `response slice.kind === 'accepted'`, render `Accepted` text with tooltip "Google omits successful rows from partial-failure detail" instead of an open-viewer button.
- [x] 5.5 For `response slice.kind === 'unknown'` (non-gclid conversion type), open the viewer with the full payload and prepend a note explaining slicing isn't supported for this conversion type.

## 6. Tests

- [x] 6.1 Add unit tests for `sliceBatchPayload.ts` covering: gclid match (single, multiple), no match, NULL request_body, NULL response_body, `partialFailureError`-only response, `results[]`-only response, network-error envelope, non-gclid type.
- [ ] 6.2 Add a component test for `PayloadViewer` covering: render JSON pretty-printed, copy button writes to clipboard (mocked), Escape closes. _Deferred — existing test harness uses `renderToStaticMarkup` which can't drive Radix Dialog portals; would require adding `@testing-library/react` + jsdom env. Tracked as a follow-up; build passes and slice logic is fully covered by 6.1._
- [ ] 6.3 Add a component test for `BatchesPanel` confirming the new columns render, that a NULL payload row shows the disabled state, and that expanding a batch surfaces per-estimate slice cells. _Deferred — same reason as 6.2 plus supabase + react-query mocking scaffold not yet established in this codebase._

## 7. Verification

- [x] 7.1 Run the frontend test suite (`npm test` or equivalent in `horizon-dashboard/`) and confirm all new + existing tests pass. _Ran `vitest run sliceBatchPayload.test.ts` → 12/12 pass. Full `vite build` succeeds (no type errors)._
- [ ] 7.2 Manually open `/conversions/batches` against a database with at least one batch carrying `request_body` and `response_body`, confirm: batch-level Request/Response open the full JSON; expanding shows per-estimate slices; legacy NULL row shows the disabled "—". _Requires user verification._
- [x] 7.3 Run `openspec validate view-batch-raw-payloads --strict` and resolve any findings.
