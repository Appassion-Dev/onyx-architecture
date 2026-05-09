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
The system SHALL include `has_form` (boolean), `lead_source` (text), `channel` (text), `call_count` (integer), `callrail_sources` (text array), `form_utm_source` (text), `form_utm_medium` (text), `form_hsa_src` (text), and `form_ref` (text) on every row, regardless of whether the estimate has been discovered.

`channel` SHALL be the resolved taxonomy channel (one of: `'Google Ads'`, `'GLS'`, `'GMB'`, `'Thumbtack'`, `'Organic'`, `'Direct'`, `'Other'`) computed by the priority chain defined in `conversion-channel-grouping/spec.md`.

`form_utm_source`, `form_utm_medium`, `form_hsa_src`, and `form_ref` are extracted from `booking_tags` and SHALL be NULL when no corresponding tag exists.

#### Scenario: Booking form estimate
- **WHEN** `estimates.is_booking_form = true`
- **THEN** `has_form` is `true`

#### Scenario: Estimate with CallRail calls
- **WHEN** one or more `callrail_leads` rows are correlated to the estimate
- **THEN** `call_count` reflects the count and `callrail_sources` contains the distinct source values

#### Scenario: Booking form estimate with resolved channel
- **WHEN** `estimates.lead_source = 'Google Ads'` (set by the write-time resolver)
- **THEN** `channel = 'Google Ads'`

#### Scenario: Form estimate with UTM tags
- **WHEN** `booking_tags` contains `utm_source = 'google'` for an estimate
- **THEN** `form_utm_source = 'google'`

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

### Requirement: Reconciliation view schema is aligned with channel taxonomy
The `vw_gads_upload_reconciliation_daily` view SHALL NOT contain any source-bucket aggregation columns. The view's schema SHALL consist solely of: `event_key`, `event_label`, `event_sort_order`, `conversion_action_id`, `conversion_action_name`, `reporting_date`, `local_uploaded_count`, `gclid_count`, `amount`, `google_successful_count`, `google_failed_count`, `has_local_data`, `has_google_data`, and `latest_google_synced_at`.

#### Scenario: SELECT * returns no bucket columns
- **WHEN** `SELECT * FROM vw_gads_upload_reconciliation_daily` is executed
- **THEN** the result set contains no columns named `form_*`, `calls_*`, `thumbtack_*`, or `other_*`