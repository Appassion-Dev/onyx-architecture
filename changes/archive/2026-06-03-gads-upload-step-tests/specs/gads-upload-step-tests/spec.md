## ADDED Requirements

### Requirement: Shared Supabase test double

The system SHALL provide a `supabase/functions/google-ads-conversion-upload/test-helpers.ts` module that exports `createFakeSupabase()` returning `{ sb, calls, seed }`. The factory SHALL be the single source of fake-Supabase behavior across every `*.test.ts` file in the function directory.

#### Scenario: Captures every operation

- **WHEN** a test invokes any `sb.from(table).<chain>` ending in a terminal operator (`.eq`, `.in`, `.maybeSingle`, `.single`, or an awaited promise on `.update`/`.insert`/`.select`)
- **THEN** the helper SHALL push an object onto `calls` recording `{ table, op, payload, filter }` where `op` discriminates `'update' | 'insert' | 'select' | 'select.maybeSingle' | 'select.single'`
- **THEN** the returned promise SHALL resolve to `{ data: <seeded data or null>, error: null }`

#### Scenario: Seeded select returns table-scoped data

- **WHEN** a test calls `seed("gads_pipeline_state", { paused: true, ... })` and then production code calls `sb.from("gads_pipeline_state").select(...).eq("id", 1).maybeSingle()`
- **THEN** the resolved `data` SHALL be the seeded object
- **WHEN** no seed exists for the queried table
- **THEN** the resolved `data` SHALL be `null` for `.maybeSingle()` / `.single()` and `[]` for plain `.select(...)`

#### Scenario: Supports every production query shape

- **WHEN** any of the chains enumerated in design.md's [D2] catalogue is invoked
- **THEN** the helper SHALL resolve without throwing and SHALL record the call in `calls`
- **WHEN** a future production query uses a shape not yet supported
- **THEN** the helper SHALL throw a clear "unsupported chain" error at the missing method so the test surface fails loudly rather than silently passing

### Requirement: pause-state unit tests

The system SHALL provide `pause-state.test.ts` covering every documented branch of `checkPipelinePause` and `tripPipelinePause`.

#### Scenario: Returns null when pipeline is not paused

- **WHEN** the seeded `gads_pipeline_state` row has `paused = false`
- **THEN** `checkPipelinePause(sb)` SHALL resolve to `null`
- **THEN** the test SHALL assert `calls` shows exactly one `select.maybeSingle` against `gads_pipeline_state` with filter `{ id: 1 }`

#### Scenario: Returns 423 response when paused

- **WHEN** the seeded row has `paused = true` and populated `paused_reason`, `paused_error_code`, `paused_batch_id`, `paused_at`
- **THEN** the returned `Response` SHALL have `status = 423`
- **THEN** the JSON body SHALL include `paused: true` and each seeded field at top level

#### Scenario: Returns 423 with null fields when paused with no reason

- **WHEN** the seeded row has `paused = true` but every other field is null
- **THEN** the response body SHALL still set `paused: true` and SHALL serialize the other fields as `null` (not omit them)

#### Scenario: tripPipelinePause writes the expected payload

- **WHEN** `tripPipelinePause(sb, { reason, errorCode, batchId, at })` is invoked
- **THEN** `calls` SHALL contain one `update` against `gads_pipeline_state` with filter `{ id: 1 }` and payload `{ paused: true, paused_reason: reason.slice(0,500), paused_error_code: errorCode, paused_batch_id: batchId, paused_at: at, resumed_at: null, resumed_by: null }`

#### Scenario: tripPipelinePause truncates reason to 500 chars

- **WHEN** the reason is longer than 500 characters
- **THEN** the recorded `paused_reason` SHALL be exactly the first 500 chars

### Requirement: runtime unit tests

The system SHALL provide `runtime.test.ts` covering `parseRequestScope`, `json`, and `getSupabase`'s environment failure path.

#### Scenario: parseRequestScope returns empty scope for empty body

- **WHEN** the request body is the empty string
- **THEN** the result SHALL be `{ estimateIds: undefined, conversionTypes: undefined, mockResponse: undefined, dryRun: undefined }`

#### Scenario: parseRequestScope parses estimate_ids and conversion_types

- **WHEN** the body is `{ estimate_ids: ["a", "b"], conversion_types: ["x"] }`
- **THEN** `estimateIds` SHALL equal `["a", "b"]` and `conversionTypes` SHALL equal `["x"]`

#### Scenario: parseRequestScope ignores empty arrays

- **WHEN** the body is `{ estimate_ids: [], conversion_types: [] }`
- **THEN** both fields SHALL resolve to `undefined`

#### Scenario: parseRequestScope captures _mock_response and _dry_run

- **WHEN** the body sets `_mock_response: { jobId: "x" }` and `_dry_run: true`
- **THEN** `mockResponse` SHALL equal `{ jobId: "x" }` and `dryRun` SHALL equal `true`

#### Scenario: parseRequestScope treats malformed JSON as empty scope

- **WHEN** the body is `"{not json"`
- **THEN** the result SHALL match the empty-scope shape without throwing

#### Scenario: json sets content-type and CORS headers

- **WHEN** `json({ ok: 1 }, 423)` is called
- **THEN** the response SHALL have `status = 423`, header `Content-Type: application/json`, and the `Access-Control-Allow-*` headers from `corsHeaders`

#### Scenario: getSupabase throws when env vars missing

- **WHEN** `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` is not set
- **THEN** `getSupabase()` SHALL throw an Error whose message names the missing variable

### Requirement: pickup unit tests

The system SHALL provide `pickup.test.ts` covering `loadDispositions`, `loadConfig`, and every branch of `selectAndExpire`'s retry-timing and 90-day filter.

#### Scenario: loadDispositions returns a map keyed by error_code

- **WHEN** the seeded `gads_error_dispositions` table contains three rows with distinct error_codes
- **THEN** `loadDispositions(sb)` SHALL resolve to a `Map` of size 3 keyed by `error_code`

#### Scenario: loadDispositions throws on Supabase error

- **WHEN** the helper is configured to return `{ error: { message: "boom" } }` for the select
- **THEN** `loadDispositions` SHALL throw `Error("Failed to load dispositions: boom")`

#### Scenario: loadConfig returns a map keyed by conversion_type

- **WHEN** the seeded `gads_conversion_config` table contains rows for two conversion types
- **THEN** `loadConfig(sb)` SHALL resolve to a `Map` of size 2 keyed by `conversion_type`

#### Scenario: selectAndExpire includes queued rows unconditionally

- **WHEN** a queued row's `conversion_datetime` is within the 90-day window
- **THEN** it SHALL be returned

#### Scenario: selectAndExpire honors retry timing for retrying rows

- **WHEN** a retrying row's `last_attempt_at + retry_after_seconds <= now()`
- **THEN** it SHALL be returned

#### Scenario: selectAndExpire excludes retrying rows still in cooldown

- **WHEN** a retrying row's `last_attempt_at + retry_after_seconds > now()`
- **THEN** it SHALL NOT be returned

#### Scenario: selectAndExpire excludes retrying rows over max_attempts

- **WHEN** a retrying row's `attempt_count >= disposition.max_attempts`
- **THEN** it SHALL NOT be returned regardless of timing

#### Scenario: selectAndExpire treats null max_attempts as unlimited

- **WHEN** the disposition row has `max_attempts = null`
- **THEN** `attempt_count` SHALL NOT cause the row to be excluded

#### Scenario: selectAndExpire expires rows outside the 90-day window

- **WHEN** queued or retrying rows have `conversion_datetime < now() - 90 days`
- **THEN** `calls` SHALL contain an `update` to `gads_conversion_uploads` setting `lifecycle = 'expired'`, `status = 'expired'`, `error_code = null`, `error_namespace = null`, `error_detail = { reason: "Outside Google Ads 90-day conversion window" }`
- **THEN** those rows SHALL NOT be returned in the candidate set

#### Scenario: selectAndExpire applies scope filters

- **WHEN** the scope has `estimateIds = ["a"]`
- **THEN** the candidate query SHALL include an `.in("estimate_id", ["a"])` filter
- **WHEN** the scope has `conversionTypes = ["x"]`
- **THEN** the candidate query SHALL include an `.in("conversion_type", ["x"])` filter

### Requirement: payload-builder unit tests

The system SHALL provide `payload-builder.test.ts` covering `classifyRows` and `buildPayloads`.

#### Scenario: classifyRows skips rows whose conversion_type is missing from config

- **WHEN** a candidate row's `conversion_type` has no entry in the config map
- **THEN** the row SHALL appear in `skippedRows`, not `uploadable`

#### Scenario: classifyRows skips disabled types

- **WHEN** a config entry has `enabled = false`
- **THEN** matching rows SHALL appear in `skippedRows`

#### Scenario: classifyRows skips dry_run types

- **WHEN** a config entry has `dry_run = true`
- **THEN** matching rows SHALL appear in `skippedRows`

#### Scenario: classifyRows skips rows whose config has no conversion_action_id

- **WHEN** a config entry has `conversion_action_id = null`
- **THEN** matching rows SHALL appear in `skippedRows`

#### Scenario: classifyRows resolves conversion_action resource name

- **WHEN** an enabled config entry has a non-null `conversion_action_id`
- **THEN** the uploadable row's `conversionAction` SHALL equal `customers/${cfg.customerId}/conversionActions/${conversion_action_id}`

#### Scenario: buildPayloads emits GCLID-only payload

- **WHEN** an uploadable row has a GCLID and no customer email or phone
- **THEN** the resulting `conv.gclid` SHALL equal the row's GCLID and `conv.userIdentifiers` SHALL be undefined

#### Scenario: buildPayloads emits enhanced-conversion identifiers when present

- **WHEN** an uploadable row has a customer email and a customer phone
- **THEN** `conv.userIdentifiers` SHALL contain two entries (one `hashedEmail`, one `hashedPhoneNumber`)
- **THEN** `conv.consent` SHALL equal `{ adUserData: "GRANTED", adPersonalization: "GRANTED" }`

#### Scenario: buildPayloads sets value and currency only when conversion_value > 0

- **WHEN** a row has `conversion_value = 0` or null
- **THEN** `conv.conversionValue` SHALL be undefined and `conv.currencyCode` SHALL be undefined
- **WHEN** a row has `conversion_value = 250` and no `conversion_currency`
- **THEN** `conv.conversionValue` SHALL equal 250 and `conv.currencyCode` SHALL equal `"USD"`

#### Scenario: buildPayloads routes no-identifier rows to noIdRows

- **WHEN** a row has no GCLID and no customer email or phone
- **THEN** it SHALL appear in `noIdRows`, not `toUpload`

### Requirement: hashing unit tests

The system SHALL provide `hashing.test.ts` with pinned SHA-256 vectors covering email normalization, gmail special-case rules, phone E.164 normalization, and rejection of invalid inputs.

#### Scenario: hashEmail lowercases and trims

- **WHEN** the input is `"  Test@Example.com  "`
- **THEN** the output SHALL equal the SHA-256 hex of `"test@example.com"`

#### Scenario: hashEmail strips gmail dots

- **WHEN** the input is `"john.doe@gmail.com"`
- **THEN** the output SHALL equal the SHA-256 hex of `"johndoe@gmail.com"`

#### Scenario: hashEmail strips gmail plus-address

- **WHEN** the input is `"john.doe+spam@gmail.com"`
- **THEN** the output SHALL equal the SHA-256 hex of `"johndoe@gmail.com"`

#### Scenario: hashEmail applies gmail rules to googlemail.com

- **WHEN** the input is `"john.doe+x@googlemail.com"`
- **THEN** the output SHALL equal the SHA-256 hex of `"johndoe@googlemail.com"`

#### Scenario: hashEmail does NOT strip dots on other domains

- **WHEN** the input is `"john.doe@example.com"`
- **THEN** the output SHALL equal the SHA-256 hex of `"john.doe@example.com"` (dot preserved)

#### Scenario: hashEmail returns null for inputs without @

- **WHEN** the input is `"plain-no-at"`
- **THEN** the function SHALL resolve to `null`

#### Scenario: hashEmail returns null for empty input

- **WHEN** the input is `""` or `"   "`
- **THEN** the function SHALL resolve to `null`

#### Scenario: hashPhone normalizes 10-digit US to E.164

- **WHEN** the input is `"(415) 555-2671"`
- **THEN** the output SHALL equal the SHA-256 hex of `"+14155552671"`

#### Scenario: hashPhone normalizes 11-digit leading-1 to E.164

- **WHEN** the input is `"1-415-555-2671"`
- **THEN** the output SHALL equal the SHA-256 hex of `"+14155552671"`

#### Scenario: hashPhone handles 11-plus-digit international

- **WHEN** the input is `"+44 20 7946 0958"`
- **THEN** the output SHALL equal the SHA-256 hex of `"+442079460958"`

#### Scenario: hashPhone returns null for fewer than 10 digits

- **WHEN** the input is `"555-2671"` (7 digits)
- **THEN** the function SHALL resolve to `null`

#### Scenario: formatConversionDateTime emits Google's expected format

- **WHEN** the input is `"2026-05-15T12:34:56Z"`
- **THEN** the output SHALL equal `"2026-05-15 12:34:56+00:00"`

#### Scenario: formatConversionDateTime pads single-digit fields

- **WHEN** the input is `"2026-01-02T03:04:05Z"`
- **THEN** the output SHALL equal `"2026-01-02 03:04:05+00:00"`

### Requirement: batches unit tests

The system SHALL provide `batches.test.ts` covering `createBatch` and `markSending`.

#### Scenario: createBatch records single-type batch

- **WHEN** every prepared row in `toUpload` has `conversion_type = "estimate_completed"`
- **THEN** the insert payload SHALL set `row_count = toUpload.length` and `conversion_type = "estimate_completed"`

#### Scenario: createBatch records mixed-type batch as null

- **WHEN** prepared rows include more than one distinct `conversion_type`
- **THEN** the insert payload SHALL set `conversion_type = null`

#### Scenario: createBatch returns the new batch id

- **WHEN** the seeded insert resolves with `{ id: "abc-123" }`
- **THEN** `createBatch` SHALL resolve to `"abc-123"`

#### Scenario: createBatch throws on insert failure

- **WHEN** the seeded insert returns `{ data: null, error: { message: "constraint violated" } }`
- **THEN** `createBatch` SHALL throw `Error("Failed to insert batch row: constraint violated")`

#### Scenario: markSending updates rows in bulk

- **WHEN** `markSending(sb, [10, 11, 12], "batch-uuid")` is invoked
- **THEN** `calls` SHALL contain one `update` against `gads_conversion_uploads` with filter `{ id IN [10,11,12] }` and payload `{ lifecycle: "sending", status: "pending", batch_id: "batch-uuid" }`

### Requirement: ads-api unit tests

The system SHALL provide `ads-api.test.ts` covering both branches of `callGoogleAds`: the `mockResponse` short-circuit and the real-fetch path.

#### Scenario: mockResponse short-circuits fetch

- **WHEN** `callGoogleAds(toUpload, cfg, token, mockResponse)` is called with a non-undefined `mockResponse`
- **THEN** the function SHALL NOT invoke `globalThis.fetch`
- **THEN** the returned `data` SHALL equal `mockResponse`
- **THEN** `res.ok` SHALL be `true` and `networkError` SHALL be `null`

#### Scenario: real fetch builds the correct URL

- **WHEN** `mockResponse` is undefined and `cfg.customerId = "1234567890"`
- **THEN** the stubbed `fetch` SHALL receive URL `https://googleads.googleapis.com/v23/customers/1234567890:uploadClickConversions`

#### Scenario: real fetch serializes conversions and partialFailure flag

- **WHEN** `toUpload` has two prepared conversions
- **THEN** the fetch body SHALL be JSON with shape `{ conversions: [<conv1>, <conv2>], partialFailure: true }`

#### Scenario: real fetch parses 2xx response body

- **WHEN** the stubbed fetch returns `Response(JSON.stringify({ jobId: "x" }), { status: 200 })`
- **THEN** `data` SHALL equal `{ jobId: "x" }`

#### Scenario: real fetch leaves data null on non-2xx

- **WHEN** the stubbed fetch returns a 500
- **THEN** `data` SHALL be `null` and `res.status` SHALL equal `500`

#### Scenario: real fetch captures network error

- **WHEN** the stubbed fetch throws `Error("ECONNRESET")`
- **THEN** `networkError` SHALL be the thrown error
- **THEN** `res.status` SHALL be `599` (sentinel; WHATWG forbids `0`)

### Requirement: error-parsing unit tests

The system SHALL provide `error-parsing.test.ts` covering `extractErrorCode` discrimination and every documented branch of `parsePartialFailure`. These tests SHALL stand alone from `outcomes.test.ts` so a regression in parsing surfaces against the parser, not against an outcome handler.

#### Scenario: extractErrorCode returns null for unknown namespaces

- **WHEN** the input is `{ unknownNamespace: "FOO" }`
- **THEN** `extractErrorCode` SHALL return `null`

#### Scenario: extractErrorCode finds the first known namespace

- **WHEN** the input contains one of the six known namespaces with a string value
- **THEN** `extractErrorCode` SHALL return `{ namespace, name }` for that field

#### Scenario: parsePartialFailure returns empty maps when no partialFailureError

- **WHEN** the response has no `partialFailureError` field
- **THEN** `perRow.size` SHALL be `0` and `batchLevel` SHALL be `null`

#### Scenario: parsePartialFailure attributes per-row errors by index

- **WHEN** an error detail has `location.fieldPathElements[0] = { fieldName: "conversions", index: 2 }`
- **THEN** `perRow.get(2)` SHALL be defined

#### Scenario: parsePartialFailure routes index-less errors to batchLevel

- **WHEN** an error detail has no `location` field or empty `fieldPathElements`
- **THEN** the error SHALL appear as `batchLevel`, not in `perRow`

#### Scenario: parsePartialFailure ignores out-of-range indices

- **WHEN** an error has `index: 99` and `conversionsCount = 3`
- **THEN** that error SHALL appear in neither `perRow` nor `batchLevel`

#### Scenario: parsePartialFailure keeps only the first batch-level error

- **WHEN** two index-less errors are present
- **THEN** `batchLevel` SHALL hold the first; the second SHALL be discarded

### Requirement: disposition unit tests

The system SHALL provide `disposition.test.ts` covering `lifecycleFromDisposition` and the `LIFECYCLE_TO_STATUS` map.

#### Scenario: lifecycleFromDisposition maps each disposition

- **WHEN** the input is `"retry"`
- **THEN** the output SHALL be `"retrying"`
- **WHEN** the input is `"drop"`
- **THEN** the output SHALL be `"failed"`
- **WHEN** the input is `"deliberate"`
- **THEN** the output SHALL be `"excluded"`
- **WHEN** the input is `"fix-config"`, `"fix-data"`, `"fix-triage"`, or `null`
- **THEN** the output SHALL be `"needs-attention"`

#### Scenario: LIFECYCLE_TO_STATUS map matches the parallel-write spec

- **WHEN** the test enumerates every lifecycle value
- **THEN** the mapping SHALL match the table in the `conversion-upload` spec (queued/sending/retrying→pending, sent→uploaded, needs-attention/failed→failed, excluded→skipped, expired→expired)

### Requirement: Orchestrator end-to-end test

The system SHALL provide `index.test.ts` that exercises `handlePost(req, sbOverride)` through every routing branch using a fake Supabase client and the `_mock_response` request-body hook, without invoking real HTTP or env-backed Supabase.

#### Scenario: Paused pipeline returns 423 and makes no further calls

- **WHEN** `gads_pipeline_state` is seeded with `paused = true`
- **THEN** the response SHALL be `status 423` with `paused: true` in the body
- **THEN** no `update` SHALL be recorded against `gads_conversion_uploads` or `gads_conversion_upload_batches`

#### Scenario: Empty candidate set returns idempotent response

- **WHEN** no eligible candidates exist
- **THEN** the response SHALL be `status 200` with body `{ uploaded: 0, skipped: 0, errored: 0, message: "No eligible conversions" }`
- **THEN** no batch row SHALL be inserted

#### Scenario: All candidates skipped by config returns skipped count

- **WHEN** eligible candidates exist but every matching config row has `enabled = false`
- **THEN** the response SHALL be `status 200` with `uploaded = 0` and `skipped = N` matching the candidate count
- **THEN** no batch row SHALL be inserted

#### Scenario: All candidates lack identifiers → excluded path

- **WHEN** uploadable rows have no GCLID and no customer email/phone
- **THEN** each such row SHALL receive an `update` setting `lifecycle = 'excluded'`, `status = 'skipped'`
- **THEN** no batch row SHALL be inserted

#### Scenario: Full success routes through to applyPerRowOutcomes

- **WHEN** `_mock_response` is `{ jobId: "job-x" }` (no `partialFailureError`)
- **THEN** the response SHALL be `status 200` with `uploaded = N`, `batch_id` set, `job_id = "job-x"`
- **THEN** every row SHALL receive an `update` setting `lifecycle = 'sent'`, `status = 'uploaded'`, `uploaded_at != null`, `error_code = null`

#### Scenario: Partial failure routes per disposition

- **WHEN** `_mock_response` contains `partialFailureError.details` with one retry, one fix-config, one drop per row index
- **THEN** the responding row updates SHALL match the disposition mapping (`retry → retrying`, `fix-config → needs-attention`, `drop → failed`)
- **THEN** the batch row update SHALL record `accepted_count` and `rejected_count` matching the counts

#### Scenario: Batch-level fix-config trips pipeline pause

- **WHEN** `_mock_response` contains a single index-less request-level error whose `error_code` maps to `fix-config`
- **THEN** the response SHALL be `status 502` with `batch_failed: true, paused: true`
- **THEN** `gads_pipeline_state` SHALL receive an `update` with `paused = true`
- **THEN** every constituent row SHALL receive an `update` with `lifecycle = 'queued'`, `status = 'pending'`

#### Scenario: Batch-level retry does not trip pause

- **WHEN** the request-level error_code maps to `retry`
- **THEN** the response SHALL be `status 502` with `paused: false`
- **THEN** no `update` SHALL be recorded against `gads_pipeline_state`

#### Scenario: Orchestrator never calls real HTTP

- **WHEN** any orchestrator test runs
- **THEN** `globalThis.fetch` SHALL NOT be invoked at any point (verified by a fetch stub that throws on call when no `_mock_response` is set)

### Requirement: Single test command

The system SHALL expose a single command that runs every `*.test.ts` under `supabase/functions/google-ads-conversion-upload/`. The command MAY live in `horizon-dashboard/package.json` as an npm script or in a `deno.json` at the function root; the choice is implementation-time per design.md.

#### Scenario: One-command run

- **WHEN** an engineer runs the documented command
- **THEN** every test file in the function directory SHALL be discovered and executed
- **THEN** the exit code SHALL be non-zero if any test fails

### Requirement: No production behavior change

The change SHALL NOT alter the behavior of the edge function in production. The only permitted production-side modification is adding the optional `sbOverride` parameter to `handlePost` per design.md [D5], which defaults to `getSupabase()` and produces identical behavior when omitted.

#### Scenario: Default handlePost call uses production Supabase

- **WHEN** `handlePost(req)` is called without a second argument
- **THEN** the function SHALL behave identically to today (calls `getSupabase()` internally)

#### Scenario: No other module signatures change

- **WHEN** the diff for this change is reviewed against `main`
- **THEN** the only production-source diff SHALL be the optional parameter on `handlePost` and any necessary `export` keyword additions
