## Requirements

### Requirement: Month and week totals reflect active filters
When one or more filters are active, every column of the rollup metric rail at Month and Week level SHALL reflect only the visible (filtered) estimates. The columns SHALL be the five defined by the `rollup-metric-columns` capability: Stage, Method, Push, Acceptance, Value. The Value column SHALL use the mode-appropriate field — `qualified_value` in Qualified mode, `converted_value` in Converted mode, `—` in Pre-discovery and Booking modes — and SHALL display three sub-values (booking `—`, qualified sum, converted sum) in `all` mode.

#### Scenario: No filters active, Qualified mode
- **WHEN** all filter dropdowns are at default and the active mode is `qualified`
- **THEN** Month and Week headers show single-stage values for Stage, Method, Push, Acceptance, and Value (summing `qualified_value`) for the Qualified stage only

#### Scenario: No filters active, Converted mode
- **WHEN** all filter dropdowns are at default and the active mode is `converted`
- **THEN** Month and Week headers show single-stage values for Stage, Method, Push, Acceptance, and Value (summing `converted_value`) for the Converted stage only

#### Scenario: No filters active, All mode
- **WHEN** all filter dropdowns are at default and the active mode is `all`
- **THEN** Month and Week headers show three sub-values per column one per stage (booking / qualified / converted) including the Acceptance sub-values fetched from `vw_gads_upload_reconciliation_daily` per `event_key`

#### Scenario: No value in Pre-discovery or Booking mode
- **WHEN** the active mode is `pre-discovery` or `booking`
- **THEN** the Value column displays `—` (no monetary total)

#### Scenario: Filter reduces visible estimates
- **WHEN** one or more filters are active
- **THEN** each Month header shows Stage / Method / Push / Acceptance / Value computed only over the filtered estimates in that month
- **AND** each Week header shows Stage / Method / Push / Acceptance / Value computed only over the filtered estimates in that week

#### Scenario: Filter eliminates all estimates in a month
- **WHEN** active filters match no estimates in a given month
- **THEN** that month group does not appear in the hierarchy

### Requirement: Page-level bulk upload reflects the filtered hierarchy
The single top-of-page bulk upload button (defined by `bulk-upload-scoped`) SHALL include only the pending estimate IDs from the currently visible (filtered) hierarchy. In single-stage modes (`booking`, `qualified`, `converted`) it includes pending IDs for the active stage. In `all` mode it includes pending IDs across booking, qualified, and converted; the confirm dialog SHALL group the IDs by `conversion_type` so the user can review per-stage counts before confirming. There SHALL NOT be any per-bucket (Month / Week / SourceGroup) bulk upload buttons.

#### Scenario: Page-level bulk upload scopes to active mode stage
- **WHEN** the active mode is `qualified` and the user clicks the top-of-page Upload button
- **THEN** only filtered-visible estimates with `qualified_status = 'pending'` are included in the upload batch

#### Scenario: Page-level bulk upload in Converted mode
- **WHEN** the active mode is `converted` and the user clicks the top-of-page Upload button
- **THEN** only filtered-visible estimates with `converted_status = 'pending'` are included in the upload batch

#### Scenario: Page-level bulk upload in All mode
- **WHEN** the active mode is `all` and the user clicks the top-of-page Upload button
- **THEN** the batch SHALL include estimates with any of `booking_status = 'pending'`, `qualified_status = 'pending'`, or `converted_status = 'pending'`
- **AND** the confirm dialog SHALL show the per-stage breakdown of the affected estimate IDs

#### Scenario: No pending estimates after filtering
- **WHEN** active filters result in no pending estimates for the relevant stages anywhere in the visible hierarchy
- **THEN** the top-of-page Upload button SHALL NOT be rendered (or SHALL be disabled)

#### Scenario: No per-bucket buttons
- **WHEN** Month, Week, or SourceGroup rollups are rendered in any mode
- **THEN** no Upload button or bulk-action control SHALL appear on those rollup headers

### Requirement: Show zero-value estimates toggle
The filter bar SHALL include a "Show zero values" toggle. When inactive (default), estimates where the **mode-appropriate value field** is NULL, zero, or negative are hidden. The toggle SHALL only be shown when the active mode is `qualified` or `converted`. It SHALL be hidden in `pre-discovery`, `booking`, and `all` modes (in `all` mode the rail simultaneously shows two value fields, so the toggle is ambiguous).

#### Scenario: Toggle hidden in Booking mode
- **WHEN** the active mode is `booking`
- **THEN** the "Show zero values" toggle SHALL NOT be rendered

#### Scenario: Toggle hidden in Pre-discovery mode
- **WHEN** the active mode is `pre-discovery`
- **THEN** the "Show zero values" toggle SHALL NOT be rendered

#### Scenario: Toggle hidden in All mode
- **WHEN** the active mode is `all`
- **THEN** the "Show zero values" toggle SHALL NOT be rendered

#### Scenario: Toggle in Qualified mode checks qualified_value
- **WHEN** the active mode is `qualified` and the toggle is inactive
- **THEN** estimates where `qualified_value <= 0` (or NULL) are excluded from the visible set

#### Scenario: Toggle in Converted mode checks converted_value
- **WHEN** the active mode is `converted` and the toggle is inactive
- **THEN** estimates where `converted_value <= 0` (or NULL) are excluded from the visible set

#### Scenario: Checkbox checked
- **WHEN** the user activates the toggle
- **THEN** estimates with a zero or null mode-appropriate value are included in the visible set, subject to other active filters
