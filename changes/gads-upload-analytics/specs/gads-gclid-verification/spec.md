## ADDED Requirements

### Requirement: On-demand GCLID verification
The system SHALL provide an operator-facing workflow that verifies a captured GCLID against Google Ads click data using an exact click date.

#### Scenario: Verification finds matching click data
- **WHEN** an operator submits a GCLID with a valid click date inside Google Ads retention limits
- **THEN** the system SHALL query `click_view` for that exact date and GCLID
- **THEN** it SHALL return whether click data was found along with contextual campaign, ad group, keyword, device, and date fields when available

### Requirement: Verification enforces Google Ads query limits
The system SHALL require a single click date for GCLID verification and SHALL reject verification requests that do not comply with current `click_view` limits.

#### Scenario: Click date is missing
- **WHEN** an operator requests GCLID verification without providing a click date
- **THEN** the system SHALL reject the request before issuing a Google Ads query

#### Scenario: Click date is outside the supported window
- **WHEN** an operator requests verification for a click date older than the supported `click_view` retention window
- **THEN** the system SHALL return a constrained diagnostic response instead of issuing an unsupported bulk lookup

### Requirement: Verification is separate from daily analytics sync
The system SHALL keep GCLID verification out of the scheduled daily upload analytics collector.

#### Scenario: Daily analytics sync runs
- **WHEN** the scheduled upload analytics job executes
- **THEN** it SHALL NOT issue `click_view` queries for individual GCLIDs

### Requirement: Missing click data is explicit
The system SHALL report a no-match diagnostic when Google Ads returns no click rows for a verification request.

#### Scenario: Verification returns no rows
- **WHEN** Google Ads returns zero `click_view` rows for the requested GCLID and click date
- **THEN** the system SHALL return an explicit no-match result instead of treating the request as an internal failure