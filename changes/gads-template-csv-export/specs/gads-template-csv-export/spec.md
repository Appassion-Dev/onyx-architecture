## ADDED Requirements

### Requirement: Shared Google Ads template CSV format

The system SHALL produce conversion-upload CSV exports with exactly these columns, in order: `Email`, `Phone Number`, `Conversion Name`, `Conversion Time`, `Conversion Value`, `Conversion Currency`, `Google Click ID`, `JSON Sent`, `JSON Echo`, `Error`. One CSV row SHALL represent one conversion upload (one `(estimate_id, conversion_type)` pair). Email and Phone Number SHALL come from the in-memory pipeline row (`customer_email`, `customer_mobile`); all other columns SHALL come from `vw_gads_upload_payload_slices` for that pair. Cells SHALL be CSV-quoted (embedded `"` doubled) so JSON payloads survive in Excel/Sheets, and JSON SHALL be serialized compactly without pretty-printing.

#### Scenario: Upload row with sent payload and echo
- **WHEN** a row's slice has `request_slice` and `response_results_slice` entries
- **THEN** `JSON Sent` SHALL contain the request entries and `JSON Echo` the response entries, each narrowed to the row's own `conversion_action` per the `gads-upload-payload-slices` narrowing rule

#### Scenario: Pending upload not yet sent
- **WHEN** a visible row's upload exists but has no batch payload yet (`response_slice_kind` is `missing`)
- **THEN** the CSV row SHALL still be emitted with populated conversion columns and blank `JSON Sent` / `JSON Echo`

#### Scenario: Error present
- **WHEN** the row's narrowed `error_slice` is non-empty
- **THEN** the `Error` column SHALL contain the narrowed `error_slice` JSON; otherwise it SHALL contain `error_message` when present, else blank

#### Scenario: Booking conversion without value
- **WHEN** the slice row has a null `conversion_value` (e.g. `booking_lead`)
- **THEN** `Conversion Value` SHALL be blank, not `0`

#### Scenario: User-data-only row without gclid
- **WHEN** the slice row has a null `gclid`
- **THEN** `Google Click ID` SHALL be blank and the row SHALL still be exported

### Requirement: Conversion Name uses live Google Ads action names

The `Conversion Name` column SHALL be resolved at export time from `gads_conversion_config.conversion_action_name` by the row's `conversion_type`. Names SHALL NOT be hardcoded in the export code. When `conversion_action_name` is null, the export SHALL fall back to the raw `conversion_type` value.

#### Scenario: Configured action names
- **WHEN** config maps `booking_lead` → `BOOKING_CONFIRMED`, `qualified_lead` → `Qualified Leads`, `converted_lead` → `Converted Leads`
- **THEN** exported rows SHALL carry those exact strings, including casing

#### Scenario: Unconfigured conversion type
- **WHEN** a conversion type's `conversion_action_name` is null
- **THEN** the `Conversion Name` cell SHALL contain the `conversion_type` value rather than being blank

### Requirement: Month-level and week-level CSV download

Each month header (`MonthRow`) and each week header (`WeekBlock`) on the conversions page SHALL show a CSV download icon that exports that group's uploads pre-filtered to what the group is currently displaying under the active conversion mode: in `all` mode one row per stage event in the group's `events`; in `booking` / `qualified` / `converted` mode one row per entry in the group's `rows` for that stage. In `pre-discovery` mode the icons SHALL NOT be shown. Activating an icon SHALL NOT toggle the group's expansion state (the month header is an expand/collapse toggle). Downloaded files SHALL be named using the group key (`gads-conversions-<monthKey>.csv` / `gads-conversions-<weekKey>.csv`).

#### Scenario: Week export in all mode
- **WHEN** the user clicks a week's CSV icon while mode is `all`
- **THEN** the CSV SHALL contain one row per stage event shown in that week, each with its own stage's conversion name, time, value, gclid, and slices

#### Scenario: Month export covers all its weeks
- **WHEN** the user clicks a month's CSV icon
- **THEN** the CSV SHALL contain exactly the union of the rows/events displayed across that month's weeks under the active mode

#### Scenario: Week export in a single-stage mode
- **WHEN** the user clicks a week's CSV icon while mode is `converted`
- **THEN** the CSV SHALL contain only `converted_lead` rows for that week's displayed rows, and no booking or qualified rows

#### Scenario: Month export click does not toggle expansion
- **WHEN** the user clicks a month's CSV icon while the month is collapsed or expanded
- **THEN** the export SHALL start and the month's expanded state SHALL remain unchanged

#### Scenario: Pre-discovery mode hides the icons
- **WHEN** the conversion mode is `pre-discovery`
- **THEN** neither month nor week headers SHALL render the CSV download icon

### Requirement: Page-level CSV export of the full 90-day window

The conversions page's top-level "Export CSV" action SHALL export every conversion upload of every conversion type for all estimates loaded in the 90-day pipeline window, ignoring the active mode filter and the filter bar. The file SHALL use the shared template format and a window-scoped filename (`gads-conversions-90d.csv`).

#### Scenario: Page export ignores mode filter
- **WHEN** the user triggers the page-level export while mode is `qualified`
- **THEN** the CSV SHALL still include `booking_lead`, `qualified_lead`, and `converted_lead` rows for all estimates in the window

#### Scenario: Page export ignores the filter bar
- **WHEN** filter-bar filters are narrowing the visible hierarchy
- **THEN** the page-level export SHALL still cover all estimates from the unfiltered 90-day pipeline result

### Requirement: Slice fetching is on-demand and chunked

Payload slices SHALL be fetched from `vw_gads_upload_payload_slices` only when an export is triggered, filtered by the scope's estimate ids with `.in()` queries chunked (at most 200 ids per query), and SHALL NOT be loaded as part of the page's pipeline query.

#### Scenario: Large page-level export
- **WHEN** the 90-day window contains more estimates than one chunk
- **THEN** the export SHALL issue sequential chunked queries and concatenate results, producing one complete CSV

#### Scenario: No slices loaded on page load
- **WHEN** the conversions page loads and no export has been triggered
- **THEN** no query against `vw_gads_upload_payload_slices` SHALL be issued by the export feature

### Requirement: Legacy converted-leads export is removed

The `useConvertedLeadsExport` hook and the `export_converted_leads(p_from_date, p_to_date)` RPC SHALL be removed. The page-level "Export CSV" button SHALL invoke the template export instead. A forward migration SHALL drop the RPC function.

#### Scenario: Old RPC no longer exists
- **WHEN** the drop migration has been applied
- **THEN** calling `export_converted_leads` SHALL fail with an undefined-function error and no frontend code SHALL reference it

#### Scenario: Export button produces the template format
- **WHEN** the user clicks the page-level "Export CSV" button after this change
- **THEN** the downloaded file SHALL be in the shared template format, not the legacy ops-column format
