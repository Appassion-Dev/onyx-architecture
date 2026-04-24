## ADDED Requirements

### Requirement: Month and week totals reflect active filters
When one or more filters are active, the quantity count and total value displayed in each month and week header SHALL reflect only the visible (filtered) estimates — not the full 90-day dataset.

#### Scenario: No filters active
- **WHEN** all filter dropdowns are set to "All"
- **THEN** month and week headers show counts and totals for all estimates in the 90-day window

#### Scenario: Filter reduces visible estimates
- **WHEN** one or more filters are active
- **THEN** each month header shows the qty and value sum of only the filtered estimates in that month
- **AND** each week header shows the qty and value sum of only the filtered estimates in that week

#### Scenario: Filter eliminates all estimates in a month
- **WHEN** active filters match no estimates in a given month
- **THEN** that month group does not appear in the hierarchy

### Requirement: Bulk upload buttons scope to filtered estimates
The bulk upload button on each month and week header SHALL only include the pending estimate IDs from the currently visible (filtered) rows. Estimates hidden by an active filter are excluded from the upload batch.

#### Scenario: Bulk upload respects active filter
- **WHEN** a Source filter is active (e.g., "Google Ads") and the user clicks the month-level upload button
- **THEN** only estimates matching the active filter that have a pending status are included in the upload batch

#### Scenario: No pending estimates after filtering
- **WHEN** active filters result in no pending estimates for a given month or week
- **THEN** the bulk upload button for that month or week is not rendered

### Requirement: Show zero-value estimates toggle
The filter bar SHALL include a "Show zero values" checkbox. When unchecked (default), estimates where `display_value` is NULL, zero, or negative are hidden. When checked, those estimates are shown alongside all others. This filter combines with all other active filters using AND logic.

#### Scenario: Checkbox unchecked (default)
- **WHEN** the page loads
- **THEN** the "Show zero values" checkbox is unchecked and estimates with `display_value <= 0` (or NULL) are excluded from the visible set

#### Scenario: Checkbox checked
- **WHEN** the user checks "Show zero values"
- **THEN** estimates with `display_value <= 0` (or NULL) are included in the visible set, subject to other active filters

#### Scenario: Zero-value filter interacts with totals
- **WHEN** "Show zero values" is unchecked
- **THEN** month and week totals exclude zero-value estimates, consistent with the other filter requirements above

### Implementation note
This behavior is achieved by passing `filteredRows` (not `rows`) into `buildHierarchy`. All month and week groups produced by `buildHierarchy` contain only filtered rows. `computeStats` and `getPendingEstimateIds` both operate on those scoped row sets, so totals and upload targets are automatically filter-aware without additional logic.
