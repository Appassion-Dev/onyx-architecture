## Context

[supabase/functions/google-ads-conversion-upload/](supabase/functions/google-ads-conversion-upload/) was decomposed (as part of `gads-upload-fix-and-refactor` and `gads-conversion-error-dispositions`) from a monolithic `index.ts` into eleven small modules. The decomposition was deliberate — each module has a narrow contract that is well-suited to unit testing — but the test surface lagged. [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts) covers `applyPerRowOutcomes`, `handleBatchFailure`, `markNoIdExcluded`, and indirectly `parsePartialFailure` / `extractErrorCode`. Nine other modules have zero coverage.

The cron path goes through every module on every successful run:

```
handlePost
 ├─ checkPipelinePause          (pause-state.ts)        ← UNTESTED
 ├─ parseRequestScope            (runtime.ts)            ← UNTESTED
 ├─ loadDispositions             (pickup.ts)             ← UNTESTED
 ├─ selectAndExpire              (pickup.ts)             ← UNTESTED
 ├─ loadConfig                   (pickup.ts)             ← UNTESTED
 ├─ classifyRows                 (payload-builder.ts)    ← UNTESTED
 ├─ buildPayloads                (payload-builder.ts)    ← UNTESTED
 │   └─ hashEmail / hashPhone    (hashing.ts)            ← UNTESTED
 │       └─ sha256hex            (hashing.ts)            ← UNTESTED
 │   └─ formatConversionDateTime (hashing.ts)            ← UNTESTED
 ├─ markNoIdExcluded             (outcomes.ts)           ✓ tested
 ├─ createBatch                  (batches.ts)            ← UNTESTED
 ├─ markSending                  (batches.ts)            ← UNTESTED
 ├─ callGoogleAds (mock branch)  (ads-api.ts)            ← UNTESTED
 ├─ parsePartialFailure          (error-parsing.ts)      ✓ tested indirectly
 ├─ handleBatchFailure           (outcomes.ts)           ✓ tested
 │   └─ tripPipelinePause        (pause-state.ts)        ← UNTESTED directly
 └─ applyPerRowOutcomes          (outcomes.ts)           ✓ tested
```

Constraints that shape the design:

- **Deno test runtime.** The edge function is Deno-native. Tests must run as `deno test`, not Vitest/Jest. The existing `outcomes.test.ts` is the format reference.
- **Mock-friendly already.** [runtime.ts](supabase/functions/google-ads-conversion-upload/runtime.ts) accepts `_mock_response` on the request body and threads it through to [ads-api.ts:callGoogleAds](supabase/functions/google-ads-conversion-upload/ads-api.ts) where a non-undefined `mockResponse` short-circuits the real HTTP call. The orchestrator-level test relies on this hook; no new production code is needed.
- **No live network.** Tests must not call Google Ads or Supabase. All Supabase calls go through the existing fake-client shape (`from().update().eq()`, `from().select().eq().maybeSingle()`, etc.). All Google Ads calls go through the `_mock_response` hook.
- **No env coupling.** [runtime.ts:getSupabase](supabase/functions/google-ads-conversion-upload/runtime.ts) reads `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` from `Deno.env`. Tests must set/unset these without leaking state across files.
- **Test parity with existing file.** The new tests adopt the naming convention `task <ref>: <description>` so they cross-reference the tasks file from this change.

Stakeholders: the on-call engineer who currently must run a manual end-to-end against a Google Ads test account to gain confidence in any edge-function change.

## Goals / Non-Goals

**Goals:**

- Every exported function in every module has at least one happy-path unit test and one test per documented failure branch.
- One end-to-end orchestrator test exercises `handlePost` through each of its routing paths (pause / no-eligible / no-uploadable / batch-success / per-row partial-failure / batch-level failure with pause / batch-level failure without pause) using a fake Supabase client and the `_mock_response` hook.
- The fake-Supabase factory currently inlined in `outcomes.test.ts` is extracted to a shared `test-helpers.ts` module and reused across all new test files.
- A single command runs every test (`deno task test:gads-upload` or `npm run test:gads-upload`, picked during implementation).
- All new tests pass on a clean clone without environment setup beyond `deno` being on PATH.

**Non-Goals:**

- **No production code changes.** If a test surfaces a real bug, the fix is its own follow-up change. This change adds tests only.
- **No fuzzing or property-based testing.** Each test is a hand-written scenario derived from the spec.
- **No live Supabase or Google Ads integration tests.** The existing manual-test affordances cover that surface; this change does not replace them.
- **No coverage tooling.** Coverage percentages are not a hard gate; the per-module checklist in tasks.md is the gate.
- **No refactor of [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts) beyond the helper extraction.** Existing tests stay byte-similar; only the `createFakeSupabase` import path changes.

## Decisions

### D1. One test file per module, named `<module>.test.ts`, colocated with the source

**Decision:** Each module gets a sibling `*.test.ts` file in the same directory. Naming follows the existing precedent: `outcomes.test.ts` lives next to `outcomes.ts`.

**Why:**
- Discoverability — looking at a module's contract and its tests in the same directory listing is the lowest-friction reading order for a future maintainer.
- `deno test` walks recursively; no test-discovery configuration is required.
- The existing test file already follows this pattern; consistency beats novelty.

**Alternatives considered:**
- *A `__tests__/` subdirectory.* Rejected: adds a layer for no benefit when the function directory is already small (~12 files).
- *One mega test file `index.test.ts` covering everything.* Rejected: file size would balloon, and module-level focus is the whole point.

### D2. Shared `test-helpers.ts` extracts the fake-Supabase factory

**Decision:** Move `createFakeSupabase()` and its `CapturedUpdate` interface from [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts) into `supabase/functions/google-ads-conversion-upload/test-helpers.ts`. Existing tests import from there. New tests import from there. The factory is widened to support the additional shapes new tests need (`.select()`, `.insert().select().single()`, `.maybeSingle()`, `.in()`, `.gte()`, `.lt()`, `.select(..., { count: ... })`).

**Why:**
- Without a shared helper, every new test file would re-implement the same Supabase double in a slightly different shape — divergence guaranteed.
- One factory means one place to add a new query shape when production code grows.

**Shape catalogue** (factory must support these chains, all of which appear in production code today):

| Production call                                                              | Required mock shape                                       |
|------------------------------------------------------------------------------|------------------------------------------------------------|
| `sb.from(t).update(p).eq(c, v)`                                              | covered today                                              |
| `sb.from(t).update(p).in(c, [...])`                                          | new                                                        |
| `sb.from(t).select(cols).eq(c, v).maybeSingle()`                             | new (used by `checkPipelinePause`)                         |
| `sb.from(t).select(cols).in(c, [...]).gte(c, v)`                             | new (used by `selectAndExpire`)                            |
| `sb.from(t).update(p).in(c, [...]).lt(c, v).select(c, { count: 'exact' })`   | new (used by `selectAndExpire` expiry sweep)               |
| `sb.from(t).insert(p).select(c).single()`                                    | new (used by `createBatch`)                                |
| `sb.from(t).select(cols)` (no filter, returns all)                           | new (used by `loadDispositions` and `loadConfig`)           |

**Alternatives considered:**
- *Keep the fake inline per file.* Rejected — D2's whole purpose.
- *Use a Supabase test library.* Rejected — overkill for ~80 lines of hand-rolled doubles, adds a dependency, and the existing pattern is already battle-tested.

### D3. The fake Supabase records every call; assertions read from the captured log

**Decision:** The factory returns `{ sb, calls }` where `calls` is an array of `{ table, op, payload, filter }` describing every operation performed. Tests assert on the contents and order of `calls`. The factory can also be configured per-test to return specific data for `select` queries via a small `seed()` API.

```ts
const { sb, calls, seed } = createFakeSupabase();
seed("gads_pipeline_state", { paused: true, paused_reason: "terms" });
const resp = await checkPipelinePause(sb);
assertEquals(resp?.status, 423);
assertEquals(calls[0], { table: "gads_pipeline_state", op: "select.maybeSingle", filter: { id: 1 }, ... });
```

**Why:**
- The current factory captures `update().eq()` calls; widening to capture every call shape (with explicit `op` discriminator) makes tests robust against query reshuffling.
- `seed()` is the minimum primitive needed to test code that reads from Supabase. Without it, tests for `loadDispositions`, `loadConfig`, `selectAndExpire`, `checkPipelinePause` can't run.

**Alternatives considered:**
- *Per-call inline stub functions.* Rejected — too much boilerplate per test.
- *jest-style `.toHaveBeenCalledWith`.* Rejected — Deno-native, no Jest matchers available without dependency.

### D4. `handlePost` orchestrator test uses the existing `_mock_response` hook

**Decision:** Add `index.test.ts` that imports `handlePost` directly (export it from index.ts if not already exported) and drives it with synthetic `Request` objects whose JSON body sets `_mock_response`. The fake Supabase is wired through `Deno.env` + a module-level supabase-getter override, or by exporting a `setSupabaseForTests()` shim from [runtime.ts](supabase/functions/google-ads-conversion-upload/runtime.ts) — chosen during implementation, see D5.

**Why:**
- `_mock_response` is the existing production-side test hook; using it preserves the same code path the real cron takes (parseRequestScope → callGoogleAds with mock → parsePartialFailure → outcomes), differing only in the HTTP call itself. That's the highest-value end-to-end coverage we can get without a real Google account.
- Per-module tests prove each function in isolation; the orchestrator test proves the routing wiring between them.

**Branches the orchestrator test must cover** (each becomes one `Deno.test`):

| Branch                                          | How it's triggered                                                  | Expected outcome                                  |
|-------------------------------------------------|---------------------------------------------------------------------|---------------------------------------------------|
| Paused pipeline                                  | seed `gads_pipeline_state.paused = true`                            | 423 response, no API call, no row updates         |
| No eligible rows                                 | seed `gads_conversion_uploads` empty                                | 200 `{ uploaded: 0, skipped: 0 }`, no batch row   |
| Eligible rows but all `enabled=false`            | seed candidates + config with `enabled=false`                       | 200 `{ uploaded: 0, skipped: N }`, no batch row   |
| Eligible rows but all missing GCLID + identifiers| seed candidates with no GCLID, customer null                        | rows marked `excluded` via `markNoIdExcluded`     |
| Full success                                     | `_mock_response = { jobId: "...", partialFailureError: undefined }` | rows `sent`, batch row finalized, `uploaded=N`    |
| Partial failure (mixed)                          | `_mock_response` with `partialFailureError.details` for some indices| per-row routing matches outcomes.test.ts pattern  |
| Batch-level `fix-config`                         | `_mock_response` with request-level CUSTOMER_NOT_ACCEPTED error      | 502, pause tripped, rows stay queued              |
| Batch-level `retry`                              | `_mock_response` with request-level TRANSIENT_ERROR                  | 502, no pause, rows stay queued                   |
| Non-2xx HTTP                                     | `_mock_response = null` + `_dry_run = false` + env throws            | not feasible via mock; covered by ads-api test    |

The non-2xx HTTP branch is covered in `ads-api.test.ts` by stubbing `globalThis.fetch`, not in the orchestrator test — see D6.

### D5. Inject the Supabase client via dependency parameter, not environment

**Decision:** Add an optional second parameter to `handlePost(req, sbOverride?)`. Production callers pass nothing and the function calls `getSupabase()` as today. The orchestrator test passes a fake. This is the minimum-invasive seam — no module-level state, no `setSupabaseForTests`.

**Why:**
- Module-level mutable state is a footgun (test ordering matters, parallelism becomes unsafe).
- `Deno.env.set` to point at a fake Supabase is also viable but couples tests to a real HTTP-ish lib (the SDK would try to connect to the stub URL). Adding a parameter is two characters of production code change and a clean seam.
- The parameter defaults to `getSupabase()`, so production behavior is identical.

**Alternatives considered:**
- *Module-level `let supabase = getSupabase()` with a setter.* Rejected: hidden global, hard to reason about under `deno test --parallel`.
- *`Deno.env`-based stubbing.* Rejected: couples tests to the real Supabase SDK's HTTP behavior.

### D6. `ads-api.test.ts` stubs `globalThis.fetch` to cover the non-mock branch

**Decision:** Use `Deno.test`'s lifecycle to stub `globalThis.fetch` for tests that need to verify the URL, headers, request body, network-error catch, and HTTP-non-2xx handling. `mockResponse` covers the happy path; the rest needs a fetch stub.

**Why:**
- The mock branch in [ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts) bypasses `fetch` entirely, so the production fetch invocation, URL construction, header build, and JSON body serialization are untested without a fetch stub.
- The network-error branch (the `catch` that sets `networkError`) only fires when fetch throws.
- A fetch stub is one line: `const original = globalThis.fetch; globalThis.fetch = stub; try { ... } finally { globalThis.fetch = original; }`.

### D7. Hashing tests use known SHA-256 vectors

**Decision:** [hashing.test.ts](supabase/functions/google-ads-conversion-upload/hashing.test.ts) asserts exact hex outputs against precomputed SHA-256 values. Generating them at test time defeats the purpose; pin them as literals so a regression in the normalization rules (gmail dots, plus addressing, phone E.164) is loud.

**Vectors to include:**

| Input                          | Normalized        | SHA-256                                                              |
|--------------------------------|-------------------|----------------------------------------------------------------------|
| `"Test@Example.com"`           | `test@example.com`| `973dfe463ec85785f5f95af5ba3906eedb2d931c24e69824a89ea65dba4e813b`   |
| `"  john.doe+spam@gmail.com  "`| `johndoe@gmail.com`| `<computed at task time and pinned>`                                |
| `"john.doe+x@googlemail.com"`  | `johndoe@googlemail.com`| `<pinned>`                                                       |
| `"(415) 555-2671"`             | `+14155552671`     | `<pinned>`                                                          |
| `"+1-415-555-2671"`            | `+14155552671`     | `<same as above>`                                                   |
| `"5552671"` (too short)        | n/a                | resolves to `null`                                                  |
| `"plain-no-at"`                | n/a                | resolves to `null`                                                  |

The "computed at task time and pinned" entries are computed once by running `deno eval` during implementation and pasted as literals. Pinning beats regenerating.

### D8. Date-of-day-bounded `selectAndExpire` test uses a clock seam

**Decision:** `selectAndExpire` calls `new Date()` directly. Tests that need a fixed "now" stub the clock with `globalThis.Date = ClockOverride` for the test's duration. We don't introduce a clock-injection seam in production code — `Date.now()`-pinning is the same lightweight pattern used elsewhere in the codebase.

**Why:** Adding a clock-injection parameter to every function that reads `now()` is invasive for one test surface. Date-stubbing within `Deno.test` blocks is local and reversible.

## Risks / Trade-offs

- **Production code grows by one optional parameter on `handlePost`.** [Risk] [D5] adds `sbOverride?` to the entrypoint. → **Mitigation:** Default is the production `getSupabase()`. Behavior is identical when the parameter is omitted, which it always is from the `Deno.serve` handler. The diff is two lines.

- **The fake Supabase grows to mirror the real API.** [Risk] Every new query shape in production needs a corresponding shape in the fake, or tests get a runtime error mid-chain. → **Mitigation:** Tests run with `deno test`; the runtime error surfaces immediately and points at the missing method. The shape catalogue in [D2] enumerates everything used today; extending it is a known-cost task whenever production grows.

- **Hashing test vectors can drift if Google changes normalization rules.** [Risk] Pinned SHA-256 literals will fail loudly if [hashing.ts](supabase/functions/google-ads-conversion-upload/hashing.ts) changes its rules (e.g., gmail dot stripping or plus addressing). → **Mitigation:** That's the point. A pinned literal failure forces the engineer to re-verify against Google's documented hashing rules and update the test deliberately, not silently.

- **`fetch` stub leak across tests.** [Risk] If a test sets `globalThis.fetch` to a stub and throws before restoring, subsequent tests see the stub. → **Mitigation:** Wrap stubs in `try { ... } finally { globalThis.fetch = original; }`. The pattern is in the per-test boilerplate, not abstracted into the helper (an abstraction would hide the cleanup).

- **The orchestrator test repeats setup that the per-module tests already cover.** [Risk] Some redundancy is unavoidable — `index.test.ts` seeds the same disposition map and fake rows that `outcomes.test.ts` does. → **Mitigation:** A small `makeOrchestratorContext()` factory in `test-helpers.ts` produces a wired-up fake-Supabase with sensible defaults (pause off, one config row, one disposition row, one candidate row). Each branch test overrides what it needs.

- **`deno test` from a Windows shell.** [Risk] The team works on Windows; `deno` CLI is installed but some PowerShell quoting gotchas could break the script. → **Mitigation:** Use a simple `deno task test:gads-upload` definition that takes no arguments, and document the command in the change. PowerShell quirks don't bite simple invocations.

- **No coverage tooling means coverage gaps could regress.** [Risk] A future module added without a paired test would not fail the build. → **Mitigation:** Out of scope for this change. A follow-up could add `deno test --coverage` gating in CI; flagging it explicitly in the tasks as a future task lets us defer without forgetting.

## Migration Plan

This change is test-only; there is no production migration. Order:

1. Extract `test-helpers.ts` from `outcomes.test.ts`. Update existing test imports. Run `deno test` to confirm green.
2. Add the optional `sbOverride` parameter to `handlePost` ([D5]). Export `handlePost` if not already. Confirm `deno check` passes.
3. Add per-module test files in any order; each is independently mergeable.
4. Add `index.test.ts` last (depends on the helper enhancements landing first).
5. Add the `deno task` / `npm` script. Document command in the change folder.

**Rollback:** Each step is a single file (or pair). Revert the file. No DB or runtime impact.

## Open Questions

- **Where does the test command live?** **Resolved during implementation:** new `supabase/functions/google-ads-conversion-upload/deno.json` with a `test` task. Run with `deno task test` from that directory, or `deno task --config supabase/functions/google-ads-conversion-upload/deno.json test` from the repo root.
- **Should `index.test.ts` cover the cron entrypoint (`Deno.serve` handler) too, or only `handlePost`?** **Resolved:** only `handlePost`. The `Deno.serve` handler is three-line glue (OPTIONS / method check / call) and testing it requires real network. The orchestrator coverage on `handlePost` is the value.
- **CI integration.** Deferred to a follow-up. The `deno task test` command is documented; wiring it into CI is a separate change.
