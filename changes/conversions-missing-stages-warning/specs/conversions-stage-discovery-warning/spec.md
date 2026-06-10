## ADDED Requirements

### Requirement: Shared missing-stages resolver follows sequential gap rule
The system SHALL provide a shared helper `getMissingStages(row)` that returns the labels of the conversion stages that are undiscovered but precede a discovered stage. Booking → Qualified → Converted is a strictly sequential process, so an undiscovered stage (status column `null`) SHALL be reported as missing ONLY when a later stage has been discovered (a gap). A trailing undiscovered stage — one with no discovered stage after it — represents normal in-progress flow and SHALL NOT be reported. The helper SHALL return the labels in stage order using the display names `Booking`, `Qualified`, and `Converted`. Both the pipeline row warning and the channel rollup warning SHALL derive from this single helper. Because Converted is the final stage, the helper SHALL return at most two labels.

#### Scenario: All stages discovered
- **WHEN** an estimate has non-null `booking_status`, `qualified_status`, and `converted_status`
- **THEN** `getMissingStages` SHALL return an empty array

#### Scenario: Trailing undiscovered stages are not missing
- **WHEN** an estimate has a non-null `booking_status` but null `qualified_status` and null `converted_status`
- **THEN** `getMissingStages` SHALL return an empty array (normal progression, no gap)

#### Scenario: Earlier stage missing while a later stage exists
- **WHEN** an estimate has null `booking_status` but a non-null `qualified_status`
- **THEN** `getMissingStages` SHALL return `["Booking"]`

#### Scenario: Converted reached but earlier stages skipped
- **WHEN** an estimate has a non-null `converted_status` but null `booking_status` and null `qualified_status`
- **THEN** `getMissingStages` SHALL return `["Booking", "Qualified"]`

### Requirement: Pipeline row warns when an earlier stage is missing
Each `PipelineRowItem` header SHALL display a warning indicator immediately after the customer name whenever `getMissingStages` returns one or more stages for the estimate (an earlier stage is undiscovered while a later stage exists). The indicator SHALL be an orange `AlertTriangle` icon. When `getMissingStages` returns an empty array, no indicator SHALL be rendered.

#### Scenario: Row with a sequential gap shows the warning
- **WHEN** a pipeline row's estimate has an undiscovered stage that precedes a discovered stage
- **THEN** an orange warning triangle SHALL be rendered directly after the customer name

#### Scenario: Row with only trailing undiscovered stages shows no warning
- **WHEN** a pipeline row's estimate has discovered stages with no gap before the latest one (e.g. Booking only, or Booking + Qualified)
- **THEN** no warning indicator SHALL be rendered in the row header

### Requirement: Pipeline row warning shows a color-scaled missing-stage count
The pipeline row warning SHALL display, next to the triangle, the number of missing stages returned by `getMissingStages` (1 or 2). The number SHALL be colored by severity: 1 in yellow (`#f5c518`) and 2 in orange (`#ff8a3d`). A tooltip on the indicator SHALL name the specific missing stages.

#### Scenario: One earlier stage missing
- **WHEN** `getMissingStages` returns exactly one stage
- **THEN** the indicator SHALL show the number `1` in yellow
- **AND** the tooltip SHALL name that stage (e.g. "Missing stages: Booking")

#### Scenario: Two earlier stages missing
- **WHEN** an estimate has a non-null `converted_status` while `booking_status` and `qualified_status` are null
- **THEN** the indicator SHALL show the number `2` in orange
- **AND** the tooltip SHALL read "Missing stages: Booking, Qualified"

### Requirement: Channel rollup warns with total missing conversions
The channel (source-group) rollup header SHALL display a warning indicator immediately after the channel's estimate count whenever any estimate in the channel has missing stages (as resolved by `getMissingStages`). The indicator SHALL be an orange `AlertTriangle` followed by the total number of missing conversions — the sum of `getMissingStages` lengths across all unique estimates in the channel. Because this total is unbounded, the number SHALL NOT use the per-estimate severity scale and SHALL be rendered in the triangle's orange. A tooltip SHALL state the total missing conversions and the number of affected estimates out of the channel total. The channel SHALL count each estimate once regardless of view mode (deriving unique estimates from stage events in all-mode and from rows otherwise).

#### Scenario: Channel with incomplete estimates
- **WHEN** a channel contains estimates whose missing stages sum to 5 across 3 affected estimates out of 12 total
- **THEN** the channel header SHALL show an orange triangle and the number `5` after the estimate count
- **AND** the tooltip SHALL read "5 missing conversions across 3 of 12 estimates"

#### Scenario: Channel fully discovered
- **WHEN** every estimate in a channel has all three stages discovered
- **THEN** no warning indicator SHALL be rendered in the channel header

#### Scenario: All-mode counts each estimate once
- **WHEN** the view is in all-mode, where an estimate appears as multiple stage-event rows
- **THEN** the channel total SHALL count that estimate's missing stages exactly once

### Requirement: All-mode expanded panel surfaces missing stages
In all-mode the expanded panel renders only the event's own stage. It SHALL additionally render each missing stage (as resolved by `getMissingStages`) as a collapsed stage summary, so a sequential gap is visible without switching to a single-stage filter. Each such missing stage summary SHALL be marked orange — an orange `AlertTriangle` icon in place of the status icon and an orange stage label. This orange marking SHALL apply only in all-mode; single-stage filters continue to render their collapsed non-active stages unchanged.

#### Scenario: Missing stage shown in all-mode
- **WHEN** an all-mode row is expanded for an estimate whose Qualified event is shown but Booking is undiscovered (a gap)
- **THEN** the panel SHALL render the Qualified stage in full
- **AND** SHALL render a collapsed Booking stage summary marked with an orange triangle and orange label

#### Scenario: No missing stage to surface
- **WHEN** an all-mode row is expanded for an estimate with no sequential gap
- **THEN** the panel SHALL render only the event's own stage, with no extra collapsed stage summaries
