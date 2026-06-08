## ADDED Requirements

### Requirement: Reconciliation day key uses the configured account timezone

`vw_gads_upload_reconciliation_daily` SHALL compute its `reporting_date` by converting `uploaded_at` into the account timezone returned by `gads_account_timezone()`, rather than a hardcoded timezone literal. `gads_account_timezone()` SHALL be the single SQL-side source for the account timezone and SHALL return `America/New_York` by default, keeping the view's output unchanged for the current deployment.

#### Scenario: Day key computed in the account timezone
- **WHEN** a local uploaded row has an `uploaded_at` instant that falls on different calendar days in UTC versus the account timezone
- **THEN** its `reporting_date` SHALL be the calendar day in the account timezone returned by `gads_account_timezone()`, not the UTC calendar day

#### Scenario: Default timezone preserves current output
- **WHEN** `gads_account_timezone()` returns its default `America/New_York`
- **THEN** every `reporting_date` SHALL equal the value the prior hardcoded `timezone('America/New_York', uploaded_at)` expression produced for the same rows

#### Scenario: Single source for the SQL-side timezone
- **WHEN** the reconciliation view is recreated
- **THEN** it SHALL reference `gads_account_timezone()` and SHALL NOT contain a hardcoded `America/New_York` timezone literal
