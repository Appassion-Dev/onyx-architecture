## MODIFIED Requirements

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

### Requirement: Qualified lead discovery is independent of booking_lead stage
The system SHALL discover qualified leads without requiring a prior `booking_lead` row in `gads_conversion_uploads` for the same estimate. The qualified stage is a fully independent detector.

#### Scenario: Estimate with no booking_lead qualifies as qualified_lead
- **WHEN** an estimate is finalized (`work_status IN ('complete rated','complete unrated','created job from estimate')`) and has at least one priced `estimate_options` row (`total_amount > 0`) but no `booking_lead` row in `gads_conversion_uploads`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion
