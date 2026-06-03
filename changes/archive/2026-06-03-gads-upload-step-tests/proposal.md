## Why

The Google Ads conversion upload edge function has been refactored into eleven small modules ([pause-state.ts](supabase/functions/google-ads-conversion-upload/pause-state.ts), [pickup.ts](supabase/functions/google-ads-conversion-upload/pickup.ts), [payload-builder.ts](supabase/functions/google-ads-conversion-upload/payload-builder.ts), [batches.ts](supabase/functions/google-ads-conversion-upload/batches.ts), [ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts), [hashing.ts](supabase/functions/google-ads-conversion-upload/hashing.ts), [error-parsing.ts](supabase/functions/google-ads-conversion-upload/error-parsing.ts), [outcomes.ts](supabase/functions/google-ads-conversion-upload/outcomes.ts), [runtime.ts](supabase/functions/google-ads-conversion-upload/runtime.ts), [disposition.ts](supabase/functions/google-ads-conversion-upload/disposition.ts), [index.ts](supabase/functions/google-ads-conversion-upload/index.ts)). Only two of them (`outcomes.ts` and `error-parsing.ts`) have unit tests today, leaving the other nine seams covered only by manual end-to-end runs against a live Google Ads account. A regression in any of `selectAndExpire`, `classifyRows`, `buildPayloads`, `createBatch`, `markSending`, `checkPipelinePause`, `hashEmail/hashPhone`, `parseRequestScope`, or `callGoogleAds`'s mock branch would land in production silently.

Because we already shipped the `_mock_response` test hook on the request body and the disposition-driven state machine, every step is now mock-friendly. The missing piece is per-step unit tests and one orchestrator-level test (using the existing mock hook) that proves every branch of [index.ts](supabase/functions/google-ads-conversion-upload/index.ts:handlePost) routes correctly without going to Google.

## What Changes

- Add per-module unit test files alongside each module in [supabase/functions/google-ads-conversion-upload/](supabase/functions/google-ads-conversion-upload/) so every exported function has at least one happy-path test plus tests for each documented failure branch.
- Extend [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts) only where it already covers the right module; new modules get their own `*.test.ts` files.
- Add an `index.test.ts` orchestrator test that exercises `handlePost` end-to-end using a fake Supabase client and the `_mock_response` test hook, covering: pause exit, no-eligible exit, no-uploadable exit, classify-skip-only exit, batch success, per-row partial failure, batch-level failure with pause trip, batch-level failure without pause trip.
- Add a single `npm`/`deno` script entry that runs every `*.test.ts` under the function directory so CI and developers run the same command.
- Document the existing fake-Supabase helper in [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts) as a shared `test-helpers.ts` so new test files don't reinvent it.
- No production code changes. If a test reveals a real bug, the fix lands as a follow-up change, not under this scope.

## Capabilities

### New Capabilities

- `gads-upload-step-tests`: Per-module test coverage requirements for the Google Ads conversion upload edge function — defines which functions must have unit tests, what branches each test must exercise, the shared fake-Supabase pattern, and the orchestrator-level integration test that uses the `_mock_response` hook to prove `handlePost` routes correctly end-to-end.

### Modified Capabilities

<!-- None. This change is test-coverage-only; no edge function behavior changes. -->

## Impact

- **Edge function tests** — new files alongside each module: `pause-state.test.ts`, `pickup.test.ts`, `payload-builder.test.ts`, `batches.test.ts`, `ads-api.test.ts`, `hashing.test.ts`, `runtime.test.ts`, `disposition.test.ts`, `error-parsing.test.ts` (standalone, even though some cases are covered indirectly by `outcomes.test.ts`), and `index.test.ts`. Existing `outcomes.test.ts` stays.
- **Shared test helpers** — new `test-helpers.ts` extracting the `createFakeSupabase()` factory from the existing test file. Existing test file updates its imports.
- **Tooling** — one new npm-style script in [horizon-dashboard/package.json](horizon-dashboard/package.json) or a top-level `deno task` definition pointing at the function test directory. No new runtime dependencies; tests use `https://deno.land/std@0.224.0/assert/mod.ts` like the existing file.
- **CI** — if a CI pipeline exists for Deno tests, it picks up the new files automatically once the script entry is added. (If not, the script is at least documented in the change so the team can wire it later.)
- **No production code changes.** The proposal is strictly additive on the test surface. Any bug a new test catches is filed as a follow-up.
- **No schema or API changes.** The `_mock_response` request-body hook already exists in [runtime.ts](supabase/functions/google-ads-conversion-upload/runtime.ts) and is used by `index.test.ts` to drive `handlePost` without an HTTP call.
