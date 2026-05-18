## Why

The Google Ads conversion upload edge function ([supabase/functions/google-ads-conversion-upload/index.ts](supabase/functions/google-ads-conversion-upload/index.ts)) shipped under `gads-conversion-error-dispositions` works, but verification against that change's `conversion-upload` spec surfaced three real spec deviations and two local linter errors. Separately, `handlePost` is a 399-line single function: the next operator who needs to extend it (e.g., adding the deferred attribution-reconciliation join, batch splitting, or self-assigned job IDs) cannot test any phase in isolation, and the pure helpers (`parsePartialFailure`, `lifecycleFromDisposition`, `hashEmail`/`hashPhone`) are not currently importable as units for fixture-based tests.

## What Changes

### A. Spec compliance fixes (behavior changes)

- **Expired rows write `error_detail`, not `error_message`.** The 90-day-window expiry update at [index.ts:309-318](supabase/functions/google-ads-conversion-upload/index.ts#L309-L318) writes the reason string to the legacy `error_message` column. The `conversion-upload` spec scenario "Pending row outside 90-day window is expired" requires `error_detail`. Switch to `error_detail: { reason: "Outside Google Ads 90-day conversion window" }`.
- **Clear stale `error_code` on excluded transitions.** When a row that was previously `retrying` (carrying a per-row `error_code` from a prior attempt) is marked `lifecycle = 'excluded'` because it now has no GCLID and no identifiers ([index.ts:396-407](supabase/functions/google-ads-conversion-upload/index.ts#L396-L407)), the old `error_code` / `error_namespace` / `error_detail` are left in place. The view `vw_gads_conversion_uploads` then projects a contradictory `disposition` (e.g., `retry`) onto an `excluded` row. The excluded update must null those three columns.
- **Clear stale `error_code` on batch-failure-back-to-queued transitions.** The batch-failure path at [index.ts:502-513](supabase/functions/google-ads-conversion-upload/index.ts#L502-L513) puts constituent rows back to `lifecycle = 'queued'` (correct per `gads-pipeline-pause` design D7 — rows are blameless) but leaves any prior `error_code` populated. A queued row with a non-NULL `error_code` is an inconsistent state for the disposition view. Null `error_code` / `error_namespace` / `error_detail` in this update too.
- **Defensive bounds check on per-row error index.** The per-row outcome loop at [index.ts:547-549](supabase/functions/google-ads-conversion-upload/index.ts#L547-L549) trusts `perRowErrors.get(i)` to align with the request `conversions[]` array. `parsePartialFailure` extracts `location.fieldPathElements[0].index` from the Google response. If Google ever returns an index outside `[0, toUpload.length)`, the corresponding row currently gets silently marked `sent`. Drop out-of-range indices in `parsePartialFailure` with a `console.warn` so the row falls into the success path only when there genuinely was no per-row error.

### B. Linter fixes

- **`require-await` on `hashEmail` and `hashPhone`** ([index.ts:42](supabase/functions/google-ads-conversion-upload/index.ts#L42), [index.ts:54](supabase/functions/google-ads-conversion-upload/index.ts#L54)). Both functions `return sha256hex(...)` with no internal `await`. Drop the `async` keyword; the return type stays `Promise<string | null>` and call sites keep their `await`.
- **Out of scope:** the three `no-import-prefix` / `no-unversioned-import` findings on the `jsr:` imports are project-wide (13 edge functions share the pattern). They belong in a separate change that introduces a `deno.json` imports map for the whole `supabase/functions/` tree.

### C. Refactor `handlePost` into testable phases (no behavior change)

- Extract pure helpers into sibling modules:
  - `error-parsing.ts` — `parsePartialFailure`, `extractErrorCode`, `KNOWN_ERROR_NAMESPACES`, `ParsedRowError`, `ParsedPartialFailure`.
  - `disposition.ts` — `Lifecycle`, `LIFECYCLE_TO_STATUS`, `Disposition`, `DispositionRow`, `lifecycleFromDisposition`.
  - `hashing.ts` — `sha256hex`, `hashEmail`, `hashPhone`, `formatConversionDateTime`.
- Extract phase functions from `handlePost` inside `index.ts` (kept in the same file so the orchestration is readable in one place):
  - `checkPipelinePause(sb)` → `Response | null`
  - `parseRequestScope(req)` → `{ estimateIds?, conversionTypes? }`
  - `loadDispositions(sb)` → `Map<string, DispositionRow>`
  - `selectAndExpire(sb, scope, dispositionMap, cutoffIso)` → `PendingRow[]` (includes the JS-side retry-timing filter and the 90-day expire UPDATE)
  - `loadConfig(sb)` → `Map<string, ConfigRow>`
  - `classifyRows(pending, configMap, cfg)` → `{ uploadable, skippedRows }`
  - `buildPayloads(uploadable, contactMap)` → `{ toUpload, noIdRows }`
  - `markNoIdExcluded(sb, noIdRows)`
  - `createBatch(sb, toUpload)` → `batchId`
  - `markSending(sb, ids, batchId)`
  - `callGoogleAds(toUpload, cfg, accessToken)` → `{ res, data, networkError }`
  - `handleBatchFailure(sb, batchId, ...)` → `Response`
  - `applyPerRowOutcomes(sb, batchId, toUpload, perRowErrors, dispositionMap, httpStatus, jobId)` → `Response`
- `handlePost` shrinks to ~60 lines of orchestration that reads top-to-bottom.
- **No behavior change.** Every extracted phase performs the same DB calls and emits the same log lines as today. The Spec-compliance fixes in section A are applied inside the extracted phases.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `conversion-upload`: Adds defensive bounds-check scenario for per-row error indices, and tightens the "expired row", "no-identifier excluded", and "batch-level failure" scenarios to require nulling stale structured-error columns when the row transitions into a state where they would be misleading. No new lifecycle values, no schema changes.

## Impact

- **Code** — [supabase/functions/google-ads-conversion-upload/index.ts](supabase/functions/google-ads-conversion-upload/index.ts) is restructured into ~13 helper functions (plus three new sibling modules `error-parsing.ts`, `disposition.ts`, `hashing.ts`). The four spec-compliance fixes live inside the extracted phases.
- **Database** — no schema change. The fixes only change the *values* written by the edge function; existing CHECK constraints and the `vw_gads_conversion_uploads` view are unaffected.
- **Linter** — `deno lint` on this file drops from 5 findings to 3 (the remaining 3 are project-wide `no-import-prefix` issues handled separately).
- **Tests** — the new helper modules are importable for unit-style fixture tests; this change does not add a test harness (none exists in `supabase/functions/` today), it only unblocks one.
- **Downstream consumers** — the FE reads `vw_gads_conversion_uploads`. After the fixes, queued/excluded rows that previously projected a contradictory `disposition` will project `NULL` disposition. The Needs Attention inbox already filters by `lifecycle = 'needs-attention'`, so it will not be affected; the Batches drill-down may show rows with `error_code = NULL` where it previously showed stale codes — which is the correct state.
- **Rollback** — pure code change; revert the PR to undo.
