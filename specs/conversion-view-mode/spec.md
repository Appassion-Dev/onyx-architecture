## Requirements

### Requirement: Conversion mode drives page context
The Conversions page SHALL operate in one of five conversion modes: `all`, `pre-discovery`, `booking`, `qualified`, or `converted`. The active mode SHALL determine the leaf entity flowing through the hierarchy and the date used for its bucketization, the value field displayed per row and in rollups, the upload cells available in the expanded detail panel, and the primary section in the expanded detail panel. The `all` mode SHALL aggregate booking, qualified, and converted stages simultaneously in the rollup rails per the `rollup-metric-columns` capability, using per-stage event dates (NOT a unified `estimate_created_at`) for bucketization.

The internal mode value `all` SHALL be rendered in the tab strip with the display label `All Conv` (short for "All Conversions"), distinguishing it from a generic "All" and signaling that the tab aggregates only the three conversion stages, not pre-discovery. The tab strip SHALL render modes in this order: `Pre-Discovery`, `All Conv`, `Booking`, `Qualified`, `Converted`. `All Conv` SHALL occupy the second position.

#### Scenario: Default mode on page load
- **WHEN** the Conversions page loads for the first time in a session
- **THEN** the active conversion mode SHALL be `all` (label `All Conv`)

#### Scenario: Tab strip order
- **WHEN** the conversion mode tab strip is rendered
- **THEN** the tabs SHALL appear in this order: `Pre-Discovery`, `All Conv`, `Booking`, `Qualified`, `Converted`
- **AND** `All Conv` SHALL be the second tab

#### Scenario: Single-stage modes group estimates by that stage's datetime
- **WHEN** the active mode is `pre-discovery`
- **THEN** the leaf entity is a `PipelineRow` per estimate grouped by `estimate_created_at`
- **WHEN** the active mode is `booking`
- **THEN** the leaf entity is a `PipelineRow` per estimate grouped by `booking_datetime`
- **WHEN** the active mode is `qualified`
- **THEN** the leaf entity is a `PipelineRow` per estimate grouped by `qualified_datetime`
- **WHEN** the active mode is `converted`
- **THEN** the leaf entity is a `PipelineRow` per estimate grouped by `converted_datetime`

#### Scenario: All mode uses per-stage event dates
- **WHEN** the active mode is `all`
- **THEN** each `PipelineRow` SHALL emit one `StageEvent` per stage whose `{stage}_status` is non-null, where `{stage}` is exactly one of `booking`, `qualified`, or `converted` (0–3 events per row); pre-discovery is NOT a stage in `all` mode and NEVER emits a `StageEvent`
- **AND** each `StageEvent` SHALL carry that stage's `{stage}_datetime` as its `eventDate`
- **AND** the hierarchy SHALL bucket `StageEvent`s by `eventDate` into Month → Week
- **AND** the table body SHALL render one visible row per `StageEvent` (a single estimate that has all three stages discovered therefore appears up to three times — once per stage — each in the period that stage's `{stage}_datetime` falls in)
- **AND** each `StageEvent` row SHALL display a small stage badge labeling it as `Booked`, `Qualified`, or `Won` (never `Pre-discovery`)
- **AND** rollup totals (`Stage`, `Method`, `Push`, `Value`) at Month / Week / SourceGroup levels SHALL equal the count of `StageEvent`s in that bucket so that visible-row counts and rail totals are tautologically consistent
- **AND** an estimate whose stages span different weeks SHALL contribute one event each to those different weeks (e.g. booked in W1, qualified in W3, converted in W7 → one row in each of W1's booking column, W3's qualified column, W7's converted column)

#### Scenario: Pre-discovery rows are excluded from All mode
- **WHEN** the active mode is `all` and a `PipelineRow` has `booking_status`, `qualified_status`, AND `converted_status` all NULL (the pre-discovery condition)
- **THEN** that row SHALL emit zero `StageEvent`s
- **AND** that row SHALL NOT appear anywhere in the visible `all`-mode hierarchy
- **AND** that row SHALL NOT contribute to any Stage / Method / Push / Acceptance / Value rollup total in `all` mode

#### Scenario: Acceptance event keys are limited to the three uploadable stages
- **WHEN** the active mode is `all` and the page fetches reconciliation data for the Acceptance column
- **THEN** the request SHALL include `event_key IN ('booking_lead', 'qualified_lead', 'converted_lead')` only
- **AND** the Acceptance cell SHALL display three sub-values one per stage in booking → qualified → converted order (no pre-discovery sub-value)

#### Scenario: All mode StageEvent expansion is single-stage scoped
- **WHEN** the active mode is `all` and the user expands a `StageEvent` row labeled `Booked`
- **THEN** the expanded detail panel SHALL render the CustomerInfoBlock followed by ONLY the Booking Lead StageDetail section, fully expanded
- **AND** the Qualified Lead and Converted Lead StageDetail sections SHALL NOT be rendered (not as full sections, not as collapsed summary rows)
- **WHEN** the active mode is `all` and the user expands a `StageEvent` row labeled `Qualified`
- **THEN** the expanded detail panel SHALL render the CustomerInfoBlock followed by ONLY the Qualified Lead StageDetail section, fully expanded
- **AND** the Booking Lead and Converted Lead sections SHALL NOT be rendered
- **WHEN** the active mode is `all` and the user expands a `StageEvent` row labeled `Won` (converted)
- **THEN** the expanded detail panel SHALL render the CustomerInfoBlock followed by ONLY the Converted Lead StageDetail section, fully expanded
- **AND** the Booking Lead and Qualified Lead sections SHALL NOT be rendered
- **AND** expansion state SHALL be tracked independently per `StageEvent` appearance — expanding the `Booked` row for an estimate has no effect on the `Qualified` or `Won` rows for the same estimate

#### Scenario: All mode rows are not grouped by parent estimate
- **WHEN** the active mode is `all` and a single estimate has produced `Booked`, `Qualified`, AND `Won` events
- **THEN** the visible list SHALL contain three completely independent rows for that estimate — one per `StageEvent` — each ordered into the period its own `*_datetime` falls in
- **AND** the rows SHALL NOT be grouped, nested, or aggregated under any "parent estimate" wrapper
- **AND** the rows MAY appear in entirely different Month groups, Week groups, or SourceGroups depending on where each stage's event date lands
- **AND** the Stage / Method / Push / Value rollup totals SHALL count each `StageEvent` exactly once (no de-duplication by `estimate_id`) so that one estimate that progressed through all three stages contributes `+1` to each of the three stage columns of the rollup levels containing its events

#### Scenario: Mode controls value field — rollup level
- **WHEN** the active mode is `all`
- **THEN** the rollup Value column SHALL display three sub-values: `—` for booking, sum of `qualified_value` over qualified `StageEvent`s in the bucket, sum of `converted_value` over converted `StageEvent`s in the bucket
- **WHEN** the active mode is `pre-discovery` or `booking`
- **THEN** the rollup Value column SHALL display `—`
- **WHEN** the active mode is `qualified`
- **THEN** the rollup Value column SHALL display the sum of `qualified_value` over rows in the bucket
- **WHEN** the active mode is `converted`
- **THEN** the rollup Value column SHALL display the sum of `converted_value` over rows in the bucket

#### Scenario: Mode controls value field — per-row level
- **WHEN** the active mode is `all` and a `StageEvent` row is for the booking stage
- **THEN** the inline Value on that row SHALL display `—`
- **WHEN** the active mode is `all` and a `StageEvent` row is for the qualified stage
- **THEN** the inline Value on that row SHALL display the formatted `qualified_value`
- **WHEN** the active mode is `all` and a `StageEvent` row is for the converted stage
- **THEN** the inline Value on that row SHALL display the formatted `converted_value`
- **WHEN** the active mode is `pre-discovery` or `booking`
- **THEN** the inline per-row Value SHALL display `—`
- **WHEN** the active mode is `qualified`
- **THEN** the inline per-row Value SHALL display the formatted `qualified_value`
- **WHEN** the active mode is `converted`
- **THEN** the inline per-row Value SHALL display the formatted `converted_value`

#### Scenario: Mode controls detail panel primary section
- **WHEN** the active mode is `booking` and a row is expanded
- **THEN** the Booking Lead section SHALL be expanded and the Qualified and Converted sections SHALL be collapsed
- **WHEN** the active mode is `qualified` and a row is expanded
- **THEN** the Qualified Lead section SHALL be expanded and the Booking and Converted sections SHALL be collapsed
- **WHEN** the active mode is `converted` and a row is expanded
- **THEN** the Converted Lead section SHALL be expanded and the Booking and Qualified sections SHALL be collapsed
- **WHEN** the active mode is `pre-discovery` and a row is expanded
- **THEN** the Booking Lead section SHALL be expanded (as it is the attribution source) and other sections SHALL be collapsed
- **WHEN** the active mode is `all` and a `StageEvent` row is expanded
- **THEN** ONLY the StageDetail section matching the row's own stage SHALL be rendered (fully expanded), preceded by the CustomerInfoBlock; the other two stages' sections SHALL NOT be rendered

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
In `pre-discovery` mode, the value column SHALL be hidden. The row SHALL display only the estimate label (HCP-linked per `pipeline-row-hcp-link`), customer name, and source/medium attribution badges.

#### Scenario: Pre-discovery row layout
- **WHEN** the active mode is `pre-discovery`
- **THEN** each table row SHALL render without a value column
- **AND** the estimate name, customer name, GCLID count badge, and `first_touch_medium` badge SHALL remain visible
