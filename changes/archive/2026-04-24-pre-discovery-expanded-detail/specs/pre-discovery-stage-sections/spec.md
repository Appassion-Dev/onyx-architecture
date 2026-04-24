## ADDED Requirements

### Requirement: Expanded detail panel always renders all three stage sections
The system SHALL render the Booking Lead, Qualified Lead, and Converted Lead sections in the expanded detail panel for every estimate row, regardless of whether the estimate has been discovered (i.e., regardless of whether `booking_status`, `qualified_status`, or `converted_status` are null).

#### Scenario: Pre-discovery estimate shows all stage sections
- **WHEN** a user expands an estimate row where `booking_status`, `qualified_status`, and `converted_status` are all `null`
- **THEN** the expanded panel renders a Booking Lead section, a Qualified Lead section, and a Converted Lead section

#### Scenario: Discovered estimate is unaffected
- **WHEN** a user expands an estimate row where one or more stage statuses are non-null
- **THEN** the expanded panel renders identically to the current behavior, showing `StageDetail` with status, upload attempts, GCLID, and datetime for each non-null stage

### Requirement: StageDetail renders a neutral state when status is null
The system SHALL render a neutral "Not discovered" display in `StageDetail` when `status` is `null`, without throwing errors or showing misleading data.

#### Scenario: StageDetail with null status
- **WHEN** `StageDetail` receives `status = null`
- **THEN** it renders the stage label (e.g., "Booking Lead") with a "Not discovered" status indicator in muted text, and suppresses GCLID, value, date, upload attempts, and error message fields

#### Scenario: StageDetail with non-null status is unchanged
- **WHEN** `StageDetail` receives a non-null status (e.g., `'pending'`, `'uploaded'`, `'skipped'`)
- **THEN** it renders exactly as it does today

### Requirement: Booking Lead section shows consolidated empty state when no attribution data exists
The system SHALL display a single "No attribution data detected" message in the Booking Lead section when the estimate has no form submission (`has_form` is false) and no CallRail calls (`call_count === 0`).

#### Scenario: No form and no calls on pre-discovery estimate
- **WHEN** `has_form` is `false` and `call_count === 0`
- **THEN** the Booking Lead section shows "No attribution data detected" instead of separate "No form submission recorded" and "No calls recorded" messages

#### Scenario: Has form but no calls
- **WHEN** `has_form` is `true` and `call_count === 0`
- **THEN** `BookingTagsTable` renders and "No calls recorded" shows beneath it (existing behavior)

#### Scenario: Has calls but no form
- **WHEN** `has_form` is `false` and `call_count > 0`
- **THEN** "No form submission recorded" shows and `CallHistoryTable` renders beneath it (existing behavior)

### Requirement: Qualified Lead section always shows estimate options
The system SHALL render `EstimateOptionsTable` in the Qualified Lead section for every estimate row. When no options exist, `EstimateOptionsTable` SHALL display its existing "No estimate options found" empty state.

#### Scenario: Pre-discovery estimate with no options
- **WHEN** an estimate has no `estimate_options` rows
- **THEN** the Qualified Lead section renders with "No estimate options found"

#### Scenario: Pre-discovery estimate with options
- **WHEN** an estimate has `estimate_options` rows
- **THEN** the Qualified Lead section renders the options table as it does today for discovered estimates
