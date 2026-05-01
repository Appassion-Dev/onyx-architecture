## MODIFIED Requirements

### Requirement: Pipeline table with estimate-per-row layout
The conversions page SHALL display a table where each row represents one estimate. In all modes except Pre-discovery, the row includes a pipeline cell (single upload action for the active stage) and a value cell. In Pre-discovery mode, the row displays only the estimate label and attribution badges with no pipeline or value column.

#### Scenario: Estimate row in Qualified mode
- **WHEN** the active mode is Qualified and an estimate has a qualified stage
- **THEN** the row SHALL show the estimate label, customer name, a single Qualified `PhaseCell`, and the formatted `qualified_value`

#### Scenario: Estimate row in Converted mode
- **WHEN** the active mode is Converted and an estimate has a converted stage
- **THEN** the row SHALL show the estimate label, customer name, a single Converted `PhaseCell`, and the formatted `converted_value`

#### Scenario: Estimate row in Booking mode
- **WHEN** the active mode is Booking and an estimate has a booking stage
- **THEN** the row SHALL show the estimate label, customer name, a single Booking `PhaseCell`, and a `—` dash in the value position

#### Scenario: Estimate row in Pre-discovery mode
- **WHEN** the active mode is Pre-discovery
- **THEN** the row SHALL show only the estimate label, customer name, GCLID count badge, and `first_touch_medium` badge (no pipeline cell, no value cell)

### Requirement: Pipeline column shows single stage cell per mode
The pipeline column SHALL render exactly one `PhaseCell` for the active conversion mode's stage. The three-cell `PipelineStrip` is replaced by a single contextual cell.

#### Scenario: Only one cell rendered per row
- **WHEN** any mode other than Pre-discovery is active
- **THEN** each table row SHALL contain exactly one `PhaseCell` (not three)

#### Scenario: No cell in Pre-discovery
- **WHEN** the active mode is Pre-discovery
- **THEN** no `PhaseCell` is rendered

### Requirement: Month and week collapsible grouping
The table SHALL group pipeline rows by month (descending) and week (descending), each collapsible. The date field used for grouping is determined by the active conversion mode (see `conversions-fiscal-grouping` spec).

#### Scenario: Month header with rollup
- **WHEN** a month group is rendered in Qualified or Converted mode
- **THEN** the header SHALL show the month label, total estimate count, and total mode-appropriate value sum

#### Scenario: Month header with no value
- **WHEN** a month group is rendered in Pre-discovery or Booking mode
- **THEN** the header SHALL show the month label and total estimate count only (no value)

#### Scenario: Week header with rollup
- **WHEN** a week group is rendered in Qualified or Converted mode
- **THEN** the header SHALL show the week label, estimate count, and mode-appropriate value sum

### Requirement: Expandable detail rows
Clicking a pipeline row SHALL expand an inline detail panel. The section for the **active mode's stage** SHALL be rendered expanded. All other sections SHALL be rendered collapsed (summary row only). All three sections are always present in the DOM for cross-reference.

#### Scenario: Expanded row in Qualified mode
- **WHEN** the active mode is Qualified and a row is expanded
- **THEN** the Qualified Lead section SHALL be fully expanded
- **AND** the Booking Lead and Converted Lead sections SHALL be collapsed to summary rows

#### Scenario: Expanded row in Booking mode
- **WHEN** the active mode is Booking and a row is expanded
- **THEN** the Booking Lead section SHALL be fully expanded
- **AND** the Qualified Lead and Converted Lead sections SHALL be collapsed to summary rows

#### Scenario: Expanded row in Converted mode
- **WHEN** the active mode is Converted and a row is expanded
- **THEN** the Converted Lead section SHALL be fully expanded
- **AND** the Booking Lead and Qualified Lead sections SHALL be collapsed to summary rows

#### Scenario: Stages that do not exist show dash in collapsed summary
- **WHEN** a row is expanded and the estimate has no converted_lead stage
- **THEN** the Converted Lead collapsed summary SHALL show a `—` dash (no status badge)

### Requirement: Qualified stage cell displays estimate work_status
The qualified stage `PhaseCell` SHALL display the estimate's raw `work_status` string as a sub-label beneath the status icon when the active mode is Qualified.

#### Scenario: Qualified cell with complete work_status
- **WHEN** the active mode is Qualified and the estimate has `work_status = 'complete rated'`
- **THEN** the qualified stage cell SHALL render "complete rated" as a sub-label beneath the status icon

#### Scenario: Qualified cell with null work_status
- **WHEN** `estimate_work_status` is NULL
- **THEN** no sub-label is rendered in the qualified cell
