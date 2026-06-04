## MODIFIED Requirements

### Requirement: Booking lead discovery criteria
The system SHALL consider an estimate a booking lead based **solely** on a schedule gate: the estimate has a non-null `schedule.scheduled_start` (a `schedules` row with `scheduled_start IS NOT NULL` exists for the estimate) **AND** has at least one assigned employee (an `estimate_assignments` row exists for the estimate).

The previously-required attribution source signals (`is_booking_form = true`, a `booking_tags` row, a correlated `callrail_leads` row, a `customer_gclids` row, and `estimates.lead_source IS NOT NULL`) SHALL NOT gate eligibility. They SHALL be retained as commented-out conditions inside `get_pending_booking_lead_conversions()` so they can be re-enabled later without being rewritten.

An estimate that already has a `gads_conversion_uploads` row with `conversion_type = 'booking_lead'` SHALL NOT be re-discovered.

#### Scenario: Scheduled estimate with an assigned employee qualifies
- **WHEN** an estimate has a `schedules` row with non-null `scheduled_start` and at least one `estimate_assignments` row
- **THEN** the estimate SHALL be discovered as a pending `booking_lead` conversion

#### Scenario: Estimate without a scheduled_start does not qualify
- **WHEN** an estimate has no `schedules` row with a non-null `scheduled_start`
- **THEN** the estimate SHALL NOT be discovered as a booking lead, regardless of any attribution signal

#### Scenario: Scheduled estimate without an assigned employee does not qualify
- **WHEN** an estimate has a non-null `scheduled_start` but no `estimate_assignments` row
- **THEN** the estimate SHALL NOT be discovered as a booking lead

#### Scenario: Source signals no longer gate eligibility
- **WHEN** an estimate has an attribution source signal (e.g. `is_booking_form = true`) but no non-null `scheduled_start`
- **THEN** the estimate SHALL NOT be discovered as a booking lead

#### Scenario: Cancelled-but-scheduled estimate still qualifies (default behavior)
- **WHEN** an estimate has a non-null `scheduled_start` and an assigned employee but `work_status` is `user canceled` or `pro canceled`
- **THEN** the estimate SHALL still be discovered as a booking lead
- **THEN** NOTE: excluding cancelled estimates via `work_status` is a documented open item and is NOT applied by default

#### Scenario: Already-uploaded estimate is not re-discovered
- **WHEN** a `gads_conversion_uploads` row with `conversion_type = 'booking_lead'` already exists for the estimate
- **THEN** the estimate SHALL NOT be discovered again

### Requirement: Booking lead GCLID resolution
The system SHALL resolve the GCLID as `COALESCE(booking_tags.gclid, callrail_leads.gclid, customer_gclids.gclid)`, preferring the booking-form GCLID, then the most-recent correlated CallRail GCLID, then the oldest (first-touch by `first_seen_at`) `customer_gclids` GCLID for the estimate's customer. GCLID resolution is independent of eligibility (it derives a value, it does not filter rows).

#### Scenario: GCLID from booking form preferred
- **WHEN** `booking_tags` and another source both have a GCLID for the same estimate
- **THEN** the booking form GCLID from `booking_tags` SHALL be used

#### Scenario: GCLID from CallRail used as fallback
- **WHEN** no `booking_tags` GCLID exists but `callrail_leads.gclid` is present
- **THEN** the CallRail GCLID SHALL be used

#### Scenario: GCLID from customer_gclids first-touch fallback
- **WHEN** no `booking_tags` or `callrail_leads` GCLID exists but the estimate's customer has a `customer_gclids` row
- **THEN** the oldest (`first_seen_at ASC`) `customer_gclids.gclid` SHALL be used

#### Scenario: No GCLID available
- **WHEN** none of the sources provides a GCLID
- **THEN** the GCLID SHALL be `NULL` and the row SHALL still be discovered as pending
