## Requirements

### Requirement: Booking lead discovery criteria
The system SHALL consider an estimate as a booking lead when it has ANY source signal: `is_booking_form = true`, at least one `booking_tags` row exists, at least one `callrail_leads` row is correlated via `estimate_id`, or `estimates.lead_source IS NOT NULL`.

#### Scenario: Estimate from booking form qualifies
- **WHEN** an estimate has `is_booking_form = true` and no other source signals
- **THEN** the estimate SHALL be discovered as a pending `booking_lead` conversion

#### Scenario: Estimate with booking tags qualifies
- **WHEN** an estimate has at least one row in `booking_tags` (regardless of `is_booking_form`)
- **THEN** the estimate SHALL be discovered as a pending `booking_lead` conversion

#### Scenario: Estimate with correlated CallRail lead qualifies
- **WHEN** a `callrail_leads` row has `estimate_id` matching the estimate
- **THEN** the estimate SHALL be discovered as a pending `booking_lead` conversion

#### Scenario: Estimate with lead_source qualifies
- **WHEN** an estimate has `lead_source IS NOT NULL` and no other source signals
- **THEN** the estimate SHALL be discovered as a pending `booking_lead` conversion

#### Scenario: Estimate with no source signal does not qualify
- **WHEN** an estimate has `is_booking_form = false`, no `booking_tags`, no correlated `callrail_leads`, and `lead_source IS NULL`
- **THEN** the estimate SHALL NOT be discovered as a booking lead

### Requirement: Booking lead conversion value
The system SHALL report `NULL` as the conversion value for booking lead conversions.

#### Scenario: Booking lead value is null
- **WHEN** a booking lead conversion is discovered
- **THEN** the `conversion_value` SHALL be `NULL`

### Requirement: Booking lead conversion datetime
The system SHALL use `estimates.created_at` as the conversion datetime for booking lead conversions.

#### Scenario: Booking lead datetime from estimate creation
- **WHEN** a booking lead conversion is discovered
- **THEN** the `conversion_datetime` SHALL equal `estimates.created_at`

### Requirement: Booking lead GCLID resolution
The system SHALL resolve the GCLID as `COALESCE(booking_tags.gclid, callrail_leads.gclid)`, preferring the booking form GCLID over the CallRail GCLID.

#### Scenario: GCLID from booking form preferred
- **WHEN** both `booking_tags` and `callrail_leads` have a GCLID for the same estimate
- **THEN** the booking form GCLID from `booking_tags` SHALL be used

#### Scenario: GCLID from CallRail used as fallback
- **WHEN** no `booking_tags` GCLID exists but `callrail_leads.gclid` is present
- **THEN** the CallRail GCLID SHALL be used

#### Scenario: No GCLID available
- **WHEN** neither source provides a GCLID
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending