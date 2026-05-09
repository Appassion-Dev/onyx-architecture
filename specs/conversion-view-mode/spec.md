## ADDED Requirements

### Requirement: Conversion mode drives page context
The Conversions page SHALL operate in one of four conversion modes: `pre-discovery`, `booking`, `qualified`, or `converted`. The active mode SHALL determine the date field used for hierarchy grouping, the value field displayed per row and in rollups, the upload cell rendered in the pipeline column, and the primary section in the expanded detail panel.

#### Scenario: Default mode on page load
- **WHEN** the Conversions page loads for the first time in a session
- **THEN** the active conversion mode SHALL be `qualified`

#### Scenario: Mode controls hierarchy date field
- **WHEN** the active mode is `pre-discovery`
- **THEN** estimates SHALL be grouped by `estimate_created_at`
- **WHEN** the active mode is `booking`
- **THEN** estimates SHALL be grouped by `booking_datetime`
- **WHEN** the active mode is `qualified`
- **THEN** estimates SHALL be grouped by `qualified_datetime`
- **WHEN** the active mode is `converted`
- **THEN** estimates SHALL be grouped by `converted_datetime`

#### Scenario: Mode controls value field
- **WHEN** the active mode is `pre-discovery` or `booking`
- **THEN** the Value column SHALL display `—` for all rows
- **WHEN** the active mode is `qualified`
- **THEN** the Value column SHALL display `qualified_value` for each row
- **WHEN** the active mode is `converted`
- **THEN** the Value column SHALL display `converted_value` for each row

#### Scenario: Mode controls upload cell
- **WHEN** the active mode is `pre-discovery`
- **THEN** no upload cell is rendered in the pipeline column
- **WHEN** the active mode is `booking`
- **THEN** only the `booking_lead` PhaseCell is rendered in the pipeline column
- **WHEN** the active mode is `qualified`
- **THEN** only the `qualified_lead` PhaseCell is rendered in the pipeline column
- **WHEN** the active mode is `converted`
- **THEN** only the `converted_lead` PhaseCell is rendered in the pipeline column

#### Scenario: Mode controls detail panel primary section
- **WHEN** the active mode is `booking` and a row is expanded
- **THEN** the Booking Lead section SHALL be expanded and the Qualified and Converted sections SHALL be collapsed
- **WHEN** the active mode is `qualified` and a row is expanded
- **THEN** the Qualified Lead section SHALL be expanded and the Booking and Converted sections SHALL be collapsed
- **WHEN** the active mode is `converted` and a row is expanded
- **THEN** the Converted Lead section SHALL be expanded and the Booking and Qualified sections SHALL be collapsed
- **WHEN** the active mode is `pre-discovery` and a row is expanded
- **THEN** the Booking Lead section SHALL be expanded (as it is the attribution source) and other sections SHALL be collapsed

### Requirement: Collapsed detail section shows summary row
When a StageDetail section is collapsed, it SHALL render a single summary row showing the stage label and status badge. If the stage has a value (qualified or converted), the value SHALL also be shown in the summary row. If the stage has no record (status NULL), the summary row shows a dash.

#### Scenario: Collapsed section with uploaded status
- **WHEN** a StageDetail section is collapsed and the stage status is `uploaded`
- **THEN** the summary row SHALL show the stage label and a green `CheckCircle2` badge

#### Scenario: Collapsed section with pending status
- **WHEN** a StageDetail section is collapsed and the stage status is `pending`
- **THEN** the summary row SHALL show the stage label and an amber `Clock` badge

#### Scenario: Collapsed section with no record
- **WHEN** a StageDetail section is collapsed and the stage has no record (status NULL)
- **THEN** the summary row SHALL show the stage label and a `—` dash

#### Scenario: Collapsed qualified section shows value
- **WHEN** the Qualified Lead section is collapsed and `qualified_value > 0`
- **THEN** the summary row SHALL also display the formatted `qualified_value`

#### Scenario: Collapsed converted section shows value
- **WHEN** the Converted Lead section is collapsed and `converted_value > 0`
- **THEN** the summary row SHALL also display the formatted `converted_value`

### Requirement: Pre-discovery mode shows simplified row layout
In `pre-discovery` mode, the pipeline column and value column SHALL be hidden. The row SHALL display only the estimate label and source/medium attribution badges.

#### Scenario: Pre-discovery row layout
- **WHEN** the active mode is `pre-discovery`
- **THEN** each table row SHALL render without a pipeline column and without a value column
- **AND** the estimate name, customer name, GCLID count badge, and `first_touch_medium` badge SHALL remain visible
