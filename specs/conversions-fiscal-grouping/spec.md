## Requirements

### Requirement: Conversions page groups estimates by fiscal month
The Conversions page month-level grouping SHALL use the fiscal calendar system (Thursday-belongs rule), where each ISO week is assigned to the calendar month containing its Thursday. All estimates within the same ISO week SHALL appear under the same month header, regardless of their individual calendar date.

#### Scenario: Estimate on a calendar month boundary lands in correct fiscal month
- **WHEN** an estimate was created on Mar 30, 2026 (ISO week W14, Thursday Apr 2 -> fiscal April)
- **THEN** the estimate appears under the "April 2026" month group in the Conversions page

#### Scenario: All estimates in the same ISO week share a month group
- **WHEN** estimates exist on both Mar 30 and Apr 5, 2026 (both in W14/2026)
- **THEN** both estimates appear under the same "April 2026" month group (not split between March and April)

#### Scenario: Mid-month estimates are unaffected
- **WHEN** an estimate was created on Apr 15, 2026 (W16, Thursday Apr 16 -> fiscal April)
- **THEN** the estimate appears under "April 2026", same as before the change

#### Scenario: Fiscal year boundary is respected
- **WHEN** an estimate was created in the first ISO week of a fiscal year (e.g., Jan 4, 2026 = W1/2026, Thursday Jan 8 -> fiscal January 2026)
- **THEN** the estimate appears under "January 2026" using the fiscal year (2026), not the calendar year of the raw date

### Requirement: Month sort keys encode fiscal identity
The month group sort keys used for ordering month sections SHALL encode the fiscal year and fiscal month (not the raw calendar date), ensuring that boundary weeks sort into the correct month order and that the same month key is shared by all estimates in weeks belonging to that fiscal month.

#### Scenario: Estimates from the same fiscal month sort together
- **WHEN** two estimates exist — one on Mar 30 (W14, fiscal April) and one on Apr 15 (W16, fiscal April)
- **THEN** both use the same month sort key and appear in the same "April 2026" section

#### Scenario: Month sections sort newest-first
- **WHEN** the Conversions page renders month groups
- **THEN** April 2026 appears before March 2026 (descending fiscal month order)