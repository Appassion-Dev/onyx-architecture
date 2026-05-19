## ADDED Requirements

### Requirement: Rollup rail uses a fixed five-column model
Each rollup row in the Conversions page hierarchy SHALL render a metric rail with exactly five columns, in this order: `Stage`, `Method`, `Push`, `Acceptance`, `Value`. The column model SHALL be applied at the Month, Week, and SourceGroup levels of the hierarchy, with the only exception being that the SourceGroup level OMITS the Acceptance column (see `rollup-acceptance-metric`). The Month and Week levels include all five columns.

#### Scenario: Month rollup column order
- **WHEN** a MonthCard is rendered in any single-stage mode or in `all` mode
- **THEN** the metric rail SHALL contain five columns in this order: Stage, Method, Push, Acceptance, Value

#### Scenario: Week rollup column order
- **WHEN** a WeekBlock is rendered in any single-stage mode or in `all` mode
- **THEN** the metric rail SHALL contain five columns in this order: Stage, Method, Push, Acceptance, Value

#### Scenario: SourceGroup rollup omits Acceptance
- **WHEN** a SourceGroupBlock is rendered in any mode
- **THEN** the metric rail SHALL contain four columns in this order: Stage, Method, Push, Value (Acceptance is NOT rendered at the SourceGroup level)

### Requirement: Each rollup column adapts to single-stage and all-stages modes
In single-stage modes (`booking`, `qualified`, `converted`), every rollup column SHALL render one value for the active stage. In `all` mode, every column SHALL render a single inline value on one line: the `Stage` column renders an inline triple `booking / qualified / converted` (slash-separated, color-keyed by stage); the `Method`, `Push`, `Acceptance`, and `Value` columns each render a single aggregate spanning all three stages. No column SHALL render vertically stacked per-stage sub-values — every column occupies one row of height at every hierarchy level so columns vertically align across Month, Week, SourceGroup, and estimate rows.

#### Scenario: Single-stage rendering
- **WHEN** the active mode is `booking`, `qualified`, or `converted`
- **THEN** every column in the rollup rail SHALL render one value for the active stage

#### Scenario: All-stages Stage column inline triple
- **WHEN** the active mode is `all`
- **THEN** the `Stage` column SHALL render a single inline `booking / qualified / converted` triple, formatted in the same `font-mono tabular-nums text-xs` style as the `Method` and `Push` columns, with each number tinted in its stage's identifying color (booking purple `#4318ff`, qualified green `#01b574`, converted dark green `#017a50`)

#### Scenario: All-stages aggregated columns
- **WHEN** the active mode is `all`
- **THEN** the `Method`, `Push`, `Acceptance`, and `Value` columns SHALL each render a single aggregate computed by summing across booking / qualified / converted (the stage breakdown lives exclusively in the `Stage` column)

#### Scenario: Cross-level vertical alignment
- **WHEN** the rollup rail renders at any hierarchy level (Month, Week, SourceGroup)
- **THEN** the Stage, Method, Push, and Value columns SHALL occupy the same horizontal positions; SourceGroup omits Acceptance by leaving its slot empty rather than collapsing the grid

#### Scenario: Empty stage in all-stages mode
- **WHEN** the active mode is `all` and a stage has zero applicable rows in the rollup window
- **THEN** the corresponding number in the `Stage` column's inline triple SHALL render as `0` (NOT as `—` or hidden)

### Requirement: Stage column shows the count of conversions at that stage
The Stage column SHALL show the count of rows present at the named stage within the rollup window. A row "is present" at a stage when the corresponding stage status column on `vw_conversion_candidates` is non-null (i.e. the stage has been discovered for that estimate).

#### Scenario: Single-stage Stage column
- **WHEN** the active mode is `qualified` and the rollup window contains 12 estimates with a non-null `qualified_status`
- **THEN** the Stage column SHALL display `12`

#### Scenario: All-stages Stage column breakdown
- **WHEN** the active mode is `all` and the rollup window contains 20 estimates with `booking_status` non-null, 12 with `qualified_status` non-null, and 7 with `converted_status` non-null
- **THEN** the Stage column SHALL display three stage-stacked sub-values: `20 / 12 / 7` (or equivalent side-by-side layout) in booking → qualified → converted order

### Requirement: Method column classifies each conversion by payload mechanism
The Method column SHALL count rows by which Google Ads upload mechanism applies to them, partitioning into three mutually exclusive buckets that mirror `supabase/functions/google-ads-conversion-upload/payload-builder.ts`:
- `with_gclid`: the per-stage `{stage}_gclid` column on `vw_conversion_candidates` is non-null. The row uploads via GCLID (with or without enhanced-conversion identifiers).
- `user_data_only`: the per-stage `{stage}_gclid` is NULL AND the customer has at least one usable identifier (email or mobile number). The row uploads via enhanced-conversions-only (`userIdentifiers` with `consent.adUserData = GRANTED`).
- `none`: the per-stage `{stage}_gclid` is NULL AND the customer has no usable identifier. The row CANNOT be uploaded.

The three counts SHALL sum to the value shown in the Stage column for the same stage.

#### Scenario: Classifier matches payload builder behavior
- **WHEN** a row has `qualified_gclid` non-null
- **THEN** the row SHALL be counted in the `with_gclid` bucket for the Qualified column regardless of the customer's email/phone presence

#### Scenario: User-data-only path
- **WHEN** a row has `qualified_gclid` NULL but the customer has a non-empty email OR mobile number
- **THEN** the row SHALL be counted in the `user_data_only` bucket for the Qualified column

#### Scenario: No identifier
- **WHEN** a row has `qualified_gclid` NULL and the customer has neither an email nor a mobile number
- **THEN** the row SHALL be counted in the `none` bucket for the Qualified column

#### Scenario: All-stages Method column
- **WHEN** the active mode is `all`
- **THEN** the Method column SHALL show a single aggregated triple `with_gclid / user_data_only / none` whose components are the sums of the corresponding per-stage counts across booking + qualified + converted, and whose total SHALL equal the sum of the three Stage sub-values

### Requirement: Push column shows local upload outcomes
The Push column SHALL count rows by their local upload state on `vw_conversion_candidates` per stage:
- `total_sent`: rows where `{stage}_status = 'uploaded'` OR `{stage}_upload_attempts > 0` (we attempted at least one push).
- `sent_no_error`: rows where `{stage}_status = 'uploaded'` AND `{stage}_error_message IS NULL`.
- `sent_with_error`: rows where `{stage}_error_message IS NOT NULL` on the latest attempt.

`sent_no_error` and `sent_with_error` SHALL be partitions of `total_sent` (their sum SHALL equal `total_sent` in single-stage mode).

#### Scenario: Successful upload counted
- **WHEN** a row has `qualified_status = 'uploaded'` and `qualified_error_message IS NULL`
- **THEN** the row SHALL be counted in both `total_sent` and `sent_no_error` for the Qualified column

#### Scenario: Errored upload counted
- **WHEN** a row has `qualified_upload_attempts > 0` and `qualified_error_message IS NOT NULL`
- **THEN** the row SHALL be counted in both `total_sent` and `sent_with_error` for the Qualified column

#### Scenario: Pending non-attempted row excluded
- **WHEN** a row has `qualified_status = 'pending'` and `qualified_upload_attempts = 0` and `qualified_error_message IS NULL`
- **THEN** the row SHALL NOT be counted in any of `total_sent`, `sent_no_error`, or `sent_with_error`

#### Scenario: All-stages Push column
- **WHEN** the active mode is `all`
- **THEN** the Push column SHALL show a single aggregated triple `total_sent / sent_no_error / sent_with_error` whose components are the sums across booking + qualified + converted

### Requirement: Value column shows mode-appropriate stage value sum
The Value column SHALL show the dollar sum of the stage's value field within the rollup window. In single-stage `qualified` mode the field is `qualified_value`; in single-stage `converted` mode the field is `converted_value`; in single-stage `booking` mode the column SHALL display `—` (booking has no per-row value). In `all` mode the column SHALL display a single aggregated currency total equal to `sum(qualified_value) + sum(converted_value)` (booking contributes zero).

#### Scenario: Booking has no value
- **WHEN** the active mode is `booking`
- **THEN** the Value column SHALL display `—`

#### Scenario: Qualified value sum
- **WHEN** the active mode is `qualified`
- **THEN** the Value column SHALL display the formatted sum of `qualified_value` across rows in the rollup window

#### Scenario: All-stages value aggregate
- **WHEN** the active mode is `all`
- **THEN** the Value column SHALL display a single formatted currency value equal to `sum(qualified_value) + sum(converted_value)` over rows in the rollup window

### Requirement: Column labels are uppercase short-form headers
Each rollup column SHALL display its label as a short uppercase tracking-wide header (e.g. `STAGE`, `METHOD`, `PUSH`, `ACCEPT`, `VALUE`) using the existing `text-[9px] font-semibold uppercase tracking-[0.16em] text-[#a3aed0]` style class.

#### Scenario: Column header style
- **WHEN** a rollup rail is rendered at any hierarchy level
- **THEN** each column header SHALL match the existing label style used by `RollupMetricCell`
