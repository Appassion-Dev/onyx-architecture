## ADDED Requirements

### Requirement: Converted lead discovery is independent of booking_lead stage
The system SHALL discover converted leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The converted stage is a fully independent detector.

#### Scenario: Estimate with approved option but no booking_lead qualifies
- **WHEN** an estimate has at least one approved option and no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

## MODIFIED Requirements

### Requirement: Converted lead GCLID resolution
The system SHALL resolve the GCLID from the `customer_gclids` table using the estimate's `customer_id`, ordered by `first_seen_at ASC` (first-touch). If no entry exists for the customer, GCLID SHALL be NULL and the row is still discovered.

#### Scenario: GCLID resolved via customer attribution
- **WHEN** a converted lead is discovered and the estimate's customer has a row in `customer_gclids`
- **THEN** the GCLID SHALL be the earliest (`first_seen_at ASC`) entry for that customer

#### Scenario: No GCLID available — row still discovered
- **WHEN** no `customer_gclids` row exists for the estimate's customer
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending
