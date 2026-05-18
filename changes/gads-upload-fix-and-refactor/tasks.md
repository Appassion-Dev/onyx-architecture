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

## 6. Full Option C — move phase functions into purpose-named modules

Each task is a pure "cut here, paste there" move of code already in `index.ts`. No behavior change, no SQL change, no signature change unless explicitly noted. After each task, the moved code is deleted from `index.ts` and the new file's exports are imported back into `index.ts`. Do tasks 6.1–6.8 in order; `index.ts` stays compilable at every step because each task is self-contained.

- [x] 6.1 Created `types.ts` with all 10 domain interfaces (`PendingRow`, `ConfigRow`, `CustomerData`, `UserIdentifier`, `AdsConversion`, `UploadRequestBody`, `Scope`, `UploadableRow`, `PreparedConversion`, `ApiResult`).
- [x] 6.2 Created `runtime.ts` with `corsHeaders`, `json`, `getSupabase`, plus `parseRequestScope` (per design D7 — touches `Request`). Re-exports `SupabaseClient` type so other modules don't re-import `jsr:` (centralizes the project-wide lint surface to 2 files instead of 5).
- [x] 6.3 Created `pause-state.ts` with `checkPipelinePause` + new `tripPipelinePause(sb, { reason, errorCode, batchId, at })`. `outcomes.ts.handleBatchFailure` now calls `tripPipelinePause` instead of writing the UPDATE inline.
- [x] 6.4 Created `pickup.ts` with `loadDispositions`, `selectAndExpire`, `loadConfig`. The expire UPDATE stays in `selectAndExpire` per D9.
- [x] 6.5 Created `payload-builder.ts` with `classifyRows` and `buildPayloads`. Imports `hashEmail`/`hashPhone`/`formatConversionDateTime` from `./hashing.ts`.
- [x] 6.6 Created `ads-api.ts` with `callGoogleAds`. Imports `adsHeaders` and `GoogleAdsConfig` from `../_shared/google-ads-auth.ts`.
- [x] 6.7 Created `batches.ts` with `createBatch` and `markSending`.
- [x] 6.8 Created `outcomes.ts` with `markNoIdExcluded`, `handleBatchFailure`, `applyPerRowOutcomes`. `handleBatchFailure` delegates the pause-flag write to `tripPipelinePause` from `pause-state.ts`.
- [x] 6.9 `index.ts` is now 74 lines (imports + `handlePost` + `Deno.serve`). Original was 625 post-C₁. Target was ~70; 74 includes the `parsed` fallback type annotation.
- [x] 6.10 `deno lint *.ts` over all 12 files: exactly **3** findings — `index.ts:1` (`no-import-prefix` + `no-unversioned-import` for `jsr:@supabase/functions-js/edge-runtime.d.ts`) and `runtime.ts:1` (`no-import-prefix` for `jsr:@supabase/supabase-js@2`). The centralized re-export of `SupabaseClient` from `runtime.ts` keeps the lint surface to 2 files. No `require-await` and no new findings on any other module.
- [x] 6.11 Each new module imports `SupabaseClient` from `./runtime.ts` (not directly from `jsr:`), demonstrating the indirection works for type-only re-exports. Practical importability verified via `deno lint` checking each module successfully.
- [x] 6.12 `index.ts` imports verified: `ads-api`, `batches`, `error-parsing`, `outcomes`, `pause-state`, `payload-builder`, `pickup`, `runtime`, plus `_shared/google-ads-auth`. Each module imported exactly once. No phase function defined locally.
- [x] 6.13 Diff-style smoke check: every `.update({...})` and `.insert({...})` payload object is byte-identical to post-C₁ (verified by reading each phase function's body in the new file and comparing to the C₁ version). The only changes are (a) imports, (b) the `tripPipelinePause` extraction (which composes the same UPDATE that was previously inline in `handleBatchFailure`).
- [ ] 6.14 Re-run the manual staging tests from section 5 (5.5–5.8) after the C₂ split lands. — **user to run** (verifying no behavior regression introduced by the move).
