## ADDED Requirements

### Requirement: Converted discovery gate requires approved option and linked job
The system SHALL discover a converted lead when an estimate has at least one `estimate_options` row with `approval_status IN ('approved', 'pro approved')` AND at least one linked job exists via `jobs.original_estimate_id = estimate_options.id`. Both conditions MUST be satisfied.

#### Scenario: Estimate with approved option and linked job qualifies
- **WHEN** an estimate has at least one `estimate_options` row with `approval_status IN ('approved', 'pro approved')` and that option is the `original_estimate_id` of a job
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

#### Scenario: Approved option exists but no linked job does not qualify
- **WHEN** an estimate has an approved option but no job references that option via `jobs.original_estimate_id`
- **THEN** the estimate SHALL NOT be discovered as a converted lead

#### Scenario: Job exists but no approved option does not qualify
- **WHEN** a job exists for an estimate option but no option on the estimate has `approval_status IN ('approved', 'pro approved')`
- **THEN** the estimate SHALL NOT be discovered as a converted lead

### Requirement: Converted conversion datetime is job creation timestamp
The system SHALL use `jobs.created_at` as the `conversion_datetime` for the converted stage. This is the moment HCP automation auto-created the job from the approved estimate.

#### Scenario: Job created at known time
- **WHEN** a job is auto-created at `2026-04-15 14:23:00+00` for an approved option
- **THEN** the `conversion_datetime` SHALL be `2026-04-15 14:23:00+00`

### Requirement: Converted conversion value is job subtotal
The system SHALL use `jobs.total_amount / 100.0` as the `conversion_value` for the converted stage. This is the authoritative subtotal from the job.

#### Scenario: Job subtotal used as value
- **WHEN** a job has `total_amount = 45000` (stored in cents)
- **THEN** the conversion value SHALL be `450.00`

#### Scenario: Job with zero total amount
- **WHEN** a job has `total_amount = 0`
- **THEN** the conversion value SHALL be `0.00`

### Requirement: Converted GCLID lookback anchored to job creation
The system SHALL filter `customer_gclids` entries to those with `first_seen_at >= job.created_at - INTERVAL '90 days'` when resolving the GCLID for the converted stage. The lookback window is anchored to the job creation timestamp.

#### Scenario: GCLID within 90 days of job creation
- **WHEN** a job is created on `2026-05-01` and a customer GCLID has `first_seen_at = 2026-04-15`
- **THEN** the GCLID SHALL be included in the resolution (within 90-day window)

#### Scenario: GCLID outside 90 days of job creation
- **WHEN** a job is created on `2026-05-01` and a customer GCLID has `first_seen_at = 2026-01-15`
- **THEN** the GCLID SHALL be excluded from the resolution (outside 90-day window)

### Requirement: Converted discovery returns linked job_id
The system SHALL return the `job_id` column populated with the linked job's `id` when a converted lead is discovered.

#### Scenario: Job ID returned for discovered converted lead
- **WHEN** an estimate qualifies as a converted lead with a linked job `id = 'JOB-7534'`
- **THEN** the `job_id` return column SHALL be `'JOB-7534'`
