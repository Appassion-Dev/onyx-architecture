## Purpose

Defines when and how the Google Ads pipeline discovers a `converted_lead` conversion: the third and final stage of the pipeline, representing a customer who has accepted a quote and transitioned to a booked job.

## Requirements

### Requirement: Converted lead discovery is independent of booking_lead stage
The system SHALL discover converted leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The converted stage is a fully independent detector.

#### Scenario: Estimate with approved option but no booking_lead qualifies
- **WHEN** an estimate has at least one approved option and no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

### Requirement: Converted lead discovery criteria
The system SHALL consider an estimate as a converted lead when at least one `estimate_options` row has `approval_status IN ('approved', 'pro approved')` AND at least one job exists linked to that option via `jobs.original_estimate_id = estimate_options.id`.

#### Scenario: Estimate with approved option and linked job qualifies
- **WHEN** an estimate has at least one `estimate_options` row with `approval_status IN ('approved', 'pro approved')` and that option is the `original_estimate_id` of a job
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

#### Scenario: Approved option exists but no linked job does not qualify
- **WHEN** an estimate has an approved option but no job references that option via `jobs.original_estimate_id`
- **THEN** the estimate SHALL NOT be discovered as a converted lead

#### Scenario: Job exists but no approved option does not qualify
- **WHEN** a job exists for an estimate option but no option on the estimate has `approval_status IN ('approved', 'pro approved')`
- **THEN** the estimate SHALL NOT be discovered as a converted lead

### Requirement: Converted lead conversion value
The system SHALL report `jobs.total_amount / 100.0` as the conversion value, where `jobs.original_estimate_id` references the approved option.

#### Scenario: Job subtotal used as value
- **WHEN** a job linked to an approved option has `total_amount = 45000` (stored in cents)
- **THEN** the conversion value SHALL be `450.00`

#### Scenario: Job with zero total amount
- **WHEN** a job linked to an approved option has `total_amount = 0`
- **THEN** the conversion value SHALL be `0.00`

### Requirement: Converted lead conversion datetime
The system SHALL use `jobs.created_at` as the conversion datetime, where `jobs.original_estimate_id` references the approved option.

#### Scenario: Datetime from job creation
- **WHEN** a job is auto-created at `2026-04-15 14:23:00+00` for an approved option
- **THEN** the `conversion_datetime` SHALL be `2026-04-15 14:23:00+00`

### Requirement: Converted lead GCLID resolution
The system SHALL resolve the GCLID from the `customer_gclids` table using the estimate's `customer_id`, ordered by `first_seen_at ASC` (first-touch). If no entry exists for the customer, GCLID SHALL be NULL and the row is still discovered.

#### Scenario: GCLID resolved via customer attribution
- **WHEN** a converted lead is discovered and the estimate's customer has a row in `customer_gclids`
- **THEN** the GCLID SHALL be the earliest (`first_seen_at ASC`) entry for that customer

#### Scenario: No GCLID available — row still discovered
- **WHEN** no `customer_gclids` row exists for the estimate's customer
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending

### Requirement: Upload skip for missing tracking data
All three stages SHALL discover estimates as pending regardless of GCLID availability. At upload time, rows with no GCLID AND no enhanced identifiers (hashed email/phone) SHALL be marked `status='skipped'` with an error message.

#### Scenario: Pending row with no tracking data skipped at upload
- **WHEN** a pending conversion has `gclid IS NULL` and the customer has no email or phone
- **THEN** the upload edge function SHALL set `status='skipped'` and `error_message` describing the missing data

#### Scenario: Pending row with only enhanced identifiers uploads
- **WHEN** a pending conversion has `gclid IS NULL` but the customer has a hashed email or phone
- **THEN** the upload edge function SHALL attempt the upload using enhanced conversions