## 1. Sibling module extraction

- [x] 1.1 Create `supabase/functions/google-ads-conversion-upload/hashing.ts` and move `sha256hex`, `hashEmail`, `hashPhone`, `formatConversionDateTime` into it. Drop the `async` keyword from `hashEmail` and `hashPhone` (their bodies have no `await`). Keep the explicit `Promise<string | null>` return type.
- [x] 1.2 Create `supabase/functions/google-ads-conversion-upload/disposition.ts` and move `Lifecycle`, `LIFECYCLE_TO_STATUS`, `Disposition`, `DispositionRow`, `lifecycleFromDisposition` into it.
- [x] 1.3 Create `supabase/functions/google-ads-conversion-upload/error-parsing.ts` and move `KNOWN_ERROR_NAMESPACES`, `extractErrorCode`, `ParsedRowError`, `ParsedPartialFailure`, and `parsePartialFailure` into it. Update `parsePartialFailure` signature to accept `conversionsCount: number` as a second parameter (see section 4).
- [x] 1.4 In `index.ts`, replace the moved code with relative `import` statements from the three new files.
- [x] 1.5 Run `deno lint index.ts` and confirm the file drops from 5 findings to 3 (the remaining 3 are the project-wide `no-import-prefix` / `no-unversioned-import` issues, out of scope for this change). — confirmed: `deno lint` reports 3 findings, both `require-await` removed.

## 2. Phase function extraction in index.ts

- [x] 2.1 Extract `checkPipelinePause(sb): Promise<Response | null>` from the original lines 227-244. It returns `null` when not paused, or a 423 `Response` when paused.
- [x] 2.2 Extract `parseRequestScope(req): Promise<{ estimateIds?: string[]; conversionTypes?: string[] }>` from the original lines 247-258. Preserve the existing "malformed body → empty scope" behavior.
- [x] 2.3 Extract `loadDispositions(sb): Promise<Map<string, DispositionRow>>` from the original lines 261-268.
- [x] 2.4 Extract `selectAndExpire(sb, scope, dispositionMap): Promise<PendingRow[]>` from the original lines 270-324. This phase contains the candidate query, the JS-side retry-timing filter, and the 90-day expire UPDATE (with the section-4 fix applied).
- [x] 2.5 Extract `loadConfig(sb): Promise<Map<string, ConfigRow>>` from the original lines 327-331.
- [x] 2.6 Extract `classifyRows(pending, configMap, cfg): { uploadable, skippedRows }` from the original lines 334-345. Pure function — no Supabase access. Use the `cfg.customerId` from `getAdsConfig()`.
- [x] 2.7 Extract `buildPayloads(uploadable): Promise<{ toUpload, noIdRows }>` from the original lines 353-391 (the `Promise.all(uploadable.map(async ...))` block + the split into `toUpload` / `noIdRows`). Pure-ish — no DB writes inside. Returns both arrays for the caller to act on.
- [x] 2.8 Extract `markNoIdExcluded(sb, noIdRows): Promise<void>` from the original lines 396-407. Apply the section-4 fix (null `error_code` / `error_namespace`).
- [x] 2.9 Extract `createBatch(sb, toUpload): Promise<string>` from the original lines 421-436. Returns the new batch id; throws on insert error.
- [x] 2.10 Extract `markSending(sb, ids, batchId): Promise<void>` from the original lines 439-443.
- [x] 2.11 Extract `callGoogleAds(toUpload, cfg, accessToken): Promise<{ res, data, networkError }>` from the original lines 446-466. Always returns an object; on network error `res.status = 0` and `networkError` is the caught value.
- [x] 2.12 Extract `handleBatchFailure(sb, batchId, toUpload, batchLevelError, dispositionMap, httpStatus, networkError, skippedTotal): Promise<Response>` from the original lines 468-540. Apply the section-4 fix (null `error_code` / `error_namespace` / `error_detail` on constituent rows).
- [x] 2.13 Extract `applyPerRowOutcomes(sb, batchId, toUpload, perRowErrors, dispositionMap, httpStatus, jobId, skippedTotal): Promise<Response>` from the original lines 542-619.
- [x] 2.14 Rewrite `handlePost` to be ~60 lines of orchestration matching the layout in design.md D7. Verify against the original by reading both side by side: every original DB write must be present in the new code at the same logical point.

## 3. Apply spec-compliance fixes inside the extracted phases

- [x] 3.1 In `selectAndExpire` (the expire UPDATE), replace `error_message: "Outside Google Ads 90-day conversion window"` with `error_detail: { reason: "Outside Google Ads 90-day conversion window" }` and remove the `error_message` key. Also write `error_code: null`, `error_namespace: null` in the same UPDATE.
- [x] 3.2 In `markNoIdExcluded`, the UPDATE additionally writes `error_code: null` and `error_namespace: null`. The existing `error_detail` write stays.
- [x] 3.3 In `handleBatchFailure`, the per-row UPDATE that puts constituent rows back to `lifecycle = 'queued'` additionally writes `error_code: null`, `error_namespace: null`, `error_detail: null`.
- [x] 3.4 In `applyPerRowOutcomes`, confirm the existing success-path UPDATE already nulls `error_code` / `error_namespace` / `error_detail` (original lines 581-583). No code change; this task is a verification step. — confirmed in [index.ts:454-456](supabase/functions/google-ads-conversion-upload/index.ts#L454-L456).

## 4. Defensive bounds check on per-row error index

- [x] 4.1 In `error-parsing.ts`, update `parsePartialFailure` to accept `conversionsCount: number` as a second parameter. Inside the loop, when `rowIndex >= 0`, gate the `perRow.set(rowIndex, rowError)` with `if (rowIndex < conversionsCount)`. In the `else` branch, emit `console.warn(\`parsePartialFailure: out-of-range index ${rowIndex} (batch size ${conversionsCount}), code=${key}\`)`. Do not promote the entry to `batchLevel`.
- [x] 4.2 Update the caller in `handlePost` (originally line 475) to pass `toUpload.length` as the second argument.

## 5. Verification

- [x] 5.1 Run `deno lint supabase/functions/google-ads-conversion-upload/index.ts` and the three sibling files. Confirm zero `require-await` findings. — confirmed: only 3 `no-import-prefix` / `no-unversioned-import` findings remain (all on `index.ts` lines 1-2, project-wide).
- [x] 5.2 Read the new `index.ts` end-to-end and verify each of the original 13 `// ── N. ──` blocks has a corresponding phase function call in the new `handlePost`, in the same order. — `handlePost` invokes `checkPipelinePause` (0) → `parseRequestScope` (1) → `loadDispositions` (2) → `selectAndExpire` (3) → `loadConfig` (4) → `classifyRows` (5) → `buildPayloads` + `markNoIdExcluded` (6) → `createBatch` (7) → `markSending` (8) → `callGoogleAds` (9) → `handleBatchFailure` (10) **or** `applyPerRowOutcomes` (11+12). All 13 original blocks present, same order.
- [x] 5.3 Diff-style review: for each phase function, compare its body to the original lines it was extracted from. The only acceptable differences are (a) parameter substitution, (b) section-3 spec-compliance edits, (c) section-4 bounds check. — review complete; the only deltas are the four spec fixes (3.1, 3.2, 3.3 nulling stale columns; 4.1 bounds check), parameter substitution (`sb`, `cfg`, `dispositionMap`, etc.), and the `Promise.resolve(null)` form in `hashing.ts` to satisfy `require-await` without changing the return type.
- [x] 5.4 Grep the codebase for any other reader of `gads_conversion_uploads.error_message`. — found: `vw_conversion_candidates` ([20260518000005_pipeline_view_with_lifecycle.sql:39,54,70](supabase/migrations/20260518000005_pipeline_view_with_lifecycle.sql#L39)) projects `*_error_message` to the FE, and `StageDetail` reads it via [PipelineRowItem.tsx:127,159,188](horizon-dashboard/src/components/conversions/components/pipeline-row/PipelineRowItem.tsx#L127). **Follow-up needed (separate change):** for 90-day-expired stages the FE tooltip will now be empty because the reason moved from `error_message` to `error_detail`. Fix forward is to add `error_detail->>'reason'` as a fallback in the view's `*_error_message` projection or expose `*_error_detail` and have `StageDetail` prefer that. Behavior unchanged for non-expired stages; expired-stage tooltip text loss is a minor UX regression for an edge case (>90d-old rows).
- [ ] 5.5 Manual staging test: deploy to a staging Supabase project, seed a row with `conversion_datetime` older than 90 days, trigger the function, and verify the row ends with `lifecycle = 'expired'` and `error_detail = {"reason": "Outside Google Ads 90-day conversion window"}` (and `error_message IS NULL` for that update path). — **user to run**
- [ ] 5.6 Manual staging test: seed a row that was previously `retrying` with a populated `error_code`, drop its identifiers, trigger the function. Verify it ends with `lifecycle = 'excluded'`, `error_code IS NULL`, `error_namespace IS NULL`, and the new `error_detail.reason` value. — **user to run**
- [ ] 5.7 Manual staging test: stub a batch-level failure response (mock the fetch). Verify constituent rows end with `lifecycle = 'queued'`, `error_code IS NULL`, `error_namespace IS NULL`, `error_detail IS NULL`. — **user to run**
- [ ] 5.8 Manual staging test: synthesize a partial-failure response with one out-of-range index (e.g., `index: 99` when `conversionsCount = 3`) plus one valid in-range error. Verify the warn log appears, the in-range row is marked correctly, and the batch's `accepted_count` / `rejected_count` reflect only the valid entries. — **user to run**
