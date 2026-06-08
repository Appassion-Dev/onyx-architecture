## ADDED Requirements

### Requirement: Conversions reporting page
The system SHALL provide a dedicated reporting page inside the Conversions section for aggregated upload reconciliation, separate from the existing Analytics and Uploads pages.

#### Scenario: User opens the reporting page
- **WHEN** an authenticated user navigates to the Conversions reporting destination
- **THEN** they see a page focused on event-first grouped upload reconciliation rather than row-level upload operations or system-health cards

### Requirement: Top-level conversion event grouping
The reporting page SHALL derive its reporting catalog from enabled conversion events in dashboard settings, backed by `gads_conversion_config`, before applying daily or weekly period groupings. With the current seeded configuration, this yields `booking`, `qualified`, and `converted`, but future configured actions SHALL extend the reporting catalog automatically without requiring hardcoded UI changes.

#### Scenario: Seeded config renders current lifecycle tabs
- **WHEN** enabled dashboard settings exist for `booking_lead`, `qualified_lead`, and `converted_lead`
- **THEN** the page renders separate top-level sections for booking, qualified, and converted rather than combining them into one period table

#### Scenario: New configured event extends the reporting catalog automatically
- **WHEN** a new enabled conversion event is added in dashboard settings
- **THEN** the reporting page can resolve local and Google-side rows for that event without requiring a UI code change

#### Scenario: Disabled configured event does not render as active tab
- **WHEN** a conversion event exists in dashboard settings but is not enabled
- **THEN** it is not rendered as an active top-level reporting tab

#### Scenario: Enabled configured event without period data does not render as active tab
- **WHEN** an enabled conversion event has no local uploaded rows and no Google daily-summary rows in the selected reporting period
- **THEN** it is not rendered as an active top-level reporting tab for that period

#### Scenario: Event section can exist with one-sided data
- **WHEN** a configured converted event has Google summary data for a reporting day but no matching local uploaded rows
- **THEN** the converted section still appears and shows the local uploaded count as zero for that day

### Requirement: Reporting page only projects configured actions
The reporting page SHALL only surface Google action summaries that can be joined to enabled dashboard-configured conversion events in `gads_conversion_config`.

#### Scenario: Unconfigured Google action is excluded from reporting
- **WHEN** `gads_action_upload_health` contains a conversion action summary that does not map to an enabled row in `gads_conversion_config`
- **THEN** that action is not rendered in the reporting page's event sections or totals

### Requirement: Daily upload reconciliation rows
The system SHALL produce one reconciliation row per reporting day within each top-level event group by joining local uploaded records from `gads_conversion_uploads` with cached Google upload summary data on the same day key. Each row SHALL show the local uploaded total, the Google successful total, and the Google failed total as distinct values.

#### Scenario: Both local and Google data exist for the day
- **WHEN** local uploads total 12 for a reporting day and cached Google daily summaries for that same day contain successful = 10 and failed = 2
- **THEN** the row shows local uploaded = 12, Google successful = 10, and Google failed = 2

#### Scenario: Only one side has data for the day
- **WHEN** a reporting day has local uploaded rows but no cached Google summary rows, or Google summary rows but no local uploaded rows
- **THEN** the row still appears for that day with any missing uploaded, successful, or failed value rendered as zero

#### Scenario: Google summary only includes failures
- **WHEN** a daily summary entry exists for a reporting day with `failedCount` present and no `successfulCount`
- **THEN** the row shows the Google successful value as zero and the Google failed value from the stored summary

### Requirement: Aggregate reconciliation language
The reporting page SHALL present its counts as aggregate reconciliation and MUST NOT claim that the joined day or week totals prove acceptance or attribution for a specific local upload row.

#### Scenario: User inspects a mismatched day
- **WHEN** a reporting day shows different local uploaded, Google successful, or Google failed counts
- **THEN** the page labels the comparison as a grouped reconciliation result rather than describing individual rows as definitively accepted or rejected by Google

### Requirement: Weekly rollups with prior-period comparison
The system SHALL aggregate daily reconciliation rows into weekly rollups within each top-level event group and SHALL compare each displayed period to its immediately preceding equivalent period.

#### Scenario: Day row compares to previous day
- **WHEN** a daily row is rendered for April 20
- **THEN** the page also shows the change relative to April 19 using the same displayed metrics

#### Scenario: Week row compares to previous week
- **WHEN** a weekly rollup is rendered for the current week
- **THEN** the page also shows the change relative to the immediately preceding week using the same displayed metrics

### Requirement: Exclusive local source buckets
The system SHALL classify every local uploaded row into exactly one reporting bucket: `form`, `calls`, `thumbtack`, or `other`. The displayed bucket subtotals SHALL add up to the local uploaded total for the same day or week.

#### Scenario: Form row with call history remains a form upload
- **WHEN** an uploaded row has booking-form signals and also has correlated calls
- **THEN** the row is counted once in the `form` bucket and not double-counted in `calls`

#### Scenario: Thumbtack signal overrides other source signals
- **WHEN** an uploaded row has an explicit Thumbtack source signal alongside other local source signals
- **THEN** the row is counted once in the `thumbtack` bucket

#### Scenario: Unclassified row falls back to other
- **WHEN** an uploaded row has no qualifying booking, call, or Thumbtack signal
- **THEN** the row is counted once in the `other` bucket

### Requirement: Backlog metrics separate from dated reconciliation
The system SHALL summarize current pending, retrying, and skipped rows separately from dated reconciliation totals when those rows do not have an upload date that matches the reporting grain.

#### Scenario: Pending row without upload timestamp
- **WHEN** a conversion upload row is still pending and has no `uploaded_at` value
- **THEN** it contributes to the backlog summary and does not appear inside a dated daily reconciliation row

### Requirement: Reporting page uses stored snapshot data
The reporting page SHALL render from stored Supabase data and SHALL NOT require live Google Ads queries during page load.

#### Scenario: Cached analytics exist
- **WHEN** the latest upload-health snapshots and local upload rows are already stored in Supabase
- **THEN** the reporting page loads its reconciliation data from those stored records without making a live Google Ads request

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