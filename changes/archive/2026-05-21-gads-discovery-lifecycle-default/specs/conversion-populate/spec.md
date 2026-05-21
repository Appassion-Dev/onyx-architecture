## MODIFIED Requirements

### Requirement: Discovery SQL wrapper writes pending rows
The system SHALL provide a SQL function `discover_pending_conversions()` that invokes all three pending conversion query functions and writes their results as rows in `gads_conversion_uploads` with `status = 'pending'` and `lifecycle = 'queued'`. Both columns are written in the same INSERT to satisfy the `(lifecycle, status)` parallel-write CHECK constraint and to make every newly discovered row visible to the disposition-driven upload edge function (which selects `lifecycle IN ('queued', 'retrying')`). This function uses `INSERT ... ON CONFLICT (estimate_id, conversion_type) DO NOTHING` for idempotency. It does NOT look up `conversion_action_id` from `gads_conversion_config` — the `conversion_action` column is left NULL at discovery time (resolved at upload time). However, it DOES check the `enabled` flag in `gads_conversion_config` — conversion types with `enabled = false` are skipped entirely (no pending rows created). This function is called directly by `pg_cron` as a SQL statement — no edge function, no HTTP call.

#### Scenario: Discovery finds new booking lead
- **WHEN** `discover_pending_conversions()` runs and `get_pending_booking_lead_conversions()` returns an estimate
- **THEN** a row is inserted with `estimate_id` = HCP estimate ID, `conversion_type = 'booking_lead'`, `conversion_value = NULL`, `conversion_action = NULL`, `status = 'pending'`, and `lifecycle = 'queued'`

#### Scenario: Discovery finds new qualified lead
- **WHEN** `discover_pending_conversions()` runs and `get_pending_qualified_lead_conversions()` returns an estimate
- **THEN** a row is inserted with `estimate_id` = HCP estimate ID, `conversion_type = 'qualified_lead'`, the estimate total ÷ 100 as `conversion_value`, `conversion_action = NULL`, `status = 'pending'`, and `lifecycle = 'queued'`

#### Scenario: Discovery finds new converted lead
- **WHEN** `discover_pending_conversions()` runs and `get_pending_converted_lead_conversions()` returns a job
- **THEN** a row is inserted with `estimate_id = original_estimate_id`, `job_id = jobs.id`, `conversion_type = 'converted_lead'`, the job total ÷ 100 as `conversion_value`, `conversion_action = NULL`, `status = 'pending'`, and `lifecycle = 'queued'`

#### Scenario: Discovery is idempotent
- **WHEN** `discover_pending_conversions()` runs twice with no status changes between runs
- **THEN** no duplicate rows are created (INSERT ON CONFLICT DO NOTHING)

#### Scenario: Newly discovered row is visible to the uploader
- **WHEN** `discover_pending_conversions()` inserts a new row and the upload edge function runs immediately after
- **THEN** the upload edge function's pickup query (which filters `lifecycle IN ('queued', 'retrying')`) SHALL include the row in its candidate set

## ADDED Requirements

### Requirement: gads_conversion_uploads.lifecycle has a `'queued'` column DEFAULT
The `lifecycle` column on `gads_conversion_uploads` SHALL have a column-level `DEFAULT 'queued'` as a safety net for any inserter that omits `lifecycle` from its column list. This default does NOT replace the explicit projection in `discover_pending_conversions()` — both mechanisms coexist so the discovery functions remain self-documenting while still tolerating future inserters that forget the column.

#### Scenario: Insert omits lifecycle column
- **WHEN** any INSERT into `gads_conversion_uploads` does not include `lifecycle` in its column list
- **THEN** the row SHALL be created with `lifecycle = 'queued'`

#### Scenario: Insert sets lifecycle explicitly
- **WHEN** an INSERT into `gads_conversion_uploads` includes `lifecycle` in its column list with a non-NULL value
- **THEN** the explicit value SHALL be used and the default SHALL NOT override it

### Requirement: Backfill stranded NULL-lifecycle rows
Any rows in `gads_conversion_uploads` with `lifecycle = NULL` at migration time SHALL be backfilled to a non-NULL lifecycle value. Rows with `upload_attempts = 0` map to `'queued'`; rows with `upload_attempts > 0` map to `'retrying'`. The backfill SHALL be expressed as an idempotent `UPDATE … WHERE lifecycle IS NULL` so re-applying the migration is safe.

#### Scenario: NULL row with zero attempts is queued
- **WHEN** the migration runs and finds a row with `lifecycle IS NULL, status = 'pending', upload_attempts = 0`
- **THEN** the row's `lifecycle` SHALL be set to `'queued'`

#### Scenario: NULL row with prior attempts is retrying
- **WHEN** the migration runs and finds a row with `lifecycle IS NULL, status = 'pending', upload_attempts > 0`
- **THEN** the row's `lifecycle` SHALL be set to `'retrying'`

#### Scenario: Re-applying the migration is a no-op
- **WHEN** the migration is re-applied after all NULL rows have already been backfilled
- **THEN** the backfill UPDATE SHALL match zero rows and SHALL NOT modify any existing lifecycle values
