## Requirements

### Requirement: Converted lead discovery is independent of booking_lead stage
The system SHALL discover converted leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The converted stage is a fully independent detector.

#### Scenario: Estimate with approved option but no booking_lead qualifies
- **WHEN** an estimate has at least one approved option and no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

### Requirement: Converted lead discovery criteria
The system SHALL consider an estimate as a converted lead when at least one `estimate_options` row has `approval_status IN ('approved', 'pro approved')`.

#### Scenario: Estimate with approved option qualifies
- **WHEN** an estimate has at least one `estimate_options` row with `approval_status = 'approved'`
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

#### Scenario: Estimate with pro-approved option qualifies
- **WHEN** an estimate has at least one `estimate_options` row with `approval_status = 'pro approved'`
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

#### Scenario: Estimate with only non-approved options does not qualify
- **WHEN** all `estimate_options` rows have `approval_status IN ('declined', 'pro declined', 'awaiting response', 'expired')` or `approval_status IS NULL`
- **THEN** the estimate SHALL NOT be discovered as a converted lead

### Requirement: Converted lead conversion value
The system SHALL report the sum of `total_amount / 100.0` for estimate options with `approval_status IN ('approved', 'pro approved')` as the conversion value.

#### Scenario: Value is sum of approved options
- **WHEN** an estimate has approved options totaling $3,200 (stored as 320000 cents)
- **THEN** the conversion value SHALL be `3200.00`

#### Scenario: Declined options excluded from value
- **WHEN** an estimate has one approved option ($2000) and one declined option ($800)
- **THEN** the conversion value SHALL be `2000.00`

### Requirement: Converted lead conversion datetime
The system SHALL use `MAX(estimate_options.updated_at)` where `approval_status IN ('approved', 'pro approved')` as the conversion datetime.

#### Scenario: Datetime from most recent approval
- **WHEN** an estimate has two approved options, one updated at 2026-03-01 and one at 2026-03-15
- **THEN** the `conversion_datetime` SHALL be `2026-03-15`

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