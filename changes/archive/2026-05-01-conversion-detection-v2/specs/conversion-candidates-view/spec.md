## MODIFIED Requirements

### Requirement: View exposes display_value as average of all options
The system SHALL compute `display_value` as `AVG(estimate_options.total_amount) / 100.0` across ALL options on the estimate, regardless of approval status. When no options exist, `display_value` SHALL be `0`.

#### Scenario: Estimate with multiple options of varying approval status
- **WHEN** an estimate has three options with amounts $500, $1000, and $1500 regardless of their approval status
- **THEN** `display_value` equals `1000.00` (average of all three)

#### Scenario: Estimate with no options
- **WHEN** no `estimate_options` rows exist for the estimate
- **THEN** `display_value` is `0`

#### Scenario: display_value matches qualified_lead conversion_value
- **WHEN** a qualified_lead conversion row exists for an estimate
- **THEN** `display_value` in the view reflects the same AVG(all options) formula used when that row's `conversion_value` was captured at discovery time
