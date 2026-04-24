## ADDED Requirements

### Requirement: Pivot view returns one row per estimate
The `vw_gads_conversion_pipeline` view SHALL return exactly one row per `estimate_id` that has at least one record in `gads_conversion_uploads`. Each row SHALL include per-stage columns for booking_lead, qualified_lead, and converted_lead.

#### Scenario: Estimate with all three stages
- **WHEN** an estimate has booking_lead, qualified_lead, and converted_lead rows in `gads_conversion_uploads`
- **THEN** the view returns one row with non-NULL values for `booking_status`, `qualified_status`, and `converted_status`

#### Scenario: Estimate with only booking stage
- **WHEN** an estimate has only a booking_lead row in `gads_conversion_uploads`
- **THEN** the view returns one row with non-NULL `booking_status` and NULL `qualified_status` and `converted_status`

#### Scenario: Unique constraint guarantees clean pivot
- **WHEN** the unique constraint `(estimate_id, conversion_type)` exists on `gads_conversion_uploads`
- **THEN** each stage column maps to at most one source row, with no aggregation ambiguity

### Requirement: Display value matches sales page logic
The view SHALL compute `display_value` using the same logic as `fn_get_sales_table_data`: when `estimates_settings.total_amount_source = 'JOB'`, use `jobs.total_amount / 100.0`; otherwise use `estimate_options.total_amount / 100.0`.

#### Scenario: Estimate with JOB amount source preference
- **WHEN** `estimates_settings.total_amount_source` is `'JOB'` for an estimate and a linked job exists with `total_amount = 95000`
- **THEN** `display_value` SHALL be `950.00`

#### Scenario: Estimate with default ESTIMATE amount source
- **WHEN** `estimates_settings.total_amount_source` is `'ESTIMATE'` (or NULL/missing) and the approved estimate option has `total_amount = 45000`
- **THEN** `display_value` SHALL be `450.00`

#### Scenario: Estimate with no settings row
- **WHEN** no row exists in `estimates_settings` for an estimate
- **THEN** `display_value` SHALL fall back to the estimate option amount (default ESTIMATE behavior)

### Requirement: Booking source column
The view SHALL expose a `booking_source` column indicating how the booking originated.

#### Scenario: Booking from website form
- **WHEN** `estimates.is_booking_form = true`
- **THEN** `booking_source` SHALL be `'form'`

#### Scenario: Booking from CallRail call
- **WHEN** a `callrail_leads` record is correlated to the estimate and `is_booking_form` is false
- **THEN** `booking_source` SHALL be `'call'`

#### Scenario: No identifiable booking source
- **WHEN** `is_booking_form` is false and no `callrail_leads` record exists
- **THEN** `booking_source` SHALL be NULL

### Requirement: Closed flag computed from stage sync status
The view SHALL expose an `is_closed` boolean that is true only when all existing stages for an estimate have `status IN ('uploaded', 'skipped')`.

#### Scenario: All stages synced
- **WHEN** an estimate has booking_lead (uploaded), qualified_lead (uploaded), and converted_lead (skipped)
- **THEN** `is_closed` SHALL be `true`

#### Scenario: One stage still pending
- **WHEN** an estimate has booking_lead (uploaded) and qualified_lead (pending)
- **THEN** `is_closed` SHALL be `false`

#### Scenario: One stage errored
- **WHEN** an estimate has booking_lead (pending, upload_attempts > 0)
- **THEN** `is_closed` SHALL be `false`

#### Scenario: No stages exist
- **WHEN** an estimate has no rows in `gads_conversion_uploads` (edge case — shouldn't appear in view)
- **THEN** the estimate SHALL NOT appear in the view results

### Requirement: Per-stage detail columns
For each pipeline stage (booking, qualified, converted), the view SHALL expose: `status`, `upload_attempts`, `gclid`, `uploaded_at`, `error_message`, `conversion_value`, and `conversion_datetime`.

#### Scenario: Booking stage detail
- **WHEN** a booking_lead row exists with status='uploaded', gclid='CjwKCA...', uploaded_at='2026-04-02T15:00:00Z'
- **THEN** `booking_status` = 'uploaded', `booking_gclid` = 'CjwKCA...', `booking_uploaded_at` = '2026-04-02T15:00:00Z'

#### Scenario: Missing stage has NULL detail columns
- **WHEN** no qualified_lead row exists for an estimate
- **THEN** `qualified_status`, `qualified_upload_attempts`, `qualified_gclid`, `qualified_uploaded_at`, `qualified_error_message`, `qualified_value`, `qualified_datetime` SHALL all be NULL
