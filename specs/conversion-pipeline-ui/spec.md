## Requirements

### Requirement: Pipeline table with estimate-per-row layout
The conversions page SHALL display a table where each row represents one estimate, with columns: Est#, Customer, Source, Job#, Value, Booking (sync icon), Qualified (sync icon), Converted (sync icon), Closed (icon).

#### Scenario: Estimate row with full pipeline
- **WHEN** an estimate has all three stages (booking uploaded, qualified uploaded, converted pending)
- **THEN** the row SHALL show the estimate number, customer name, booking source, job number, display value, a green CheckCircle2 for Booking, a green CheckCircle2 for Qualified, an amber Clock for Converted, and an unchecked Square for Closed

#### Scenario: Estimate row with partial pipeline
- **WHEN** an estimate has only a booking_lead stage (pending, no attempts)
- **THEN** the row SHALL show an amber Clock for Booking, a text dash for Qualified, a text dash for Converted, and an unchecked Square for Closed

#### Scenario: Estimate row that is closed
- **WHEN** all existing stages for an estimate are uploaded or skipped
- **THEN** the row SHALL show a green CheckSquare icon in the Closed column

### Requirement: Sync status icons use Lucide components
Each pipeline cell SHALL render a Lucide icon based on the stage status.

#### Scenario: Uploaded status
- **WHEN** a stage has `status = 'uploaded'`
- **THEN** the cell SHALL render a `CheckCircle2` icon in green (#01b574)

#### Scenario: Pending status with no attempts
- **WHEN** a stage has `status = 'pending'` and `upload_attempts = 0`
- **THEN** the cell SHALL render a `Clock` icon in amber (#ffb547)

#### Scenario: Pending status with upload attempts (error)
- **WHEN** a stage has `status = 'pending'` and `upload_attempts > 0`
- **THEN** the cell SHALL render an `XCircle` icon in red (#ee5d50)

#### Scenario: Skipped status
- **WHEN** a stage has `status = 'skipped'`
- **THEN** the cell SHALL render a `MinusCircle` icon in gray (#a3aed0)

#### Scenario: Stage does not exist
- **WHEN** a stage has NULL status (no conversion row exists)
- **THEN** the cell SHALL render a text dash (—) in gray (#a3aed0)

### Requirement: Month and week collapsible grouping
The table SHALL group pipeline rows by month (descending) and week (descending), each collapsible. Grouping is based on `estimate_created_at`.

#### Scenario: Month header with rollup
- **WHEN** a month group is rendered
- **THEN** the header SHALL show the month label, total estimate count, and total display value sum

#### Scenario: Week header with rollup
- **WHEN** a week group is rendered
- **THEN** the header SHALL show the week label (e.g., "W16 Apr 13 – Apr 19"), estimate count, and total display value sum

### Requirement: Expandable detail rows
Clicking a pipeline row SHALL expand an inline detail panel showing per-stage information.

#### Scenario: Expanded row with booking stage
- **WHEN** a row is expanded and the estimate has a booking_lead stage
- **THEN** the detail panel SHALL show a Booking Lead section with: source label, GCLID value, upload status, uploaded timestamp, and error message (if any)

#### Scenario: Expanded row with qualified stage
- **WHEN** a row is expanded and the estimate has a qualified_lead stage
- **THEN** the detail panel SHALL show a Qualified Lead section with: per-stage value, GCLID, upload status, uploaded timestamp, and upload attempts

#### Scenario: Expanded row with converted stage
- **WHEN** a row is expanded and the estimate has a converted_lead stage
- **THEN** the detail panel SHALL show a Converted Lead section with: job invoice number, per-stage value, GCLID, upload status, uploaded timestamp

#### Scenario: Stages that do not exist are not shown in detail
- **WHEN** a row is expanded and the estimate has no qualified_lead stage
- **THEN** the detail panel SHALL NOT render a Qualified Lead section

### Requirement: Source column displays booking origin
The table SHALL display a Source column showing how the estimate was booked.

#### Scenario: Form source
- **WHEN** `booking_source = 'form'`
- **THEN** the Source cell SHALL display "Form"

#### Scenario: Call source
- **WHEN** `booking_source = 'call'`
- **THEN** the Source cell SHALL display "Call"

#### Scenario: Unknown source
- **WHEN** `booking_source` is NULL
- **THEN** the Source cell SHALL display a dash (—)

### Requirement: Qualified stage cell displays estimate work_status
The qualified stage cell in the pipeline strip SHALL display the estimate's raw `work_status` string as a sub-label beneath the status icon. The value is shown as-is (no condensing or mapping). This applies to both discovered and undiscovered qualified stages.

#### Scenario: Qualified cell with complete work_status
- **WHEN** the estimate has `work_status = 'complete rated'`
- **THEN** the qualified stage cell SHALL render "complete rated" as a sub-label beneath the status icon

#### Scenario: Qualified cell with null work_status
- **WHEN** `estimate_work_status` is NULL
- **THEN** no sub-label is rendered in the qualified cell

### Requirement: Action buttons preserved
The page header SHALL retain the Scan Now, Upload Pending, Settings, and Refresh buttons with existing behavior.

#### Scenario: Scan Now triggers discovery
- **WHEN** the user clicks Scan Now
- **THEN** the system SHALL call `discover_pending_conversions()` RPC, show a toast with results, and refresh the table

#### Scenario: Upload Pending triggers upload
- **WHEN** the user clicks Upload Pending
- **THEN** the system SHALL invoke the `google-ads-conversion-upload` edge function, show a toast with results, and refresh the table