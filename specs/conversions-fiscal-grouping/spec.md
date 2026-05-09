## MODIFIED Requirements

### Requirement: Conversions page groups estimates by fiscal month
The Conversions page month-level grouping SHALL use the fiscal calendar system (Thursday-belongs rule), where each ISO week is assigned to the calendar month containing its Thursday. The date field used for grouping SHALL be determined by the active conversion mode: `estimate_created_at` for Pre-discovery, `booking_datetime` for Booking, `qualified_datetime` for Qualified, `converted_datetime` for Converted. All estimates within the same ISO week SHALL appear under the same month header, regardless of their individual calendar date.

#### Scenario: Estimate on a calendar month boundary lands in correct fiscal month
- **WHEN** an estimate was created on Mar 30, 2026 (ISO week W14, Thursday Apr 2 -> fiscal April) and the active mode is Pre-discovery
- **THEN** the estimate appears under the "April 2026" month group

#### Scenario: Qualified mode groups by qualified_datetime
- **WHEN** the active mode is Qualified and an estimate has `qualified_datetime` of Apr 15, 2026
- **THEN** the estimate appears under "April 2026" based on the qualified date, not the estimate creation date

#### Scenario: Converted mode groups by converted_datetime
- **WHEN** the active mode is Converted and an estimate has `converted_datetime` of May 2, 2026
- **THEN** the estimate appears under "May 2026" based on the converted date

#### Scenario: Row with null mode date appears in Unknown group
- **WHEN** the active mode is Booking and an estimate has a NULL `booking_datetime`
- **THEN** the estimate appears under an "Unknown" group (this should not occur in practice because the mode filter only shows estimates with a non-null stage, but the grouping must handle it gracefully)

#### Scenario: All estimates in the same ISO week share a month group
- **WHEN** estimates exist on both Mar 30 and Apr 5, 2026 (both in W14/2026) and the active mode is Pre-discovery
- **THEN** both estimates appear under the same "April 2026" month group

#### Scenario: Month sections sort newest-first
- **WHEN** the Conversions page renders month groups
- **THEN** the most recent month appears first (descending order)

### Requirement: Month sort keys encode fiscal identity
The month group sort keys used for ordering month sections SHALL encode the fiscal year and fiscal month (not the raw calendar date), derived from the mode-appropriate date field.

#### Scenario: Estimates from the same fiscal month sort together
- **WHEN** two estimates have mode-appropriate dates in the same fiscal month
- **THEN** both use the same month sort key and appear in the same month section
