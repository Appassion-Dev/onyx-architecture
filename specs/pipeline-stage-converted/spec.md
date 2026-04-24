## Requirements

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
The system SHALL resolve the GCLID identically to the other stages: `COALESCE(booking_tags.gclid, callrail_leads.gclid)`.

#### Scenario: GCLID resolved via estimate sources
- **WHEN** a converted lead is discovered
- **THEN** the GCLID SHALL be resolved from `booking_tags` (preferred) or `callrail_leads` (fallback)

#### Scenario: No GCLID available
- **WHEN** neither source provides a GCLID
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending

### Requirement: Upload skip for missing tracking data
All three stages SHALL discover estimates as pending regardless of GCLID availability. At upload time, rows with no GCLID AND no enhanced identifiers (hashed email/phone) SHALL be marked `status='skipped'` with an error message.

#### Scenario: Pending row with no tracking data skipped at upload
- **WHEN** a pending conversion has `gclid IS NULL` and the customer has no email or phone
- **THEN** the upload edge function SHALL set `status='skipped'` and `error_message` describing the missing data

#### Scenario: Pending row with only enhanced identifiers uploads
- **WHEN** a pending conversion has `gclid IS NULL` but the customer has a hashed email or phone
- **THEN** the upload edge function SHALL attempt the upload using enhanced conversions