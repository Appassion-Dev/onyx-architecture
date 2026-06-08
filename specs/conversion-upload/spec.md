# conversion-upload

## Purpose

Define the edge function that uploads pending conversions to Google Ads, persists per-batch request/response audit data, routes per-row failures by disposition, and maintains the lifecycle column in parallel with the legacy status column during the transition.

## Requirements

### Requirement: Upload pending conversions to Google Ads

The system SHALL provide an edge function that reads rows from `gads_conversion_uploads` with `lifecycle = 'queued'` (or `lifecycle = 'retrying'` where `last_attempt_at + (joined retry_after_seconds) <= now()` and `attempt_count < (joined max_attempts OR ∞)`) and `conversion_datetime` within the last 90 days, checks `gads_conversion_config` for each row's `conversion_type` (skipping types where `enabled = false` or `dry_run = true`), resolves the `conversion_action` resource name, fetches customer contact data (email and mobile_number) via `estimates.customer_id` -> `customers` for enhanced conversions using `.limit()` sized to the batch to bypass PostgREST's default 1000-row cap, builds Google Ads API conversion payloads, and uploads them via the `uploadClickConversions` endpoint in a single batched API call. The function SHALL check `gads_pipeline_state.paused` as its very first action and SHALL exit without doing any work if `paused = true`. On each attempt (success or failure), the function increments `attempt_count` (also writing legacy `upload_attempts` for backward compatibility). Rows with `conversion_datetime` older than 90 days SHALL be bulk-updated to `lifecycle = 'expired'` (and legacy `status = 'expired'`) in the same run. Every API call SHALL write exactly one row to `gads_conversion_upload_batches` and SHALL set `batch_id` on every row included in that call. Whenever the function transitions a row away from a state in which a structured `error_code` is meaningful (specifically: into `lifecycle = 'queued'`, `'excluded'`, `'sent'`, or `'expired'`), the function SHALL null `error_code`, `error_namespace`, and `error_detail` (except where a new `error_detail` value is explicitly written by the scenario), so that the `vw_gads_conversion_uploads` view never projects a `disposition` derived from a stale code.

#### Scenario: Pickup query honors retry timing and pause

- **WHEN** the cron triggers the function and the pipeline is not paused
- **THEN** the function SHALL select rows where either `lifecycle = 'queued'` OR (`lifecycle = 'retrying'` AND `last_attempt_at + (disposition.retry_after_seconds || ' seconds')::interval <= now()` AND `attempt_count < COALESCE(disposition.max_attempts, 2147483647)`)
- **THEN** the function SHALL NOT select rows whose `lifecycle` is `'needs-attention'`, `'failed'`, `'excluded'`, `'expired'`, `'sent'`, or `'sending'`

#### Scenario: Pending row with GCLID is uploaded

- **WHEN** a queued row has `gclid` populated and a matching enabled `conversion_type` in `gads_conversion_config` with a non-null `conversion_action_id`
- **THEN** the function resolves the `conversion_action` resource name from config, builds an `AdsConversion` payload with the GCLID, conversion action, datetime, value (if present), and currency, and includes it in the batch upload
- **THEN** if the estimate's customer has email or mobile_number, they are hashed and included as `userIdentifiers` alongside the GCLID
- **THEN** the row's `lifecycle` is set to `'sending'` for the duration of the API call (and legacy `status` stays `'pending'` per the parallel-write mapping)

#### Scenario: Pending row without GCLID but with hashed identifiers

- **WHEN** a queued row has `gclid = NULL` but the estimate's customer has email or mobile_number
- **THEN** the function builds the payload with `userIdentifiers` (SHA-256 hashed email and/or phone) and consent fields for enhanced conversions

#### Scenario: Pending row with neither GCLID nor contact data

- **WHEN** a queued row has no GCLID and the estimate's customer has no email or mobile_number
- **THEN** the row's `lifecycle` is updated to `'excluded'` (and legacy `status = 'skipped'`) with `error_detail = { "reason": "no GCLID and no enhanced-conversion identifiers" }`
- **THEN** the row's `error_code` and `error_namespace` SHALL be set to NULL in the same UPDATE, even if they were populated from a prior retrying-state attempt

#### Scenario: Pending row outside 90-day window is expired

- **WHEN** a queued row has `conversion_datetime` older than 90 days from the current time
- **THEN** the row's `lifecycle` is updated to `'expired'` (and legacy `status = 'expired'`) with `error_detail = { "reason": "Outside Google Ads 90-day conversion window" }`
- **THEN** the row's `error_code` and `error_namespace` SHALL be set to NULL in the same UPDATE
- **THEN** the row is NOT included in the upload batch

#### Scenario: Successful upload updates audit state

- **WHEN** the Google Ads API accepts the conversion
- **THEN** the row's `lifecycle` is updated to `'sent'` (and legacy `status = 'uploaded'`), `uploaded_at` is set to now, `attempt_count` (and legacy `upload_attempts`) is incremented, `error_code` / `error_namespace` / `error_detail` are cleared (set to NULL), `batch_id` is set to the new batch row's id, and the resolved `conversion_action` resource name is written to the row as a historical record

#### Scenario: Partial failure captures structured error and routes by disposition

- **WHEN** the Google Ads API returns a partial-failure detail for a specific row
- **THEN** the function SHALL parse the detail to extract the namespaced `error_code` (e.g., `conversionUploadError.EXPIRED_EVENT`), the `error_namespace`, and the full error object as `error_detail`
- **THEN** the function SHALL look up the row in `gads_error_dispositions` and derive `lifecycle` per the disposition: `retry` → `'retrying'`; `fix-config` / `fix-data` / `fix-triage` → `'needs-attention'`; `drop` → `'failed'`; `deliberate` → `'excluded'`
- **THEN** the function SHALL write `error_code`, `error_namespace`, `error_detail`, `last_attempt_at = now()`, `batch_id`, and increment `attempt_count` (and legacy `upload_attempts`)
- **THEN** the function SHALL update legacy `status` per the lifecycle→status mapping

#### Scenario: Unknown error_code defaults to fix-triage

- **WHEN** a partial-failure detail has an `error_code` for which no row exists in `gads_error_dispositions`
- **THEN** the function SHALL set the row's `lifecycle` to `'needs-attention'` (the `fix-triage` default behavior)
- **THEN** the function SHALL NOT retry this row on the next cron tick

#### Scenario: Batch-level failure writes batch row and may pause

- **WHEN** the Google Ads API call returns a non-2xx HTTP status or a request-level error code preventing any rows from being accepted
- **THEN** the function SHALL write one row to `gads_conversion_upload_batches` with `accepted_count = 0`, `rejected_count = 0`, and populated `request_error_code` / `request_error_message`
- **THEN** the rows included in that failed batch SHALL be updated to `lifecycle = 'queued'` (status `'pending'` per the parallel-write mapping), `last_attempt_at = now()`, `batch_id = <new batch id>`, and incremented `attempt_count` / `upload_attempts`
- **THEN** the same UPDATE SHALL also set `error_code = NULL`, `error_namespace = NULL`, `error_detail = NULL` for the constituent rows (the row did not individually fail; the batch did, and the batch row carries the cause)
- **THEN** if the disposition for the batch-level `error_code` is `fix-config`, the function SHALL UPDATE `gads_pipeline_state` setting `paused = true` per the `gads-pipeline-pause` spec

#### Scenario: Upload function is idempotent when nothing eligible

- **WHEN** the upload function runs and finds no eligible rows within the 90-day window (or all eligible rows belong to disabled/dry_run types) and the pipeline is not paused
- **THEN** it returns immediately with `{ uploaded: 0, skipped: 0 }` and makes no API calls
- **THEN** no row SHALL be written to `gads_conversion_upload_batches`

### Requirement: Persist raw request and response per batch

The upload function SHALL persist the exact JSON request body sent to the Google Ads `uploadClickConversions` endpoint and the parsed JSON response received from Google onto the `gads_conversion_upload_batches` row for the batch. Both values SHALL be written exactly once per batch invocation, as part of the same write that finalizes the batch row's `http_status` / `accepted_count` / `rejected_count` / `request_error_*` fields.

The table `gads_conversion_upload_batches` SHALL include two `jsonb` columns, `request_body` and `response_body`, both nullable. Pre-existing rows (predating this change) MAY remain `NULL`; no backfill is required.

The `request_body` SHALL be the object `{ "conversions": [...], "partialFailure": true }` whose `JSON.stringify`-ed form was POSTed to Google, with each `conversions[i]` entry exactly as built by the payload-builder (including hashed `userIdentifiers`, `gclid`, `conversionAction`, `conversionDateTime`, `orderId`, and optional `conversionValue`/`currencyCode`/`consent` fields).

#### Scenario: Successful batch records both bodies

- **WHEN** the function POSTs a batch to `uploadClickConversions` and Google returns a 2xx response
- **THEN** the batch row's `request_body` SHALL equal the JSON object that was POSTed and `response_body` SHALL equal the parsed JSON Google returned, both written in the same update as `accepted_count`, `rejected_count`, `http_status`, and `job_id`

#### Scenario: Partial-failure batch records both bodies

- **WHEN** the function POSTs a batch and Google returns a 2xx response containing a `partialFailureError`
- **THEN** the batch row's `request_body` and `response_body` SHALL both be populated; `response_body` SHALL include the `partialFailureError` field exactly as Google returned it

#### Scenario: Non-2xx HTTP batch failure records request body

- **WHEN** the function POSTs a batch and Google returns a non-2xx HTTP status
- **THEN** the batch row's `request_body` SHALL be populated and `response_body` SHALL be `NULL` (the body is not assumed to be JSON); the existing `request_error_code` / `request_error_message` / `http_status` fields SHALL still be set per current behavior

#### Scenario: Network failure records request body and structured envelope

- **WHEN** the `fetch` call throws before a response is received (network, DNS, TLS, timeout)
- **THEN** the batch row's `request_body` SHALL be populated and `response_body` SHALL be a JSON object `{ "network_error": "<truncated error message>", "captured_at": "<ISO-8601 timestamp>" }` distinguishable from a real Google response by the presence of the `network_error` key

#### Scenario: Mock-response test path records both bodies

- **WHEN** the upload is invoked with `_mock_response` set (test hook in `UploadRequestBody`)
- **THEN** the batch row's `request_body` SHALL be populated with the body that would have been sent and `response_body` SHALL be populated with the mock response value; no HTTP call is made

#### Scenario: Capture failure does not corrupt batch accounting

- **WHEN** writing `request_body` or `response_body` to the batch row fails
- **THEN** the existing batch finalization behavior (per-row outcome updates, `accepted_count` / `rejected_count`, lifecycle transitions on `gads_conversion_uploads`) SHALL still complete; the batch row's other columns SHALL be written; the new columns MAY remain `NULL` for that batch and the function SHALL surface the error in its normal error-propagation path

### Requirement: Per-row error index bounds check

The partial-failure parser SHALL validate that every per-row error index from Google's response falls within `[0, conversionsCount)` where `conversionsCount` is the number of conversions in the request body. Indices outside that range SHALL be discarded (not recorded as per-row errors) and SHALL be logged at `console.warn` level with the error code and the out-of-range index. Discarded entries SHALL NOT be reclassified as batch-level errors.

#### Scenario: Per-row error with valid index is recorded

- **WHEN** Google's partial-failure response includes a per-row detail with `location.fieldPathElements[0].index = N` where `0 <= N < conversionsCount`
- **THEN** the parser SHALL record the error against row index `N`

#### Scenario: Per-row error with out-of-range index is discarded

- **WHEN** Google's partial-failure response includes a per-row detail with `location.fieldPathElements[0].index = N` where `N < 0` or `N >= conversionsCount`
- **THEN** the parser SHALL NOT add the entry to the per-row map
- **THEN** the parser SHALL emit a `console.warn` log line containing the error code and the out-of-range index
- **THEN** the parser SHALL NOT promote the entry to the `batchLevel` slot

#### Scenario: Out-of-range index does not affect other rows

- **WHEN** the response contains one out-of-range per-row error and one valid per-row error
- **THEN** the valid per-row error SHALL be recorded normally
- **THEN** the upload run SHALL proceed with per-row outcome processing using the valid entries only

### Requirement: Parallel writes preserve legacy status column

For one release cycle, the edge function SHALL write the legacy `gads_conversion_uploads.status` column in parallel with the new `lifecycle` column. The mapping SHALL be:

- `lifecycle = 'queued'` → `status = 'pending'`
- `lifecycle = 'sending'` → `status = 'pending'`
- `lifecycle = 'sent'` → `status = 'uploaded'`
- `lifecycle = 'retrying'` → `status = 'pending'`
- `lifecycle = 'needs-attention'` → `status = 'failed'`
- `lifecycle = 'failed'` → `status = 'failed'`
- `lifecycle = 'excluded'` → `status = 'skipped'`
- `lifecycle = 'expired'` → `status = 'expired'`

A database CHECK constraint SHALL enforce that any row with a non-NULL `lifecycle` has a `status` matching this mapping.

#### Scenario: Every lifecycle write maps to a legacy status

- **WHEN** the edge function writes any `lifecycle` value to a row
- **THEN** the same UPDATE SHALL also write the mapped legacy `status` value
- **THEN** the CHECK constraint SHALL accept the write

#### Scenario: Out-of-spec write rejected

- **WHEN** any process attempts to UPDATE a row with `lifecycle = 'sent'` and `status = 'pending'` simultaneously (out-of-spec)
- **THEN** the database SHALL reject the write with a CHECK constraint violation

#### Scenario: Historical rows with NULL lifecycle

- **WHEN** an existing row has not yet been touched by the new edge function and has `lifecycle IS NULL`
- **THEN** the CHECK constraint SHALL permit the row to exist (the mapping constraint applies only to rows with a non-NULL `lifecycle`)

### Requirement: Backfill lifecycle for existing rows

The migration introducing `lifecycle` SHALL backfill every existing row in `gads_conversion_uploads` from its current `status`:

- `status = 'pending'` AND `upload_attempts = 0` → `lifecycle = 'queued'`
- `status = 'pending'` AND `upload_attempts > 0` → `lifecycle = 'retrying'`
- `status = 'uploaded'` → `lifecycle = 'sent'`
- `status = 'skipped'` → `lifecycle = 'excluded'`
- `status = 'failed'` → `lifecycle = 'failed'`
- `status = 'expired'` → `lifecycle = 'expired'`

Existing rows SHALL NOT have their `error_code`, `error_namespace`, `error_detail`, or `batch_id` populated by the backfill (the original structured code is unrecoverable from the truncated `error_message`).

#### Scenario: Backfill produces consistent state

- **WHEN** the migration runs against the production table
- **THEN** every row SHALL have a non-NULL `lifecycle` value after the migration completes
- **THEN** every row's `(lifecycle, status)` pair SHALL satisfy the CHECK constraint
- **THEN** historical rows' `error_code` SHALL be NULL

### Requirement: Conversion dateTime is formatted in the configured account timezone

The edge function SHALL format each conversion's `conversionDateTime` field by re-projecting the stored UTC instant into the configured account timezone, emitting the Google Ads format `YYYY-MM-DD HH:MM:SS±HH:MM`. The timezone SHALL be sourced from the `GOOGLE_ADS_ACCOUNT_TIMEZONE` environment variable, defaulting to `America/New_York` when unset. The rendering SHALL be instant-preserving and DST-aware: the wall-clock components and the offset together SHALL denote the same absolute instant as the stored value, with the offset resolved for that specific instant (e.g. `-04:00` during US Eastern daylight time, `-05:00` during standard time). The function SHALL NOT relabel the offset while leaving the UTC wall-clock components unchanged.

#### Scenario: Default timezone renders a summer instant in Eastern daylight time
- **WHEN** the account timezone is unset (defaulting to `America/New_York`) and a row's `conversion_datetime` is `2026-05-15T12:00:00Z`
- **THEN** the `conversionDateTime` sent to Google SHALL be `2026-05-15 08:00:00-04:00`

#### Scenario: Default timezone renders a winter instant in Eastern standard time
- **WHEN** the account timezone defaults to `America/New_York` and a row's `conversion_datetime` is `2026-01-02T03:04:05Z`
- **THEN** the `conversionDateTime` sent to Google SHALL be `2026-01-01 22:04:05-05:00`

#### Scenario: Rendered value denotes the same instant as the stored UTC value
- **WHEN** a row's `conversion_datetime` is rendered in the account timezone
- **THEN** parsing the emitted string SHALL yield the same absolute instant as the stored UTC value, with only the wall-clock representation and offset differing

#### Scenario: Timezone is configurable via environment variable
- **WHEN** `GOOGLE_ADS_ACCOUNT_TIMEZONE` is set to `UTC` and a row's `conversion_datetime` is `2026-05-15T12:00:00Z`
- **THEN** the `conversionDateTime` sent to Google SHALL be `2026-05-15 12:00:00+00:00`

#### Scenario: Midnight in the account timezone renders as 00, not 24
- **WHEN** a row's instant falls exactly at midnight in the account timezone
- **THEN** the emitted hour component SHALL be `00:00:00` (not `24:00:00`)
