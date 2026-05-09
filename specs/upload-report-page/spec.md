## ADDED Requirements

### Requirement: Upload report page exists with per-conversion-type tabs
The system SHALL provide an Upload Report page accessible from the Conversions section. The page SHALL display three tabs: Booking Leads, Qualified Leads, and Converted Leads, each corresponding to a distinct Google Ads conversion action.

#### Scenario: User opens Upload Report page
- **WHEN** the user navigates to the Upload Report page
- **THEN** three tabs are displayed: Booking Leads, Qualified Leads, Converted Leads
- **AND** the first tab (Booking Leads) is selected by default

#### Scenario: User switches conversion type tab
- **WHEN** the user clicks a different tab
- **THEN** the table content updates to show data for that conversion type only

### Requirement: Weekly/monthly hierarchy with aggregate header stats
The page SHALL display uploaded records grouped first by calendar month, then by ISO week within each month. Month and week rows SHALL be collapsible. Each month and week header row SHALL display aggregate stats: total uploaded count, count with a Google Click ID (gclid), Google-confirmed received count, Google-confirmed failed count, and conversion amount.

#### Scenario: Month row collapsed by default
- **WHEN** the page loads
- **THEN** month rows are collapsed and only the month headers with their aggregate stats are visible

#### Scenario: User expands a week row
- **WHEN** the user clicks a week header row
- **THEN** the per-source breakdown rows for that week appear below the header

#### Scenario: Stats shown in week/month headers
- **WHEN** a month or week header is visible
- **THEN** the header displays: uploaded count, gclid count, Google received (✓), Google failed (✗), and amount
- **AND** the Google received/failed values are derived from `google_successful_count` and `google_failed_count` in the daily view, summed over all days in the period

### Requirement: Per-source breakdown rows inside expanded weeks
When a week is expanded, the page SHALL display one breakdown row per source bucket: form, calls, thumbtack, and other. Source rows SHALL show local-only stats (uploaded count, gclid count, amount). Google received/failed columns SHALL be blank for source rows.

#### Scenario: Expanded week shows source rows
- **WHEN** the user expands a week
- **THEN** up to four source rows appear: form, calls, thumbtack, other
- **AND** each row shows local uploaded count, gclid count, and amount for that source
- **AND** the Google received and failed columns are blank (—) for all source rows

#### Scenario: Source row with zero records is hidden
- **WHEN** a source bucket has zero uploaded records in a given week
- **THEN** that source row is not shown

### Requirement: Time axis uses uploaded_at date
The page SHALL key all date groupings on `uploaded_at` (the date the record was sent to Google), not on estimate creation date.

#### Scenario: Records grouped by upload date
- **WHEN** the table is rendered
- **THEN** each record appears in the week and month corresponding to its `uploaded_at` date

### Requirement: Amount column behavior per conversion type
The amount column SHALL show the sum of `conversion_value` for the group. For the Booking Leads tab, amount SHALL display as — (no value) since booking events carry no monetary value.

#### Scenario: Amount shown on Qualified and Converted tabs
- **WHEN** the user is on the Qualified Leads or Converted Leads tab
- **THEN** amount displays as a formatted currency value in week and month header rows

#### Scenario: Amount suppressed on Booking tab
- **WHEN** the user is on the Booking Leads tab
- **THEN** the amount column shows — for all rows

### Requirement: Google data freshness label
The page SHALL display the timestamp of the most recent Google health snapshot (`latest_google_synced_at`) so the user understands how current the Google-side counts are.

#### Scenario: Freshness label visible
- **WHEN** the page has loaded data
- **THEN** a label such as "Google data as of [date/time]" is visible near the top of the active tab
