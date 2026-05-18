## ADDED Requirements

### Requirement: Batch tracking table

The system SHALL provide a table `gads_conversion_upload_batches` with these columns:

- `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
- `sent_at timestamptz NOT NULL DEFAULT now()`
- `job_id text` (server-assigned `jobId` from Google's response; NULL if the batch failed before a job was assigned)
- `http_status integer`
- `request_error_code text` (the structured error code namespaced per the catalog, if the batch itself failed)
- `request_error_message text` (Google's error message, untruncated)
- `row_count integer NOT NULL`
- `accepted_count integer NOT NULL DEFAULT 0`
- `rejected_count integer NOT NULL DEFAULT 0`
- `conversion_type text` (the `conversion_type` of the rows in this batch; NULL if mixed)

The table `gads_conversion_uploads` SHALL have a new nullable column `batch_id uuid` with a foreign key reference to `gads_conversion_upload_batches.id` (ON DELETE SET NULL).

#### Scenario: Every API call writes a batch row

- **WHEN** the edge function calls Google Ads `uploadClickConversions`
- **THEN** a single row SHALL be written to `gads_conversion_upload_batches` for that API call, regardless of whether the call succeeded, returned a partial failure, or failed entirely

#### Scenario: Per-row batch_id linkage

- **WHEN** a row in `gads_conversion_uploads` is included in an API call
- **THEN** its `batch_id` SHALL be updated to the `id` of the newly-written batch row in the same write that updates its `lifecycle`, `last_attempt_at`, and `attempt_count`

#### Scenario: Batch-level failure populates request_error fields

- **WHEN** the API call returns a non-2xx HTTP status or a request-level error code that prevents any rows from being processed
- **THEN** the batch row SHALL be written with `accepted_count = 0`, `rejected_count = 0`, and `request_error_code` / `request_error_message` populated

### Requirement: Batches panel in the Workbench

The system SHALL provide a Workbench page at `/conversions/batches` that lists rows from `gads_conversion_upload_batches` ordered by `sent_at` descending, paginated 50 per page. Each row SHALL display `sent_at` (in the user's timezone), `job_id` (abbreviated), `row_count`, `accepted_count`, `rejected_count`, and a status indicator.

#### Scenario: Status indicator semantics

- **WHEN** a batch row has `rejected_count = 0` and `request_error_code IS NULL`
- **THEN** the status indicator SHALL be a green check with label "Accepted"

- **WHEN** a batch row has `rejected_count > 0` and `request_error_code IS NULL`
- **THEN** the status indicator SHALL be an amber dot with label "Partial (N rejected)"

- **WHEN** a batch row has `request_error_code IS NOT NULL`
- **THEN** the status indicator SHALL be a red triangle with the abbreviated `request_error_code` as label, and a tooltip showing the full `request_error_message`

#### Scenario: Batch drill-down

- **WHEN** a user expands a batch row
- **THEN** the panel SHALL show the constituent rows from `vw_gads_conversion_uploads WHERE batch_id = <id>`
- **THEN** each constituent row SHALL display the row's `estimate_id`, `conversion_type`, `lifecycle`, and `error_code` (if any)

#### Scenario: Paused-batch tagging

- **WHEN** a batch row's `id` equals the current `gads_pipeline_state.paused_batch_id`
- **THEN** the batch row SHALL display a "Paused pipeline" tag in addition to its status indicator
