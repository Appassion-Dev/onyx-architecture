## Purpose

Delta spec: update discovery gate, conversion datetime, and conversion value requirements for the converted pipeline stage. Anchors all three to the linked job rather than the approved option.

## MODIFIED Requirements

### Requirement: Converted lead discovery criteria
**MODIFIED FROM:** The system SHALL consider an estimate as a converted lead when at least one `estimate_options` row has `approval_status IN ('approved', 'pro approved')`.

**TO:** The system SHALL consider an estimate as a converted lead when at least one `estimate_options` row has `approval_status IN ('approved', 'pro approved')` AND at least one job exists linked to that option via `jobs.original_estimate_id = estimate_options.id`.

#### Scenario: Estimate with approved option and linked job qualifies
- **WHEN** an estimate has at least one `estimate_options` row with `approval_status IN ('approved', 'pro approved')` and that option is the `original_estimate_id` of a job
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

#### Scenario: Approved option exists but no linked job does not qualify
- **WHEN** an estimate has an approved option but no job references that option via `jobs.original_estimate_id`
- **THEN** the estimate SHALL NOT be discovered as a converted lead

### Requirement: Converted lead conversion value
**MODIFIED FROM:** The system SHALL report the sum of `total_amount / 100.0` for estimate options with `approval_status IN ('approved', 'pro approved')` as the conversion value.

**TO:** The system SHALL report `jobs.total_amount / 100.0` as the conversion value, where `jobs.original_estimate_id` references the approved option.

#### Scenario: Job subtotal used as value
- **WHEN** a job linked to an approved option has `total_amount = 45000` (stored in cents)
- **THEN** the conversion value SHALL be `450.00`

#### Scenario: Job with zero total amount
- **WHEN** a job linked to an approved option has `total_amount = 0`
- **THEN** the conversion value SHALL be `0.00`

### Requirement: Converted lead conversion datetime
**MODIFIED FROM:** The system SHALL use `MAX(estimate_options.updated_at)` where `approval_status IN ('approved', 'pro approved')` as the conversion datetime.

**TO:** The system SHALL use `jobs.created_at` as the conversion datetime, where `jobs.original_estimate_id` references the approved option.

#### Scenario: Datetime from job creation
- **WHEN** a job is auto-created at `2026-04-15 14:23:00+00` for an approved option
- **THEN** the `conversion_datetime` SHALL be `2026-04-15 14:23:00+00`
