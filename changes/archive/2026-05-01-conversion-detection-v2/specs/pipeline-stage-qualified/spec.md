## ADDED Requirements

### Requirement: Qualified lead discovery is independent of booking_lead stage
The system SHALL discover qualified leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The qualified stage is a fully independent detector.

#### Scenario: Estimate with no booking_lead qualifies as qualified_lead
- **WHEN** an estimate has `work_status IN ('complete rated', 'complete unrated')` but no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

## MODIFIED Requirements

### Requirement: Qualified lead discovery criteria
The system SHALL consider an estimate as a qualified lead when BOTH conditions are met: (1) `estimates.work_status` is `'complete rated'` or `'complete unrated'`, AND (2) the estimate has at least one `estimate_options` row with `total_amount > 0`. An estimate with a complete work_status but no priced options has no measurable scope and SHALL NOT be discovered.

#### Scenario: Estimate with work_status complete rated qualifies
- **WHEN** an estimate has `work_status = 'complete rated'` and at least one option with `total_amount > 0`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

#### Scenario: Estimate with work_status complete unrated qualifies
- **WHEN** an estimate has `work_status = 'complete unrated'` and at least one option with `total_amount > 0`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

#### Scenario: Estimate with non-complete work_status does not qualify
- **WHEN** an estimate has `work_status` not in `('complete rated', 'complete unrated')` (e.g., `'needs scheduling'`, `'scheduled'`, `'in progress'`)
- **THEN** the estimate SHALL NOT be discovered as a qualified lead

#### Scenario: Estimate with complete work_status but all $0 options does not qualify
- **WHEN** an estimate has `work_status = 'complete rated'` but all `estimate_options` rows have `total_amount = 0` (or no options exist)
- **THEN** the estimate SHALL NOT be discovered as a qualified lead

### Requirement: Qualified lead conversion datetime
The system SHALL use `estimates.updated_at` as the `conversion_datetime` for qualified lead conversions. This field captures the moment the estimate's work_status was last changed — which is the transition to complete.

#### Scenario: Datetime reflects estimate completion timestamp
- **WHEN** a qualified lead is discovered for an estimate with `work_status = 'complete rated'`
- **THEN** `conversion_datetime` SHALL equal `estimates.updated_at`

### Requirement: Qualified lead conversion value
The system SHALL report the average of `total_amount / 100.0` across ALL estimate options (regardless of approval status) as the conversion value. When no options exist, the value SHALL be `0`.

#### Scenario: Value is average of all options
- **WHEN** an estimate has three options with amounts $500, $1000, and $1500 (stored as 50000, 100000, 150000 cents)
- **THEN** the conversion value SHALL be `1000.00`

#### Scenario: Value includes unapproved options
- **WHEN** an estimate has one approved option ($1000) and one declined option ($500)
- **THEN** the conversion value SHALL be `750.00` (average of both)

#### Scenario: Value is zero when no options exist
- **WHEN** an estimate has no `estimate_options` rows
- **THEN** the conversion value SHALL be `0`

### Requirement: Qualified lead GCLID resolution
The system SHALL resolve the GCLID from the `customer_gclids` table using the estimate's `customer_id`, ordered by `first_seen_at ASC` (first-touch). If no entry exists for the customer, GCLID SHALL be NULL and the row is still discovered.

#### Scenario: GCLID resolved via customer attribution
- **WHEN** a qualified lead is discovered and the estimate's customer has a row in `customer_gclids`
- **THEN** the GCLID SHALL be the earliest (`first_seen_at ASC`) entry for that customer

#### Scenario: No GCLID available — row still discovered
- **WHEN** no `customer_gclids` row exists for the estimate's customer
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending
