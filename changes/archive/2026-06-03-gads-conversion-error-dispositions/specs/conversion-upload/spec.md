## MODIFIED Requirements

### Requirement: Upload pending conversions to Google Ads

The system SHALL provide an edge function that reads rows from `gads_conversion_uploads` with `lifecycle = 'queued'` (or `lifecycle = 'retrying'` where `last_attempt_at + (joined retry_after_seconds) <= now()` and `attempt_count < (joined max_attempts OR ∞)`) and `conversion_datetime` within the last 90 days, checks `gads_conversion_config` for each row's `conversion_type` (skipping types where `enabled = false` or `dry_run = true`), resolves the `conversion_action` resource name, fetches customer contact data (email and mobile_number) via `estimates.customer_id` -> `customers` for enhanced conversions using `.limit()` sized to the batch to bypass PostgREST's default 1000-row cap, builds Google Ads API conversion payloads, and uploads them via the `uploadClickConversions` endpoint in a single batched API call. The function SHALL check `gads_pipeline_state.paused` as its very first action and SHALL exit without doing any work if `paused = true`. On each attempt (success or failure), the function increments `attempt_count` (also writing legacy `upload_attempts` for backward compatibility). Rows with `conversion_datetime` older than 90 days SHALL be bulk-updated to `lifecycle = 'expired'` (and legacy `status = 'expired'`) in the same run. Every API call SHALL write exactly one row to `gads_conversion_upload_batches` and SHALL set `batch_id` on every row included in that call.

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
- **THEN** the row's `lifecycle` is updated to `'excluded'` (and legacy `status = 'skipped'`) with an `error_detail` describing the missing inputs

#### Scenario: Pending row outside 90-day window is expired

- **WHEN** a queued row has `conversion_datetime` older than 90 days from the current time
- **THEN** the row's `lifecycle` is updated to `'expired'` (and legacy `status = 'expired'`) with `error_detail` "Outside Google Ads 90-day conversion window"
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
- **THEN** the rows included in that failed batch SHALL remain in `lifecycle = 'queued'` (their `attempt_count` SHALL still increment, and `last_attempt_at` SHALL be updated, and `batch_id` SHALL link to the failed batch)
- **THEN** if the disposition for the batch-level `error_code` is `fix-config`, the function SHALL UPDATE `gads_pipeline_state` setting `paused = true` per the `gads-pipeline-pause` spec

#### Scenario: Upload function is idempotent when nothing eligible

- **WHEN** the upload function runs and finds no eligible rows within the 90-day window (or all eligible rows belong to disabled/dry_run types) and the pipeline is not paused
- **THEN** it returns immediately with `{ uploaded: 0, skipped: 0 }` and makes no API calls
- **THEN** no row SHALL be written to `gads_conversion_upload_batches`

## ADDED Requirements

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
