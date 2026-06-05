## Requirements

### Requirement: Qualified lead discovery is independent of booking_lead stage
The system SHALL discover qualified leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The qualified stage is a fully independent detector.

#### Scenario: Estimate with no booking_lead qualifies as qualified_lead
- **WHEN** an estimate is finalized (`work_status IN ('complete rated','complete unrated','created job from estimate')`) and has at least one priced `estimate_options` row (`total_amount > 0`) but no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

### Requirement: Qualified lead discovery criteria
The system SHALL consider an estimate as a qualified lead when BOTH conditions hold: (a) `estimates.work_status IN ('complete rated','complete unrated','created job from estimate')` (the estimate is finalized — its estimating visit completed or it was converted to a job), AND (b) at least one `estimate_options` row exists for that estimate with `total_amount > 0`. Option `approval_status` SHALL NOT be consulted. An estimate whose `work_status` is outside that set, or that has no priced option, SHALL NOT be discovered as qualified.

#### Scenario: Estimate converted to a job qualifies
- **WHEN** an estimate has `work_status = 'created job from estimate'` and at least one option with `total_amount > 0`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

#### Scenario: Completed estimate visit qualifies without an approved option
- **WHEN** an estimate has `work_status IN ('complete rated','complete unrated')` and at least one priced option (`total_amount > 0`) but no option with `approval_status IN ('approved','pro approved')`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion (approval is not consulted)

#### Scenario: In-flight estimate does not qualify
- **WHEN** an estimate has `work_status IN ('needs scheduling','scheduled','in progress')` even with a priced option
- **THEN** the estimate SHALL NOT be discovered as qualified

#### Scenario: Cancelled estimate does not qualify
- **WHEN** an estimate has `work_status IN ('user canceled','pro canceled')`
- **THEN** the estimate SHALL NOT be discovered as qualified

#### Scenario: Finalized estimate with no priced option does not qualify
- **WHEN** an estimate is finalized (`work_status` in the allowed set) but all its `estimate_options` rows have `total_amount IS NULL` or `total_amount = 0`, or it has no options
- **THEN** the estimate SHALL NOT be discovered as qualified

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
The system SHALL use the estimate's `work_timestamps.completed_at` as the `conversion_datetime` for qualified lead conversions when a non-NULL value is present, and SHALL fall back to `estimates.updated_at` otherwise. `completed_at` is stored as `timestamp without time zone` holding HCP's UTC value, so it SHALL be interpreted as UTC (`completed_at AT TIME ZONE 'UTC'`) to yield a `timestamptz` compatible with the fallback and the return type. Because `completed_at` is the literal visit-completion signal, it is preferred over `updated_at` (a lagging proxy) wherever it exists; `updated_at` guarantees 100% coverage so a value is always produced.

#### Scenario: Datetime uses completed_at when present
- **WHEN** a qualified lead is discovered for an estimate that has a `work_timestamps` row with a non-NULL `completed_at`
- **THEN** `conversion_datetime` SHALL equal that `completed_at` interpreted as UTC

#### Scenario: Datetime falls back to updated_at when no completed_at
- **WHEN** a qualified lead is discovered for an estimate that has no `work_timestamps` row, or whose `work_timestamps` row has a NULL `completed_at`
- **THEN** `conversion_datetime` SHALL equal `estimates.updated_at`

#### Scenario: Pending rows order by the conversion datetime
- **WHEN** pending qualified conversions are returned
- **THEN** they SHALL be ordered ascending by the same coalesced expression used for `conversion_datetime` (`completed_at` interpreted as UTC, else `updated_at`)

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