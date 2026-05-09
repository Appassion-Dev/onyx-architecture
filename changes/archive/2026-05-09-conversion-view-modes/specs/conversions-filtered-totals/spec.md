## MODIFIED Requirements

### Requirement: Month and week totals reflect active filters
When one or more filters are active, the quantity count and total value displayed in each month and week header SHALL reflect only the visible (filtered) estimates. The value summed in rollup totals SHALL use the mode-appropriate value field: `qualified_value` when the active mode is Qualified, `converted_value` when the active mode is Converted, and no value (hidden or zero) when the active mode is Pre-discovery or Booking.

#### Scenario: No filters active, Qualified mode
- **WHEN** all filter dropdowns are at default and the active mode is Qualified
- **THEN** month and week headers show estimate counts and totals summing `qualified_value`

#### Scenario: No filters active, Converted mode
- **WHEN** all filter dropdowns are at default and the active mode is Converted
- **THEN** month and week headers show estimate counts and totals summing `converted_value`

#### Scenario: No value in Pre-discovery or Booking mode
- **WHEN** the active mode is Pre-discovery or Booking
- **THEN** month and week headers show only the estimate count with no monetary total

#### Scenario: Filter reduces visible estimates
- **WHEN** one or more filters are active
- **THEN** each month header shows the qty and mode-appropriate value sum of only the filtered estimates in that month
- **AND** each week header shows the qty and mode-appropriate value sum of only the filtered estimates in that week

#### Scenario: Filter eliminates all estimates in a month
- **WHEN** active filters match no estimates in a given month
- **THEN** that month group does not appear in the hierarchy

### Requirement: Bulk upload buttons scope to filtered estimates
The bulk upload button on each month and week header SHALL only include the pending estimate IDs for the **active mode's stage** from the currently visible (filtered) rows.

#### Scenario: Bulk upload scopes to active mode stage
- **WHEN** the active mode is Qualified and the user clicks a month-level upload button
- **THEN** only estimates visible in that month with `qualified_status = 'pending'` are included in the upload batch

#### Scenario: Bulk upload in Converted mode
- **WHEN** the active mode is Converted and the user clicks a month-level upload button
- **THEN** only estimates visible in that month with `converted_status = 'pending'` are included in the upload batch

#### Scenario: No pending estimates after filtering
- **WHEN** active filters result in no pending estimates for the active mode's stage in a given month or week
- **THEN** the bulk upload button for that month or week is not rendered

### Requirement: Show zero-value estimates toggle
The filter bar SHALL include a "Show zero values" toggle. When inactive (default), estimates where the **mode-appropriate value field** is NULL, zero, or negative are hidden. The toggle SHALL only be shown when the active mode is Qualified or Converted. It SHALL be hidden in Pre-discovery and Booking modes.

#### Scenario: Toggle hidden in Booking mode
- **WHEN** the active mode is Booking
- **THEN** the "Show zero values" toggle SHALL NOT be rendered

#### Scenario: Toggle hidden in Pre-discovery mode
- **WHEN** the active mode is Pre-discovery
- **THEN** the "Show zero values" toggle SHALL NOT be rendered

#### Scenario: Toggle in Qualified mode checks qualified_value
- **WHEN** the active mode is Qualified and the toggle is inactive
- **THEN** estimates where `qualified_value <= 0` (or NULL) are excluded from the visible set

#### Scenario: Toggle in Converted mode checks converted_value
- **WHEN** the active mode is Converted and the toggle is inactive
- **THEN** estimates where `converted_value <= 0` (or NULL) are excluded from the visible set

#### Scenario: Checkbox checked
- **WHEN** the user activates the toggle
- **THEN** estimates with a zero or null mode-appropriate value are included in the visible set, subject to other active filters
