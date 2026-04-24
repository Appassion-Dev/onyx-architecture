## ADDED Requirements

### Requirement: Qualified lead discovery criteria
The system SHALL consider an estimate as a qualified lead when at least one `estimate_options` row has `total_amount IS NOT NULL`.

#### Scenario: Estimate with quoted option qualifies
- **WHEN** an estimate has at least one `estimate_options` row where `total_amount IS NOT NULL`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

#### Scenario: Estimate with no option amounts does not qualify
- **WHEN** all `estimate_options` rows for an estimate have `total_amount IS NULL`, or no options exist
- **THEN** the estimate SHALL NOT be discovered as a qualified lead

#### Scenario: Zero-dollar option qualifies
- **WHEN** an estimate has an option with `total_amount = 0` (not null)
- **THEN** the estimate SHALL be discovered as a qualified lead

### Requirement: Qualified lead conversion value
The system SHALL report the sum of `total_amount / 100.0` for estimate options with `approval_status IN ('approved', 'pro approved')` as the conversion value.

#### Scenario: Value is sum of approved options
- **WHEN** an estimate has approved options with amounts $1500 and $500 (stored as 150000 and 50000 cents)
- **THEN** the conversion value SHALL be `2000.00`

#### Scenario: Value is zero when no options approved
- **WHEN** an estimate has options with total_amount but none have `approval_status IN ('approved', 'pro approved')`
- **THEN** the conversion value SHALL be `0` or `NULL`

#### Scenario: Only approved options counted in value
- **WHEN** an estimate has one approved option ($1000) and one declined option ($500)
- **THEN** the conversion value SHALL be `1000.00`

### Requirement: Qualified lead conversion datetime
The system SHALL use `estimates.updated_at` as the conversion datetime for qualified lead conversions.

#### Scenario: Qualified lead datetime from estimate update
- **WHEN** a qualified lead conversion is discovered
- **THEN** the `conversion_datetime` SHALL equal `estimates.updated_at`

### Requirement: Qualified lead GCLID resolution
The system SHALL resolve the GCLID identically to the booking stage: `COALESCE(booking_tags.gclid, callrail_leads.gclid)`.

#### Scenario: GCLID resolved via estimate sources
- **WHEN** a qualified lead is discovered
- **THEN** the GCLID SHALL be resolved from `booking_tags` (preferred) or `callrail_leads` (fallback)

#### Scenario: No GCLID available
- **WHEN** neither source provides a GCLID
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending
