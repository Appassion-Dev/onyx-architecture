## Requirements

### Requirement: Unified conversion candidates view returns all estimates
The system SHALL expose a Postgres view `vw_conversion_candidates` that returns one row per estimate, with no filter on the existence of `gads_conversion_uploads` rows. All estimates are eligible to appear regardless of discovery state.

#### Scenario: Pre-discovery estimate is visible
- **WHEN** an estimate has no corresponding rows in `gads_conversion_uploads`
- **THEN** the view returns a row for that estimate with all stage status columns (`booking_status`, `qualified_status`, `converted_status`) as NULL

#### Scenario: Discovered estimate retains stage state
- **WHEN** an estimate has one or more rows in `gads_conversion_uploads`
- **THEN** the view returns a row with the correct stage status, upload_attempts, gclid, uploaded_at, error_message, and conversion_datetime for each stage that has a row

### Requirement: View exposes job context per estimate
The system SHALL resolve each estimate's associated job (via `estimate_options -> jobs`) and include `job_id`, `invoice_number`, `job_work_status`, and `job_total` on each view row. When no job exists, these columns SHALL be NULL.

#### Scenario: Estimate with an accepted job
- **WHEN** an estimate has an `estimate_option` that is the `original_estimate_id` of a job
- **THEN** the view row includes that job's `id`, `invoice_number`, `work_status`, and `total_amount / 100.0`

#### Scenario: Estimate with no job
- **WHEN** no job references any option on the estimate
- **THEN** `job_id`, `invoice_number`, `job_work_status`, and `job_total` are all NULL

#### Scenario: Estimate with multiple jobs
- **WHEN** multiple jobs reference options on the same estimate
- **THEN** the view returns the most recently created job's fields (ORDER BY `jobs.created_at DESC LIMIT 1`)

### Requirement: View exposes display_value as average of all options
The system SHALL compute `display_value` as `AVG(estimate_options.total_amount) / 100.0` across ALL options on the estimate, regardless of approval status. When no options exist, `display_value` SHALL be `0`.

#### Scenario: Estimate with options
- **WHEN** an estimate has one or more `estimate_options` rows
- **THEN** `display_value` equals the average of all options' `total_amount` divided by 100

#### Scenario: Estimate with no options
- **WHEN** no `estimate_options` rows exist for the estimate
- **THEN** `display_value` is `0`

### Requirement: View exposes source signals for every estimate
The system SHALL include `has_form` (boolean), `lead_source` (text), `call_count` (integer), and `callrail_sources` (text array) on every row, regardless of whether the estimate has been discovered.

#### Scenario: Booking form estimate
- **WHEN** `estimates.is_booking_form = true`
- **THEN** `has_form` is `true`

#### Scenario: Estimate with CallRail calls
- **WHEN** one or more `callrail_leads` rows are correlated to the estimate
- **THEN** `call_count` reflects the count and `callrail_sources` contains the distinct source values

### Requirement: is_closed is false for pre-discovery estimates
The system SHALL compute `is_closed` as `false` for any estimate where all stage status columns are NULL (i.e., no pipeline rows exist yet).

#### Scenario: Pre-discovery estimate is not closed
- **WHEN** `booking_status`, `qualified_status`, and `converted_status` are all NULL
- **THEN** `is_closed` is `false`

#### Scenario: Fully uploaded estimate is closed
- **WHEN** at least one stage row exists AND all non-null stages have status `'uploaded'` or `'skipped'`
- **THEN** `is_closed` is `true`

### Requirement: Frontend queries apply a time-window filter at query time
The system SHALL NOT bake a time filter into `vw_conversion_candidates`. The frontend ConversionsPage SHALL apply a 90-day filter via `.gte('estimate_created_at', cutoff)` at query time.

#### Scenario: Dashboard loads with 90-day window
- **WHEN** `ConversionsPage` fetches from `vw_conversion_candidates`
- **THEN** the query includes `.gte('estimate_created_at', now minus 90 days)` and returns only estimates created within that window