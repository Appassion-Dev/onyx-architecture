## Requirements

### Requirement: Multi-source badge rendering
The ConversionsPage SHALL render all applicable lead source signals as separate badges for each estimate row.

#### Scenario: Estimate from booking form shows Form badge
- **WHEN** an estimate has `has_form = true`
- **THEN** a "Form" badge SHALL be rendered

#### Scenario: Estimate with correlated calls shows Call badge with count
- **WHEN** an estimate has `call_count = 3`
- **THEN** a "Call (3)" badge SHALL be rendered

#### Scenario: Estimate with lead_source shows lead source badge
- **WHEN** an estimate has `lead_source = 'Google Ads'`
- **THEN** a "Google Ads" badge SHALL be rendered

#### Scenario: CallRail lead sources shown as badges
- **WHEN** an estimate has correlated CallRail leads with sources "Google Ads" and "Google Local Services"
- **THEN** badges for "Google Ads" and "Google Local Services" SHALL be rendered

#### Scenario: Duplicate sources deduplicated
- **WHEN** an estimate has `lead_source = 'Google Ads'` AND a CallRail lead with `source = 'Google Ads'`
- **THEN** only one "Google Ads" badge SHALL be rendered

#### Scenario: Multiple source types combined
- **WHEN** an estimate has `has_form = true`, `call_count = 1`, `lead_source = 'Google Ads'`, and a CallRail source of 'Google Local Services'
- **THEN** badges "Form", "Call (1)", "Google Ads", and "Google Local Services" SHALL all be rendered

#### Scenario: No source signals
- **WHEN** an estimate has `has_form = false`, `call_count = 0`, `lead_source IS NULL`, and no CallRail sources
- **THEN** a "—" placeholder SHALL be rendered instead of badges