## Context

The `gads-conversion-error-dispositions` change shipped a 399-line `handlePost` in [supabase/functions/google-ads-conversion-upload/index.ts](supabase/functions/google-ads-conversion-upload/index.ts) plus three sibling specs (`conversion-upload`, `gads-pipeline-pause`, `phase-cell-upload`). The function is correct in the happy path. Verification against the `conversion-upload` spec surfaced four narrow defects (one of which is a soft spec gap, not a code bug), plus two local Deno lint findings. Separately, the function is large enough that the next contributor cannot test any phase in isolation, and the pure helpers (`parsePartialFailure`, `lifecycleFromDisposition`, `hashEmail`, `hashPhone`) are buried in the same file as the orchestration.

Constraints that shape this design:

- **No DB schema change.** The four spec-compliance fixes only change column *values*, not column shapes. The CHECK constraint on `(lifecycle, status)` from `20260518000001_gads_error_dispositions_schema.sql` continues to be sufficient.
- **No behavior change beyond the four named fixes.** The refactor must produce byte-identical DB writes for every existing scenario.
- **One file stays the deployment unit.** Supabase edge functions deploy a single bundled artifact. Splitting into sibling modules is fine (the Deno bundler resolves relative imports at deploy time), but the orchestration must stay in `index.ts` so a reader sees the pipeline in one place.
- **No new test harness in this change.** `supabase/functions/` has no test setup today. Refactoring for testability is the goal; *adding* tests is a follow-up.

## Goals / Non-Goals

**Goals:**

- Bring the edge function into compliance with the four `conversion-upload` spec scenarios where it currently deviates (expired error_detail; clearing stale `error_code` on excluded and on batch-failure transitions; defensive bounds check on per-row error index).
- Eliminate the two `require-await` lint errors local to this file.
- Decompose `handlePost` into ~13 named phase functions so each phase is readable on a single screen and is independently testable.
- Extract the pure helpers (error parsing, lifecycle mapping, hashing/formatting) into sibling modules so they can be imported into a future test file without dragging the whole edge function in.

**Non-Goals:**

- Adding a test harness or test files. The refactor unblocks tests; writing them is a separate change.
- Fixing the project-wide `no-import-prefix` / `no-unversioned-import` lint findings. Those affect 13 edge functions; they belong in a cross-cutting change that adds a `deno.json` imports map.
- Changing any spec values, the CHECK constraint, the view, or the migrations.
- Restructuring the disposition lookup, the pickup query, the pause flow, or the parallel-write mapping.
- Adding `error_code` clearing on the success path. The success path already nulls `error_code` / `error_namespace` / `error_detail` at [index.ts:581-583](supabase/functions/google-ads-conversion-upload/index.ts#L581-L583).

## Decisions

### D1. Spec-compliance fix: write `error_detail` (not `error_message`) on 90-day expiry

**Decision:** Change the expiry UPDATE at [index.ts:309-318](supabase/functions/google-ads-conversion-upload/index.ts#L309-L318) to write `error_detail: { reason: "Outside Google Ads 90-day conversion window" }` and stop writing `error_message`. Continue to set `lifecycle = 'expired'` and `status = 'expired'`.

**Why:**
- The `conversion-upload` spec ("Pending row outside 90-day window is expired") explicitly names `error_detail` as the column. Writing `error_message` instead is a straight deviation.
- Internal consistency: the no-id-excluded path at [index.ts:402-403](supabase/functions/google-ads-conversion-upload/index.ts#L402-L403) already writes `error_detail` for the analogous "we knew up front this row could not succeed" case. Two adjacent code paths writing the same kind of fact to different columns is a smell that has now produced a real spec deviation.
- The legacy `error_message` column is bound for deprecation (per the parent change's section H). Writing to it for a *new* class of row (expired rows) extends its lifetime for no reason.

**Alternatives considered:**
- *Write both columns.* Rejected: duplicates data and confuses the deprecation story. The spec is the single source of truth.
- *Leave it and update the spec to say `error_message`.* Rejected: `error_detail` is the structured column intended for forensic state; expiry-reason fits there. Aligning the code to the spec preserves the design intent.

### D2. Spec-compliance fix: clear stale `error_code` on `excluded` transition

**Decision:** Extend the no-id-excluded UPDATE at [index.ts:399-405](supabase/functions/google-ads-conversion-upload/index.ts#L399-L405) to additionally write `error_code: null`, `error_namespace: null`, and to put the existing reason into `error_detail` exactly as today. Concretely:

```ts
sb.from("gads_conversion_uploads").update({
  lifecycle: "excluded",
  status: LIFECYCLE_TO_STATUS.excluded,
  error_code: null,
  error_namespace: null,
  error_detail: { reason: "no GCLID and no enhanced-conversion identifiers" },
}).eq("id", row.id)
```

**Why:**
- A row that was `lifecycle = 'retrying'` carries a non-NULL `error_code` from the prior failure (e.g., `userDataError.HASHED_FORMAT_REQUIRED`). On a later cron tick the row may have lost identifiers (data drift) and now get marked `'excluded'`. The view `vw_gads_conversion_uploads` LEFT JOINs `error_code → gads_error_dispositions` to project `disposition`. An `'excluded'` row that still has the old `error_code` will project `disposition = 'retry'` — meaningless, because the row is terminal.
- The view assumption baked into `gads-needs-attention-inbox` and `gads-error-dispositions` specs is that `(lifecycle, error_code, disposition)` is internally consistent. The fix re-establishes that invariant at the write site.
- `error_detail` is overwritten (not nulled) because the new structured reason ("no GCLID and no identifiers") is more useful for forensics than the prior partial-failure payload from a transient retry.

**Alternatives considered:**
- *Add a SQL trigger that nulls `error_code` whenever `lifecycle` transitions to a terminal state.* Rejected: spreads the invariant logic between code and DB, hard to reason about during incidents.
- *Recompute the inconsistency in the view (e.g., `CASE WHEN lifecycle IN ('excluded', 'queued', 'sent') THEN NULL ELSE disposition END`).* Rejected: papers over a write-site bug, costs nothing to fix at the source, and the view should reflect what's actually stored.

### D3. Spec-compliance fix: clear stale `error_code` on batch-failure-back-to-queued transition

**Decision:** Extend the per-row UPDATE in the batch-failure branch at [index.ts:502-513](supabase/functions/google-ads-conversion-upload/index.ts#L502-L513) to additionally write `error_code: null`, `error_namespace: null`, `error_detail: null`. The row's `lifecycle` returns to `'queued'`, `status = 'pending'`, and the structured error columns are cleared because *this row* did not individually fail — the batch did.

**Why:**
- Same view-consistency argument as D2: `vw_gads_conversion_uploads` projects `disposition` based on `error_code`. A `'queued'` row with a stale `error_code` from a prior partial-failure attempt would show a bogus disposition in the Batches drill-down and any debug view.
- The batch row itself carries the batch-level error (`request_error_code`, `request_error_message`), so we are not losing forensic information by clearing the per-row columns — the cause of *this batch's* failure is recorded against the batch.
- This is consistent with the `gads-pipeline-pause` spec's "rows from the failed batch SHALL be eligible for the next cron pickup": eligibility implies `lifecycle = 'queued'`, and a queued row with no `last_attempt_at`-based retry-timing constraint should have no `error_code` either.

**Alternatives considered:**
- *Leave `error_code` populated as a record of the last per-row error.* Rejected: it's not actually the last per-row error from *this* attempt (this attempt was a batch failure), so the column would lie about its meaning. The batch row is the right home for the batch-failure record.
- *Move the row to `lifecycle = 'retrying'` instead of `queued` to honor `retry_after_seconds`.* Rejected: the row's prior `error_code` is stale; honoring its `retry_after_seconds` would be honoring the wrong throttle. The pipeline-pause flag (when applicable) is the throttle for batch failures.

### D4. Spec-compliance fix: defensive bounds check on per-row error index

**Decision:** Inside `parsePartialFailure` at [index.ts:177-218](supabase/functions/google-ads-conversion-upload/index.ts#L177-L218), accept the conversions-array length as a second parameter and discard any per-row index that is `< 0` or `>= length`. Log the discarded entry at `console.warn` level so it surfaces in the function logs without breaking the run. Specifically:

```ts
function parsePartialFailure(
  response: Record<string, unknown>,
  conversionsCount: number,
): ParsedPartialFailure {
  // ... existing logic, but:
  if (rowIndex >= 0) {
    if (rowIndex < conversionsCount) {
      perRow.set(rowIndex, rowError);
    } else {
      console.warn(`parsePartialFailure: out-of-range index ${rowIndex} (batch size ${conversionsCount}), code=${key}`);
    }
  } else if (!batchLevel) {
    batchLevel = rowError;
  }
}
```

The caller at [index.ts:475](supabase/functions/google-ads-conversion-upload/index.ts#L475) passes `toUpload.length`.

**Why:**
- Today's loop at [index.ts:547-549](supabase/functions/google-ads-conversion-upload/index.ts#L547-L549) does `for (let i = 0; i < toUpload.length; i++) { const rowError = perRowErrors.get(i); ... }`. If Google returns an index ≥ `toUpload.length` (parser/API drift, malformed response), the `Map` entry is stored but never consumed — the corresponding row gets marked `sent` because no error matched its `i`. A row that was actually rejected by the API would be falsely recorded as accepted, and the accepted/rejected counts on the batch row would be wrong.
- The fix happens at the parser, not the loop, because the parser is the single funnel for response data. Adding a `for (const [idx, _] of perRowErrors) if (idx >= toUpload.length) warn` after parsing is redundant.
- `console.warn` (not `throw`) because batch processing should continue: a malformed per-row index does not invalidate the whole response, only that one entry. The batch row will still record an accurate `accepted_count` / `rejected_count` for the rows we *did* process.

**Alternatives considered:**
- *Throw on out-of-range index and fail the batch.* Rejected: turns a Google-side anomaly into a self-inflicted batch failure, which would re-enqueue the rows and re-burn quota.
- *Mark the over-range row as `needs-attention` with a synthetic `error_code`.* Rejected: there is no over-range row to mark — by definition the index doesn't correspond to a row in `toUpload`. The only sane action is to log and discard.

### D5. Linter fix: drop `async` from `hashEmail` and `hashPhone`

**Decision:** Both functions return the `Promise` from `sha256hex(...)` directly. Drop the `async` keyword and the `Promise<string | null>` return type stays unchanged. Callers (`await hashEmail(...)`) work identically.

**Why:** `require-await` is a real lint rule that catches a class of bugs (a function declared `async` for documentation but accidentally synchronous). The proper signal is "this returns a Promise" via the explicit return type, not the `async` keyword. Callers do not need to change.

### D6. Refactor: split pure helpers into sibling modules; keep orchestration in `index.ts`

**Decision:** Three new files alongside `index.ts`:

- `error-parsing.ts` exports `parsePartialFailure`, `extractErrorCode`, `KNOWN_ERROR_NAMESPACES`, `ParsedRowError`, `ParsedPartialFailure`.
- `disposition.ts` exports `Lifecycle`, `LIFECYCLE_TO_STATUS`, `Disposition`, `DispositionRow`, `lifecycleFromDisposition`.
- `hashing.ts` exports `sha256hex`, `hashEmail`, `hashPhone`, `formatConversionDateTime`.

`index.ts` keeps:
- `corsHeaders`, `json`, `getSupabase` (HTTP / env / Supabase glue — only useful here)
- All domain interfaces local to the handler (`PendingRow`, `ConfigRow`, `CustomerData`, `UserIdentifier`, `AdsConversion`, `UploadRequestBody`)
- The 13 phase functions (D7) + `handlePost` + `Deno.serve` glue

**Why:**
- The three extracted modules are pure (no Deno globals, no Supabase client). They can be imported into a future test file with no mocking.
- Keeping the orchestration in `index.ts` preserves "open one file, read the pipeline" — the chief readability win the refactor is trying to deliver.
- Supabase edge function bundling resolves relative imports at deploy time; no new tooling required.

**Alternatives considered:**
- *One big `helpers.ts`.* Rejected: bundles unrelated concerns (parsing, mapping, hashing) into one import surface and obscures what's pure vs. what isn't.
- *Move the phase functions into separate files too.* Rejected: the phases are not pure (they take `sb` and mutate DB) and their value is being readable together. Splitting them spreads the pipeline across 13 files.

### D7. Refactor: extract 13 phase functions inside `index.ts`

**Decision:** `handlePost` is decomposed into the phases listed below. Each phase corresponds to one of the original `// ── N. ──` comment blocks. Phases that early-return drive control flow back to `handlePost` via either a `Response` (signaling "we're done") or a discriminated result.

| Phase function | Inputs | Output | Original lines |
|---|---|---|---|
| `checkPipelinePause(sb)` | sb | `Response \| null` | 227-244 |
| `parseRequestScope(req)` | req | `{ estimateIds?, conversionTypes? }` | 247-258 |
| `loadDispositions(sb)` | sb | `Map<string, DispositionRow>` | 261-268 |
| `selectAndExpire(sb, scope, dispositionMap)` | sb, scope, map | `PendingRow[]` | 270-324 |
| `loadConfig(sb)` | sb | `Map<string, ConfigRow>` | 327-331 |
| `classifyRows(pending, configMap, cfg)` | pending, cfg | `{ uploadable, skippedRows }` | 334-350 |
| `buildPayloads(uploadable)` | uploadable | `{ toUpload, noIdRows }` | 353-407 (incl. mark-excluded) |
| `markNoIdExcluded(sb, noIdRows)` | sb, noIdRows | `void` | 396-407 (extracted) |
| `createBatch(sb, toUpload)` | sb, toUpload | `string` (batchId) | 421-436 |
| `markSending(sb, ids, batchId)` | sb, ids, batchId | `void` | 439-443 |
| `callGoogleAds(toUpload, cfg, accessToken)` | toUpload, cfg, token | `{ res, data, networkError }` | 446-466 |
| `handleBatchFailure(sb, batchId, ...)` | sb, batchId, ... | `Response` | 468-540 |
| `applyPerRowOutcomes(sb, batchId, toUpload, perRowErrors, dispositionMap, httpStatus, jobId)` | ... | `Response` | 542-619 |

`handlePost` reads top-to-bottom in ~60 lines:

```ts
async function handlePost(req: Request): Promise<Response> {
  const sb = getSupabase();
  const cfg = getAdsConfig();

  const pauseResp = await checkPipelinePause(sb);
  if (pauseResp) return pauseResp;

  const scope = await parseRequestScope(req);
  const dispositionMap = await loadDispositions(sb);

  const pending = await selectAndExpire(sb, scope, dispositionMap);
  if (pending.length === 0)
    return json({ uploaded: 0, skipped: 0, errored: 0, message: "No eligible conversions" });

  const configMap = await loadConfig(sb);
  const { uploadable, skippedRows } = classifyRows(pending, configMap, cfg);
  if (uploadable.length === 0)
    return json({ uploaded: 0, skipped: skippedRows.length, errored: 0 });

  const accessToken = await getAccessToken(cfg);
  const { toUpload, noIdRows } = await buildPayloads(uploadable);
  if (noIdRows.length > 0) await markNoIdExcluded(sb, noIdRows);
  if (toUpload.length === 0)
    return json({ uploaded: 0, skipped: skippedRows.length + noIdRows.length, errored: 0 });

  const batchId = await createBatch(sb, toUpload);
  await markSending(sb, toUpload.map(x => x.row.id), batchId);

  const { res, data, networkError } = await callGoogleAds(toUpload, cfg, accessToken);
  const parsed = data ? parsePartialFailure(data, toUpload.length) : { perRow: new Map(), batchLevel: null };
  const batchLevelError = parsed.batchLevel && parsed.perRow.size === 0 ? parsed.batchLevel : null;
  const isBatchFailure = !res.ok || networkError !== null || batchLevelError !== null;

  if (isBatchFailure)
    return handleBatchFailure(sb, batchId, toUpload, batchLevelError, dispositionMap,
                              res.status, networkError, skippedRows.length + noIdRows.length);

  return applyPerRowOutcomes(sb, batchId, toUpload, parsed.perRow, dispositionMap,
                             res.status, (data?.jobId ?? null) as string | null,
                             skippedRows.length + noIdRows.length);
}
```

**Why:**
- Linear, no nested helper functions, no shared mutable state between phases beyond what passes through parameters.
- Each phase is small enough (~30-80 lines) to read on a single screen.
- The three branch points (pause, empty pickup, batch failure) are visible at the top level of `handlePost`.

**Alternatives considered:**
- *A `Stage[]` pipeline abstraction.* Rejected per the proposal — adds machinery for no concrete reorderability requirement.
- *A class with method-per-phase.* Rejected — Deno edge functions instantiate per request; a class adds ceremony without testability gain over plain functions.

### D8. `buildPayloads` returns `noIdRows` as data, the side effect happens separately

**Decision:** `buildPayloads` is pure-ish: it takes `uploadable` and returns `{ toUpload, noIdRows }` without writing to the DB. The actual UPDATE for `noIdRows` is in `markNoIdExcluded`, called from `handlePost`.

**Why:**
- Keeps `buildPayloads` testable with a fixture (which is half the point of the refactor).
- Separates "decide" from "do" — the natural seam for unit tests.
- `markNoIdExcluded` is the smallest possible side-effect function: one UPDATE in a `Promise.all`.

## Risks / Trade-offs

- **Refactor introduces silent regressions if a phase boundary is wrong.** [Risk] The refactor must produce byte-identical DB writes. Mistakes are easy: missing a column in an UPDATE, getting the order of operations wrong (mark-excluded vs. create-batch), passing the wrong sentinel for `httpStatus`. → **Mitigation:** the implementation tasks include a manual diff-style review pass against the original file before merge, and each phase function's body should be a literal copy of its original lines with parameter substitution only.

- **`error_code` clearing on excluded/queued transitions could mask debugging info.** [Risk] An operator looking at a queued row to debug "why did this go back to queued?" no longer sees the prior `error_code` on the row. → **Mitigation:** the prior error is still on the batch row (`request_error_code` for batch failures) or remains in the row history if we ever add an audit table. The view consistency we gain is the bigger win; the loss is recoverable from logs.

- **Defensive `console.warn` on out-of-range index does not page anyone.** [Risk] If Google starts emitting out-of-range indices systematically, the warn flows into logs without alerting. → **Mitigation:** acceptable for v1. The batch row's `rejected_count` will diverge from the `perRowErrors.size` consumed, which is itself observable in the Batches panel. If this happens in practice, the follow-up is a structured-log emission with a known label that the log pipeline can alert on.

- **Module split adds three import statements per consumer.** [Risk] Minor. → **Mitigation:** trivial; readability wins outweigh import surface.

- **Linter still reports `no-import-prefix` × 3 after this PR.** [Risk] CI may be configured to fail on lint errors. → **Mitigation:** check CI before merge. If CI does fail, the `deno.json` imports-map work is a prerequisite, not a follow-up — bump it into this change. Default assumption: CI either does not run `deno lint` on edge functions or treats these specific rules as warnings; verify during task 6.

## Migration Plan

Single PR, single deploy. No DB migration. Steps:

1. Create the three sibling modules (`error-parsing.ts`, `disposition.ts`, `hashing.ts`) with the extracted code. Drop `async` from `hashEmail` / `hashPhone` in the move.
2. Rewrite `index.ts` to import from the new modules and house the 13 phase functions + the slimmed `handlePost`.
3. Apply the four spec-compliance fixes (D1–D4) inside the relevant extracted phases.
4. Run `deno lint` to confirm `require-await` is gone (5 → 3 findings expected).
5. Deploy to a staging Supabase project; trigger a manual invocation with a small batch of seeded rows; verify the function logs the same set of "UPLOADED" / "ROW_FAILED" / "expired" lines as before.
6. Deploy to production.

**Rollback:** revert the PR. No DB state is affected by the rollback — the new column-clearing behavior just produces nicer view rows; rolling back leaves slightly inconsistent rows that the next forward-fix re-cleans.

## Open Questions

- **Are there other edge functions that read `gads_conversion_uploads.error_message` directly?** A grep should clear this up during implementation. If yes, those callers may rely on the legacy expired-row error_message being populated; we'd need to either also write the new field or migrate those callers in this PR.
- **Should the defensive bounds check also fire if Google returns more total per-row errors than `toUpload.length`?** The current decision only checks each index. A separate "count mismatch" assertion (e.g., `parsed.perRow.size > toUpload.length` → warn) would catch a different anomaly. Defer to task 5 reviewer call — cheap to add if desired.
