## Requirements

### Requirement: Pipeline table row layout
The conversions page SHALL display a table whose row unit depends on the active mode. In single-stage modes (`pre-discovery`, `booking`, `qualified`, `converted`) each row represents one estimate. In `all` mode each row represents one `StageEvent` — a `(estimate, stage)` pair — so a single estimate that has all three stages discovered appears up to three times in the visible list, once per stage. In all modes except Pre-discovery, the row includes an inline value cell rendered without a card container or border. The row layout SHALL NOT include a per-row upload card or PhaseCell — per-row upload is reachable only through the expanded StageDetail panel.

#### Scenario: Estimate row in Qualified mode
- **WHEN** the active mode is `qualified` and an estimate has a qualified stage
- **THEN** the row SHALL show the HCP-linked estimate label, customer name, and the formatted `qualified_value` rendered inline (no card container)

#### Scenario: Estimate row in Converted mode
- **WHEN** the active mode is `converted` and an estimate has a converted stage
- **THEN** the row SHALL show the HCP-linked estimate label, customer name, and the formatted `converted_value` rendered inline (no card container)

#### Scenario: Estimate row in Booking mode
- **WHEN** the active mode is `booking` and an estimate has a booking stage
- **THEN** the row SHALL show the HCP-linked estimate label, customer name, and a `—` dash in the inline value position

#### Scenario: StageEvent row in All mode — single stage per row
- **WHEN** the active mode is `all` and an estimate has booking_status, qualified_status, and converted_status all non-null
- **THEN** the visible list SHALL contain three separate rows for that estimate — one labeled `Booked` and dated by `booking_datetime`, one labeled `Qualified` and dated by `qualified_datetime`, one labeled `Won` (converted) and dated by `converted_datetime`
- **AND** each row SHALL show the HCP-linked estimate label, customer name, a stage badge identifying which stage event this row represents, and an inline single-valued Value cell matching that stage (`—` for booking, `qualified_value` for qualified, `converted_value` for converted)

#### Scenario: StageEvent row in All mode — partial stages
- **WHEN** the active mode is `all` and an estimate has only `booking_status` non-null (no qualified or converted yet)
- **THEN** the visible list SHALL contain exactly one row for that estimate, labeled `Booked`, dated by `booking_datetime`, with an inline value of `—`

#### Scenario: Estimate row in Pre-discovery mode
- **WHEN** the active mode is `pre-discovery`
- **THEN** the row SHALL show only the HCP-linked estimate label, customer name, GCLID count badge, and `first_touch_medium` badge (no value cell)

### Requirement: Month and week collapsible grouping
The table SHALL group pipeline rows by month (descending) and week (descending), each collapsible. The date field used for grouping is determined by the active conversion mode (see `conversion-view-mode` and `conversions-fiscal-grouping` specs).

#### Scenario: Month header with rollup
- **WHEN** a month group is rendered in any mode
- **THEN** the header SHALL show the month label, plus the five-column rollup rail (Stage, Method, Push, Acceptance, Value) per the `rollup-metric-columns` and `rollup-acceptance-metric` capabilities

#### Scenario: Week header with rollup
- **WHEN** a week group is rendered in any mode
- **THEN** the header SHALL show the week label, plus the five-column rollup rail

### Requirement: Expandable detail rows
Clicking a pipeline row SHALL expand an inline detail panel. The panel SHALL include a CustomerInfoBlock at the top per the `pipeline-row-hcp-link` capability, followed by the three StageDetail sections. The StageDetail expansion behavior depends on the active mode:
- In a single-stage mode (`booking`, `qualified`, `converted`), the corresponding stage SHALL be expanded and the other two SHALL be collapsed (summary row only).
- In `pre-discovery` mode, the Booking Lead section SHALL be expanded and the others collapsed.
- In `all` mode, all three StageDetail sections SHALL be expanded in parallel.

#### Scenario: Expanded row in Qualified mode
- **WHEN** the active mode is `qualified` and a row is expanded
- **THEN** the CustomerInfoBlock SHALL render at the top
- **AND** the Qualified Lead section SHALL be fully expanded
- **AND** the Booking Lead and Converted Lead sections SHALL be collapsed to summary rows

#### Scenario: Expanded row in Booking mode
- **WHEN** the active mode is `booking` and a row is expanded
- **THEN** the Booking Lead section SHALL be fully expanded
- **AND** the Qualified Lead and Converted Lead sections SHALL be collapsed to summary rows

#### Scenario: Expanded row in Converted mode
- **WHEN** the active mode is `converted` and a row is expanded
- **THEN** the Converted Lead section SHALL be fully expanded
- **AND** the Booking Lead and Qualified Lead sections SHALL be collapsed to summary rows

#### Scenario: Expanded row in All mode is single-stage
- **WHEN** the active mode is `all` and a `StageEvent` row is expanded
- **THEN** ONLY the StageDetail section corresponding to the row's stage SHALL be rendered (fully expanded), preceded by the CustomerInfoBlock — the other two stages' sections SHALL NOT be rendered (no full section, no collapsed summary)
- **AND** the rendered StageDetail SHALL show that stage's status, GCLID, value, datetime, error message, and any other stage-specific evidence (BookingTagsTable / CallHistoryTable / EstimateOptionsTable / JobDetailSection) appropriate to the stage
- **AND** expansion state SHALL be tracked independently per appearance: expanding the `Booked` row for an estimate does NOT auto-expand the `Qualified` or `Won` rows for the same estimate

#### Scenario: All mode rows are independent records
- **WHEN** the active mode is `all` and a single estimate has more than one stage discovered
- **THEN** the visible list SHALL contain one independent row per discovered stage — no parent grouping, no aggregation header
- **AND** each row SHALL be sortable, filterable, and selectable on its own without affecting the other appearances of the same underlying estimate

#### Scenario: Stages that do not exist show dash in collapsed summary
- **WHEN** a row is expanded and the estimate has no `converted_lead` stage
- **THEN** the Converted Lead collapsed summary SHALL show a `—` dash (no status badge)

### Requirement: Qualified stage cell displays estimate work_status
The qualified stage `PhaseCell`, when rendered inside the expanded StageDetail panel, SHALL display the estimate's raw `work_status` string as a sub-label beneath the status icon.

#### Scenario: Qualified cell with complete work_status
- **WHEN** a Qualified Lead PhaseCell is rendered in the expanded detail panel and the estimate has `work_status = 'complete rated'`
- **THEN** the qualified stage cell SHALL render "complete rated" as a sub-label beneath the status icon

#### Scenario: Qualified cell with null work_status
- **WHEN** `estimate_work_status` is NULL
- **THEN** no sub-label is rendered in the qualified cell
