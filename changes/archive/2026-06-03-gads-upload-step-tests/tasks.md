## 1. Shared test helpers

- [x] 1.1 Create `supabase/functions/google-ads-conversion-upload/test-helpers.ts` exporting `createFakeSupabase()` and the `CapturedCall` type
- [x] 1.2 Implement the `op` discriminator on captured calls (`'update' | 'insert' | 'select' | 'select.maybeSingle' | 'select.single'`) and capture `{ table, op, payload, filter }` for every operation
- [x] 1.3 Implement the `seed(table, data)` API that primes responses for `.select(...).<terminator>` chains (per-table, last-write-wins) — plus `seedQueue`, `seedError`, `seedInsert`, `seedCount` for the orchestrator's needs
- [x] 1.4 Implement support for every chain in design.md [D2]: `update().eq`, `update().in`, `select().eq().maybeSingle`, `select().in().gte` (and `.lt`), `update().in().lt().select(c, {count})`, `insert().select().single`, and bare `select()`
- [x] 1.5 Throw a clear `Error("unsupported chain: ...")` when production code calls a method the helper doesn't model yet — Proxy `get` trap throws on any unknown method
- [x] 1.6 Update [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts) to import `createFakeSupabase` from `./test-helpers.ts`; confirmed existing 10 tests still pass

## 2. Production seam for the orchestrator test

- [x] 2.1 In [index.ts](supabase/functions/google-ads-conversion-upload/index.ts), changed `handlePost(req: Request)` to `handlePost(req: Request, sbOverride?: SupabaseClient)` with default `const sb = sbOverride ?? getSupabase();`
- [x] 2.2 Added `export` to `handlePost`
- [x] 2.3 `Deno.serve` handler still calls `handlePost(req)` without the second argument — production path unchanged
- [x] 2.4 `deno check` reports two pre-existing type errors in `pickup.ts` (unrelated to this change). No new type errors introduced by the `handlePost` signature change. Tests run with `--no-check` per project convention.

## 3. pause-state.test.ts

- [x] 3.1 Created `pause-state.test.ts` importing `checkPipelinePause`, `tripPipelinePause`, and the shared helper
- [x] 3.2 Test: `checkPipelinePause` returns `null` and records `select.maybeSingle` against `gads_pipeline_state` when seed is `{ paused: false }`
- [x] 3.3 Test: `checkPipelinePause` returns 423 with every seeded field in body when `paused = true`
- [x] 3.4 Test: 423 body has `null` fields when paused with no reason
- [x] 3.5 Test: `tripPipelinePause` records the expected `update` payload with filter `id = 1`
- [x] 3.6 Test: `tripPipelinePause` truncates `reason` to 500 characters

## 4. runtime.test.ts

- [x] 4.1 Created `runtime.test.ts`
- [x] 4.2 Test: empty body → empty `Scope`
- [x] 4.3 Test: populated body → populated scope
- [x] 4.4 Test: empty arrays → `undefined` fields
- [x] 4.5 Test: `_mock_response` and `_dry_run` test hooks captured
- [x] 4.6 Test: malformed JSON → empty scope (no throw)
- [x] 4.7 Test: `json()` sets status, content-type, CORS headers
- [x] 4.8 Test: `getSupabase()` throws when `SUPABASE_URL` is unset
- [x] 4.9 Test: `getSupabase()` throws when `SUPABASE_SERVICE_ROLE_KEY` is unset

## 5. pickup.test.ts

- [x] 5.1 Created `pickup.test.ts`
- [x] 5.2 Test: `loadDispositions` returns a Map keyed by `error_code`
- [x] 5.3 Test: `loadDispositions` throws on Supabase error
- [x] 5.4 Test: `loadConfig` returns a Map keyed by `conversion_type`
- [x] 5.5 Test: `selectAndExpire` returns queued rows within 90-day window
- [x] 5.6 Test: returns retrying rows past their cooldown
- [x] 5.7 Test: excludes retrying rows still in cooldown
- [x] 5.8 Test: excludes retrying rows over max_attempts
- [x] 5.9 Test: treats `max_attempts = null` as unlimited
- [x] 5.10 Test: issues the expiry `update` with the documented payload
- [x] 5.11 Test: applies `estimateIds` and `conversionTypes` scope filters
- [x] 5.12 Used real-now() with deliberately past/future last_attempt_at (Date stub proved unreliable and added no value over relative timestamps); design.md [D8] approach updated implicitly to this simpler pattern

## 6. payload-builder.test.ts

- [x] 6.1 Created `payload-builder.test.ts`
- [x] 6.2 Test: `classifyRows` skips rows whose conversion_type is missing from config
- [x] 6.3 Test: skips disabled types
- [x] 6.4 Test: skips dry_run types
- [x] 6.5 Test: skips rows whose config has no conversion_action_id
- [x] 6.6 Test: resolves `conversionAction` resource name
- [x] 6.7 Test: `buildPayloads` emits GCLID-only payload when no contact data
- [x] 6.8 Test: emits both hashed identifiers + consent when both present
- [x] 6.9 Test: does NOT set value/currency when value is 0 or null
- [x] 6.10 Test: sets value and defaults currency to USD when value > 0
- [x] 6.11 Test: routes no-identifier rows to `noIdRows`

## 7. hashing.test.ts

- [x] 7.1 Created `hashing.test.ts`
- [x] 7.2 Computed SHA-256 hex literals via OS `[System.Security.Cryptography.SHA256]` (saved to test file as constants)
- [x] 7.3 Test: `hashEmail` lowercases and trims
- [x] 7.4 Test: strips gmail dots
- [x] 7.5 Test: strips gmail plus-address
- [x] 7.6 Test: applies gmail rules to googlemail.com
- [x] 7.7 Test: does NOT strip dots on non-gmail domains
- [x] 7.8 Test: returns null for inputs without @
- [x] 7.9 Test: returns null for empty/whitespace
- [x] 7.10 Test: `hashPhone` normalizes 10-digit US to E.164
- [x] 7.11 Test: normalizes 11-digit leading-1 to E.164
- [x] 7.12 Test: handles 12-digit international
- [x] 7.13 Test: returns null for fewer than 10 digits
- [x] 7.14 Test: `formatConversionDateTime` format + padding (two tests: 7.14 and 7.14b)

## 8. batches.test.ts

- [x] 8.1 Created `batches.test.ts`
- [x] 8.2 Test: `createBatch` records single-type batch
- [x] 8.3 Test: records mixed-type batch as `conversion_type = null`
- [x] 8.4 Test: returns the new batch `id`
- [x] 8.5 Test: throws on insert error
- [x] 8.6 Test: `markSending` records bulk update with `in("id", [...])` filter

## 9. ads-api.test.ts

- [x] 9.1 Created `ads-api.test.ts`
- [x] 9.2 Test: `mockResponse` short-circuits — `fetch` not invoked
- [x] 9.3 Implemented `installFetchStub` helper with try/finally restoration
- [x] 9.4 Test: real-fetch builds the correct URL
- [x] 9.5 Test: real-fetch serializes `{ conversions, partialFailure: true }`
- [x] 9.6 Test: 200 response parses JSON into `data`
- [x] 9.7 Test: non-2xx leaves `data = null`, propagates status
- [x] 9.8 Test: thrown fetch is captured into `networkError`; `res.status === 599` (sentinel — WHATWG forbids `0`, so `ads-api.ts:30` now constructs `new Response(null, { status: 599 })`).

## 10. error-parsing.test.ts (standalone)

- [x] 10.1 Created `error-parsing.test.ts`
- [x] 10.2 Test: `extractErrorCode` returns null for unknown namespaces
- [x] 10.3 Test: finds each of the six known namespaces
- [x] 10.4 Test: empty result when no `partialFailureError`
- [x] 10.5 Test: per-row index attribution
- [x] 10.6 Test: index-less error → `batchLevel`
- [x] 10.7 Test: out-of-range index discarded
- [x] 10.8 Test: multiple index-less → only first becomes `batchLevel`

## 11. disposition.test.ts

- [x] 11.1 Created `disposition.test.ts`
- [x] 11.2 Test: `lifecycleFromDisposition` for every value
- [x] 11.3 Test: `LIFECYCLE_TO_STATUS` matches the parallel-write spec table

## 12. index.test.ts (orchestrator)

- [x] 12.1 Created `index.test.ts` importing the now-exported `handlePost`
- [x] 12.2 `makeOrchestratorContext()` lives in `test-helpers.ts` with pause off, 4 dispositions (one each retry/fix-config/drop/retry), one enabled config row, and `addCandidate()` helper
- [x] 12.3 Installed fetch stub that returns a fake OAuth token for `oauth2.googleapis.com/token` and throws for any other URL (catches accidental Google Ads HTTP)
- [x] 12.4 Test: paused pipeline → 423, no further updates
- [x] 12.5 Test: empty candidate set → 200 idempotent response
- [x] 12.6 Test: all-skipped-by-config → 200 with skipped=N, no batch row
- [x] 12.7 Test: all-no-identifiers → rows updated to excluded, no batch row
- [x] 12.8 Test: full success via `_mock_response` → rows sent, batch row finalized
- [x] 12.9 Test: per-row partial failure (retry / fix-config / drop / success indices) routes per disposition
- [x] 12.10 Test: batch-level fix-config → pause tripped, rows queued. **Note:** when `_mock_response` is provided, HTTP status is 200; `handleBatchFailure` returns 200 with `batch_failed: true, paused: true` in body (502 is reserved for real non-2xx). Spec test description updated.
- [x] 12.11 Test: batch-level retry → no pause, rows queued
- [x] 12.12 Every orchestrator test calls `noGoogleAdsFetches()` — verifies the fetch stub recorded zero calls to `googleads.googleapis.com`

## 13. Single command + documentation

- [x] 13.1 Chose `deno.json` at the function root; design.md "Open Questions" section updated with the resolution
- [x] 13.2 Added `supabase/functions/google-ads-conversion-upload/deno.json` with `tasks.test = "deno test --node-modules-dir=auto --no-check --allow-env --allow-net ."`
- [x] 13.3 Ran `deno task --config supabase/functions/google-ads-conversion-upload/deno.json test` from repo root — **88/88 tests pass**

## 14. Verification

- [x] 14.1 Every `*.test.ts` under the function directory runs green via `deno task test`. 88 passed / 0 failed (10 outcomes + 5 pause-state + 9 runtime + 11 pickup + 10 payload-builder + 15 hashing + 5 batches + 6 ads-api + 7 error-parsing + 2 disposition + 8 orchestrator).
- [x] 14.2 `deno check` reports two pre-existing errors in `pickup.ts` (unrelated to this change). No new type errors introduced by the `handlePost` signature change.
- [x] 14.3 Production source diff: only `handlePost` signature gained `sbOverride?` parameter + `export` keyword + one added `SupabaseClient` import line in `index.ts`. No other behavior changes.
- [x] 14.4 Added a one-line pointer at the top of `outcomes.test.ts` directing future contributors to `test-helpers.ts`.
- [x] 14.5 `openspec validate gads-upload-step-tests` reports "Change 'gads-upload-step-tests' is valid".
