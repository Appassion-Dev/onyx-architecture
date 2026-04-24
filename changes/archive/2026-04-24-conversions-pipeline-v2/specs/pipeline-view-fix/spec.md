## ADDED Requirements

### Requirement: One row per estimate
The pipeline view SHALL return exactly one row per estimate, regardless of how many callrail_leads or estimate_options records are associated with that estimate.

#### Scenario: Estimate with multiple correlated calls
- **WHEN** an estimate has 3 callrail_leads records correlated to it
- **THEN** the view returns exactly 1 row for that estimate with `call_count = 3`

#### Scenario: Estimate with multiple approved options
- **WHEN** an estimate has 2 estimate_options in 'approved' status with amounts $500 and $300
- **AND** `total_amount_source` is 'ESTIMATE'
- **THEN** the view returns exactly 1 row with `display_value = 800.00`

#### Scenario: Estimate with job-based value
- **WHEN** an estimate has a converted_lead with a linked job
- **AND** `total_amount_source` is 'JOB'
- **THEN** `display_value` uses `jobs.total_amount / 100.0` (ignoring estimate_options)

### Requirement: Call count column
The pipeline view SHALL include a `call_count` integer column representing the number of callrail_leads records correlated to each estimate.

#### Scenario: Estimate with no calls
- **WHEN** an estimate has no callrail_leads records
- **THEN** `call_count = 0`

#### Scenario: Estimate with calls
- **WHEN** an estimate has 5 callrail_leads records
- **THEN** `call_count = 5`

### Requirement: Booking source derivation
The pipeline view SHALL derive `booking_source` with priority: form > call > null.

#### Scenario: Form booking
- **WHEN** `estimates.is_booking_form = true`
- **THEN** `booking_source = 'form'` regardless of whether callrail records exist

#### Scenario: Call-only lead
- **WHEN** `estimates.is_booking_form` is false or null
- **AND** `call_count > 0`
- **THEN** `booking_source = 'call'`

#### Scenario: No online source
- **WHEN** `estimates.is_booking_form` is false or null
- **AND** `call_count = 0`
- **THEN** `booking_source IS NULL`

### Requirement: Callrail RLS grant
The `callrail_leads` table SHALL have SELECT granted to the `authenticated` role so the frontend can query call records directly.

#### Scenario: Authenticated user queries callrail_leads
- **WHEN** an authenticated user queries `callrail_leads` filtered by `estimate_id`
- **THEN** the query succeeds and returns matching rows
