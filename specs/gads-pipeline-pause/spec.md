# gads-pipeline-pause

## Purpose

Provide a global pause switch for the conversion-upload pipeline so that batch-level `fix-config` failures halt all API work until an operator resolves the configuration and resumes, with the pause state surfaced and controllable from the Workbench.

## Requirements

### Requirement: Pipeline state singleton

The system SHALL provide a singleton table `gads_pipeline_state` with exactly one row (enforced by `CHECK (id = 1)` and a primary key on `id`). Columns:

- `id integer PRIMARY KEY CHECK (id = 1)`
- `paused boolean NOT NULL DEFAULT false`
- `paused_reason text` (NULL when not paused)
- `paused_error_code text` (NULL when not paused; the batch-level error code that caused the pause)
- `paused_batch_id uuid REFERENCES gads_conversion_upload_batches(id)` (NULL when not paused)
- `paused_at timestamptz` (NULL when not paused)
- `resumed_at timestamptz`
- `resumed_by uuid` (nullable; references `auth.users.id`)

The seed migration SHALL insert the singleton row with `id = 1, paused = false`.

#### Scenario: Singleton enforcement

- **WHEN** an insert attempts to add a second row to `gads_pipeline_state` (e.g., `id = 2`)
- **THEN** the database SHALL reject the insert with a CHECK constraint violation

### Requirement: Edge function checks pause flag before any API work

The edge function `google-ads-conversion-upload` SHALL read `gads_pipeline_state.paused` as the first action of its cron entrypoint. If `paused = true`, the function SHALL log the pause state and return `{ paused: true, reason: <paused_reason> }` without making any Google Ads API calls and without modifying any rows.

#### Scenario: Cron tick while paused

- **WHEN** the cron triggers the edge function and `gads_pipeline_state.paused = true`
- **THEN** the function SHALL NOT call Google Ads
- **THEN** the function SHALL NOT modify any row in `gads_conversion_uploads` or `gads_conversion_upload_batches`
- **THEN** the function SHALL return a response indicating it skipped due to pause

#### Scenario: Manual invocation while paused

- **WHEN** a manual invocation hits the edge function (e.g., from the Workbench bulk-upload UI) and the pipeline is paused
- **THEN** the function SHALL respond with HTTP 423 (Locked) and a body indicating the pause reason

### Requirement: Batch-level fix-config errors trip the pause

When a Google Ads API call returns a batch-level error (HTTP non-2xx or a request-level error code that prevents any rows from being accepted), the edge function SHALL look up the disposition for the structured error code. If the disposition is `fix-config`, the function SHALL set `gads_pipeline_state.paused = true` along with the related metadata.

#### Scenario: Batch-level fix-config pauses pipeline

- **WHEN** the API returns a batch-level error whose `error_code` has `disposition = 'fix-config'` in `gads_error_dispositions`
- **THEN** the function SHALL write the failed batch row to `gads_conversion_upload_batches`
- **THEN** the function SHALL UPDATE `gads_pipeline_state` setting `paused = true`, `paused_reason = <human-readable message>`, `paused_error_code = <error_code>`, `paused_batch_id = <new batch id>`, `paused_at = now()`
- **THEN** the function SHALL leave rows that were in the failed batch with `lifecycle = 'queued'` (not `'needs-attention'`)

#### Scenario: Batch-level retry-disposition does not pause

- **WHEN** the API returns a batch-level error whose `error_code` has `disposition = 'retry'` (e.g., transient `INTERNAL_ERROR` at request level)
- **THEN** the function SHALL write the failed batch row to `gads_conversion_upload_batches`
- **THEN** `gads_pipeline_state.paused` SHALL remain `false`
- **THEN** rows from the failed batch SHALL be eligible for the next cron pickup (respecting per-row `retry_after_seconds`)

### Requirement: Pause banner in the Workbench

The Workbench shell SHALL render a sticky banner on every Conversions tab when `gads_pipeline_state.paused = true`. The banner SHALL show the pause time, the `paused_error_code`, the `paused_reason`, and offer three actions: "View batch" (links to the Batches panel filtered/scrolled to `paused_batch_id`), "Open Google Ads" (external link), and "Resume uploads".

#### Scenario: Banner visibility tracks pause state

- **WHEN** `gads_pipeline_state.paused = true`
- **THEN** the banner SHALL render at the top of every Conversions route (Pipeline, Needs Attention, Batches, Dispositions admin)

- **WHEN** `gads_pipeline_state.paused = false`
- **THEN** no banner SHALL render

#### Scenario: Pause state refresh

- **WHEN** the dashboard is mounted or the user focuses a Conversions tab
- **THEN** the dashboard SHALL refetch `gads_pipeline_state` within 30 seconds of any event that could have changed it (background poll, tab focus, post-resume)

### Requirement: Resume action clears the pause

The "Resume uploads" button SHALL invoke a mutation that UPDATEs `gads_pipeline_state` setting `paused = false`, `resumed_at = now()`, `resumed_by = auth.uid()`. Any logged-in user MAY resume.

#### Scenario: Resume returns pipeline to active

- **WHEN** a logged-in user clicks "Resume uploads" and confirms the dialog
- **THEN** `gads_pipeline_state.paused` SHALL be set to `false`
- **THEN** `resumed_at` SHALL be set to `now()` and `resumed_by` SHALL be set to the user's ID
- **THEN** `paused_reason`, `paused_error_code`, `paused_batch_id`, and `paused_at` SHALL remain as historical record (not nulled)
- **THEN** the next cron tick SHALL proceed normally
