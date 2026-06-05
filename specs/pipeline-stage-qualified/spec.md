## Requirements

### Requirement: Qualified lead discovery is independent of booking_lead stage
The system SHALL discover qualified leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The qualified stage is a fully independent detector.

#### Scenario: Estimate with no booking_lead qualifies as qualified_lead
- **WHEN** an estimate has at least one approved, priced `estimate_options` row but no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

### Requirement: Qualified lead discovery criteria
The system SHALL consider an estimate as a qualified lead when at least one `estimate_options` row exists for that estimate with `approval_status IN ('approved','pro approved')` AND `total_amount > 0`. The estimate's own `work_status` is NOT consulted by this gate. An estimate with no approved-and-priced options SHALL NOT be discovered as qualified.

#### Scenario: Estimate with an approved priced option qualifies regardless of work_status
- **WHEN** an estimate has at least one `estimate_options` row with `approval_status IN ('approved','pro approved')` AND `total_amount > 0`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion regardless of `estimates.work_status`

#### Scenario: Estimate with `created job from estimate` work_status qualifies
- **WHEN** an estimate has `work_status = 'created job from estimate'` and at least one option that is both approved (`approval_status IN ('approved','pro approved')`) and priced (`total_amount > 0`)
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

#### Scenario: Estimate with no priced options does not qualify
- **WHEN** all `estimate_options` rows for an estimate have `total_amount IS NULL` or `total_amount = 0`, or no options exist
- **THEN** the estimate SHALL NOT be discovered as a qualified lead

#### Scenario: Estimate with priced but unapproved options does not qualify
- **WHEN** all `estimate_options` rows for an estimate have `total_amount > 0` but no option has `approval_status IN ('approved','pro approved')`
- **THEN** the estimate SHALL NOT be discovered as a qualified lead

#### Scenario: Estimate with non-complete work_status now qualifies if approved and priced
- **WHEN** an estimate has `work_status` such as `'needs scheduling'`, `'scheduled'`, or `'in progress'` and has at least one approved priced option
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

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

### Requirement: Qualified lead conversion datetime
The system SHALL use `estimates.updated_at` as the `conversion_datetime` for qualified lead conversions. This field captures the moment the estimate's work_status was last changed — which is the transition to complete.

#### Scenario: Datetime reflects estimate completion timestamp
- **WHEN** a qualified lead is discovered for an estimate with `work_status = 'complete rated'`
- **THEN** `conversion_datetime` SHALL equal `estimates.updated_at`

### Requirement: Qualified lead GCLID resolution
The system SHALL resolve the GCLID with an inline subquery against the `customer_gclids` table using the estimate's `customer_id`, restricted to entries with `first_seen_at >= estimates.updated_at - INTERVAL '90 days'`, ordered by `first_seen_at ASC` (earliest in-window first-touch), taking the first match. If no in-window entry exists, GCLID SHALL be NULL and the row is still discovered.

#### Scenario: GCLID resolved via customer attribution within the 90-day window
- **WHEN** a qualified lead is discovered and the estimate's customer has a `customer_gclids` row with `first_seen_at >= estimates.updated_at - INTERVAL '90 days'`
- **THEN** the GCLID SHALL be the earliest (`first_seen_at ASC`) in-window entry for that customer

#### Scenario: GCLID older than the 90-day window is excluded
- **WHEN** the estimate's customer has only `customer_gclids` rows with `first_seen_at < estimates.updated_at - INTERVAL '90 days'`
- **THEN** those rows SHALL NOT be selected, and if no in-window row exists the GCLID SHALL be `NULL`

#### Scenario: No GCLID available — row still discovered
- **WHEN** no in-window `customer_gclids` row exists for the estimate's customer
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending