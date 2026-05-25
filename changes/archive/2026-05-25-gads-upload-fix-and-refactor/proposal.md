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

### C. Full module split — one purpose per file (no behavior change)

The refactor pushes Option C in full: every meaningful responsibility moves into its own sibling module so each can be unit-tested in isolation and extended without re-reading the orchestration. `index.ts` becomes a ~70-line orchestration + `Deno.serve` entry; the 13 phase functions plus the pure helpers live in purpose-named modules.

**Pure helpers (already landed in C₁; kept):**
- `error-parsing.ts` — `parsePartialFailure`, `extractErrorCode`, `KNOWN_ERROR_NAMESPACES`, `ParsedRowError`, `ParsedPartialFailure`.
- `disposition.ts` — `Lifecycle`, `LIFECYCLE_TO_STATUS`, `Disposition`, `DispositionRow`, `lifecycleFromDisposition`.
- `hashing.ts` — `sha256hex`, `hashEmail`, `hashPhone`, `formatConversionDateTime`.

**New modules (C₂):**
- `types.ts` — domain interfaces with no logic: `PendingRow`, `ConfigRow`, `CustomerData`, `UserIdentifier`, `AdsConversion`, `UploadRequestBody`, `Scope`, `UploadableRow`, `PreparedConversion`, `ApiResult`. Importable into any test fixture.
- `runtime.ts` — runtime/env glue: `corsHeaders`, `json`, `getSupabase`. The only module that touches `Deno.env` directly.
- `pause-state.ts` — `checkPipelinePause(sb)` + `tripPipelinePause(sb, ...)`. Single funnel for every read/write of `gads_pipeline_state`.
- `pickup.ts` — `loadDispositions(sb)`, `selectAndExpire(sb, scope, dispositionMap)`, `loadConfig(sb)`. The read-side phase. The 90-day expire UPDATE lives here so the pickup contract is self-contained.
- `payload-builder.ts` — `classifyRows(pending, configMap, cfg)`, `buildPayloads(uploadable)`. Pure-ish: no DB writes inside; consumers act on the returned arrays.
- `ads-api.ts` — `callGoogleAds(toUpload, cfg, accessToken)`. The only `fetch()` to Google. Replaceable with a fixture stub in tests.
- `batches.ts` — `createBatch(sb, toUpload)`, `markSending(sb, ids, batchId)`. Insert + the initial `sending` marker for `gads_conversion_upload_batches` and `gads_conversion_uploads`.
- `outcomes.ts` — `markNoIdExcluded(sb, noIdRows)`, `handleBatchFailure(sb, ...)`, `applyPerRowOutcomes(sb, ...)`. All terminal-row UPDATEs and the batch-row finalize live here. This is the largest new module (~200 lines) but coherent: every "after we decided what happened to a row" path is on one screen.

**`index.ts` keeps only:**
- The ~70-line `handlePost` orchestration (top-to-bottom phase calls + the three branch points: pause, empty-pickup, batch-vs-row outcome).
- The `Deno.serve` entry + method/exception glue.
- Imports from all sibling modules.

**Why push further than the C₁ split?**

- The 13 phase functions co-located in `index.ts` were already testable in principle but practically un-testable: importing one phase pulled in the whole file's top-level type declarations and the `Deno.serve` side-effect. Splitting them into purpose-named modules makes each phase importable from a future test file with no incidental dependencies.
- Future extensions (deferred from the parent change: batch splitting, self-assigned job IDs, attribution reconciliation join) all sit cleanly in `ads-api.ts` / `batches.ts` / a new module. The current single-file layout would force them to land as more 30-line additions to `handlePost`.
- Operational debugging: searching for "where does the pause state get written?" yields exactly one file (`pause-state.ts`). Searching for "what fields do we write when a row is marked excluded?" yields exactly `outcomes.ts`.

**No behavior change.** Every extracted phase performs the same DB calls and emits the same log lines as today. The spec-compliance fixes in section A are applied inside the extracted phases (already done in C₁; the C₂ split moves the same code without re-editing the SQL).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `conversion-upload`: Adds defensive bounds-check scenario for per-row error indices, and tightens the "expired row", "no-identifier excluded", and "batch-level failure" scenarios to require nulling stale structured-error columns when the row transitions into a state where they would be misleading. No new lifecycle values, no schema changes.

## Impact

- **Code** — [supabase/functions/google-ads-conversion-upload/index.ts](supabase/functions/google-ads-conversion-upload/index.ts) shrinks to ~70 lines (orchestration + `Deno.serve` entry). Eleven sibling modules sit alongside it: three pure-helper modules from C₁ (`error-parsing.ts`, `disposition.ts`, `hashing.ts`) and eight new purpose-named modules from C₂ (`types.ts`, `runtime.ts`, `pause-state.ts`, `pickup.ts`, `payload-builder.ts`, `ads-api.ts`, `batches.ts`, `outcomes.ts`). Each is independently importable. The four spec-compliance fixes live inside the appropriate extracted phases (`selectAndExpire` in `pickup.ts`, `markNoIdExcluded` + `handleBatchFailure` in `outcomes.ts`, the success-path null in `outcomes.ts`, the bounds check already in `error-parsing.ts`).
- **Database** — no schema change. The fixes only change the *values* written by the edge function; existing CHECK constraints and the `vw_gads_conversion_uploads` view are unaffected.
- **Linter** — `deno lint` on this file drops from 5 findings to 3 (the remaining 3 are project-wide `no-import-prefix` issues handled separately).
- **Tests** — the new helper modules are importable for unit-style fixture tests; this change does not add a test harness (none exists in `supabase/functions/` today), it only unblocks one.
- **Downstream consumers** — the FE reads `vw_gads_conversion_uploads`. After the fixes, queued/excluded rows that previously projected a contradictory `disposition` will project `NULL` disposition. The Needs Attention inbox already filters by `lifecycle = 'needs-attention'`, so it will not be affected; the Batches drill-down may show rows with `error_code = NULL` where it previously showed stale codes — which is the correct state.
- **Rollback** — pure code change; revert the PR to undo.
